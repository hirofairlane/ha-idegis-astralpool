"""Weekly HTML email report.

Renders a Jinja2 template using the latest snapshot + counters and sends
it through the HA `notify.<service>` configured by the user. Falls back
to Telegram with a compressed text version if email service is not set.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aggregator import AGG, COUNTERS
from config import SETTINGS
from ha_client import HA

log = logging.getLogger("pool_brain.reporter")

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render_html() -> str:
    template = _env.get_template("weekly_email.html.j2")
    return template.render(
        snapshot=AGG.snapshot,
        runtime_today=COUNTERS.runtime_today(),
        runtime_week=COUNTERS.runtime_week(),
        filter_kwh_today=COUNTERS.filter_kwh_today(),
        filter_kwh_week=COUNTERS.filter_kwh_week(),
        cleaner_kwh_today=COUNTERS.cleaner_kwh_today(),
        cleaner_kwh_week=COUNTERS.cleaner_kwh_week(),
        runtime_history=COUNTERS.data.get("runtime_minutes", {}),
        filter_kwh_history=COUNTERS.data.get("filter_kwh", {}),
        now=datetime.now().astimezone(),
    )


def _telegram_summary() -> str:
    s = AGG.snapshot or {}
    return (
        "🏊 *Pool Brain — semana en una línea*\n\n"
        f"Salud: {s.get('health_score', '?')}/100\n"
        f"pH {s.get('bands', {}).get('ph', '?')} · "
        f"Sal {s.get('bands', {}).get('salt', '?')} · "
        f"Temp {s.get('bands', {}).get('temperature', '?')}\n"
        f"Depuradora 7d: {COUNTERS.runtime_week()} min · "
        f"{COUNTERS.filter_kwh_week()} kWh\n"
        f"Limpiafondos 7d: {COUNTERS.cleaner_kwh_week()} kWh"
    )


async def send_weekly_report() -> None:
    if not SETTINGS.weekly_report_enabled:
        return
    html = _render_html()

    target = SETTINGS.notify_email_service
    if target:
        ok = await HA.notify(
            target,
            "Reporte semanal de la piscina (HTML adjunto)",
            title="Pool Brain — Reporte semanal",
            data={"html": html},
        )
        if ok:
            log.info("weekly report sent via %s", target)
            return
        log.warning("email send via %s failed; falling back to Telegram", target)

    if SETTINGS.notify_telegram_service:
        await HA.notify(SETTINGS.notify_telegram_service, _telegram_summary())
        log.info("weekly report sent via Telegram fallback")
