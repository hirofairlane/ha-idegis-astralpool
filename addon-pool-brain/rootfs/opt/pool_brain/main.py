"""Entrypoint of the Pool Brain add-on.

Runs five long-lived asyncio tasks in a single event loop:
- The aggregator that pushes synthetic entities through MQTT every 30 s.
- The pump anomaly watchdog.
- The MQTT publisher (discovery + command subscription).
- An APScheduler job that fires the weekly report.
- An aiohttp web server on :8099 that serves the ingress dashboard and a
  small JSON API.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aggregator import AGG, COUNTERS
from capturer_client import CAPTURER
from config import SETTINGS
from ha_client import HA
from mqtt_pub import MQTT
import pump_watch
from reporter import send_weekly_report

# ----- Logging --------------------------------------------------------------

LOG_LEVEL = SETTINGS.log_level.upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pool_brain")


# ----- HTTP API + ingress dashboard -----------------------------------------

STATIC_DIR = Path(__file__).parent / "static"


async def api_state(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.json_response(AGG.snapshot or {})


async def api_history(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.json_response(
        {
            "capacity": AGG.history.capacity,
            "decimation_ticks": AGG.history.decimation,
            "series": AGG.history.snapshot(),
        }
    )


async def api_health(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.json_response(
        {
            "status": "ok" if AGG.snapshot else "warming-up",
            "capturer_last_error": CAPTURER.last_error,
        }
    )


async def api_run_report(request: web.Request) -> web.Response:  # noqa: ARG001
    asyncio.create_task(send_weekly_report())
    return web.json_response({"queued": True})


async def api_emergency_stop(request: web.Request) -> web.Response:
    which = request.match_info.get("which", "all")
    fn = {
        "all": pump_watch.emergency_stop_all,
        "pump": pump_watch.emergency_stop_pump,
        "cleaner": pump_watch.emergency_stop_cleaner,
    }.get(which)
    if fn is None:
        return web.json_response({"error": "unknown target"}, status=400)
    asyncio.create_task(fn())
    return web.json_response({"queued": True, "which": which})


async def root(request: web.Request) -> web.Response:  # noqa: ARG001
    idx = STATIC_DIR / "index.html"
    if not idx.exists():
        return web.Response(text="Pool Brain ingress not built yet", status=200)
    return web.FileResponse(idx)


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/api/brain/state", api_state)
    app.router.add_get("/api/brain/history", api_history)
    app.router.add_get("/api/brain/health", api_health)
    app.router.add_post("/api/brain/run-report", api_run_report)
    app.router.add_post("/api/brain/emergency-stop/{which}", api_emergency_stop)
    app.router.add_static("/static/", path=str(STATIC_DIR), show_index=False)
    return app


# ----- MQTT command wiring --------------------------------------------------


def wire_mqtt_commands() -> None:
    MQTT.on_command("emergency_stop_all", pump_watch.emergency_stop_all)
    MQTT.on_command("emergency_stop_pump", pump_watch.emergency_stop_pump)
    MQTT.on_command("emergency_stop_cleaner", pump_watch.emergency_stop_cleaner)
    MQTT.on_command("run_weekly_report_now", send_weekly_report)


# ----- Scheduler ------------------------------------------------------------


def schedule_weekly_report(scheduler: AsyncIOScheduler) -> None:
    if not SETTINGS.weekly_report_enabled:
        log.info("weekly report disabled by option")
        return
    day_map = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    day = day_map.get(SETTINGS.weekly_report_day.lower(), 6)
    trigger = CronTrigger(day_of_week=day, hour=SETTINGS.weekly_report_hour, minute=0)
    scheduler.add_job(send_weekly_report, trigger, name="weekly_report")
    log.info(
        "weekly report scheduled at day_of_week=%s hour=%s",
        SETTINGS.weekly_report_day,
        SETTINGS.weekly_report_hour,
    )


# ----- Main -----------------------------------------------------------------


async def main() -> None:
    log.info("Pool Brain starting (log level %s)", LOG_LEVEL)

    wire_mqtt_commands()
    await MQTT.start()

    scheduler = AsyncIOScheduler()
    schedule_weekly_report(scheduler)
    scheduler.start()

    # background loops
    asyncio.create_task(AGG.run_forever(interval_s=30))
    asyncio.create_task(pump_watch.run_forever(interval_s=10))

    # HTTP server
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8099)
    await site.start()
    log.info("HTTP ingress listening on :8099")

    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        await runner.cleanup()
        await CAPTURER.close()
        await HA.close()
        await MQTT.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
