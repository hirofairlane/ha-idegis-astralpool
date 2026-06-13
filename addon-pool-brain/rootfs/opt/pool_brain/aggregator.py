"""Periodic aggregator.

Pulls the snapshot from the capturer + the live HA states (Shelly
channels), computes every synthetic value, and pushes them through the
MQTT publisher. Also tracks per-day counters that persist in `/data`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from capturer_client import CAPTURER
from config import SETTINGS
from ha_client import HA
from health import HealthInput, all_ok, health_score
from mqtt_pub import MQTT
from timer_engine import (
    TimerInput,
    nominal_flow_for_serial,
    recommended_minutes_today,
    recommended_minutes_week,
)

log = logging.getLogger("pool_brain.aggregator")

STATE_FILE = Path("/data/state.json")


# ----- Persistent counters --------------------------------------------------


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _today_key() -> str:
    return _now_local().date().isoformat()


def _week_window() -> tuple[datetime, datetime]:
    end = _now_local()
    start = end - timedelta(days=7)
    return start, end


class Counters:
    """Per-day runtime minutes and kWh accumulators.

    `runtime_minutes_today` increments by 1 every minute the pump switch
    is `on`. kWh is integrated from the live W reading.
    """

    def __init__(self) -> None:
        self.data: dict[str, Any] = {
            "runtime_minutes": {},  # day -> int
            "filter_kwh": {},  # day -> float
            "cleaner_kwh": {},  # day -> float
            "pump_nominal_w": 1100.0,  # learned baseline
            "cleaner_nominal_w": 600.0,
            "last_pump_w_sample_ts": 0.0,
            "last_cleaner_w_sample_ts": 0.0,
        }
        self.load()

    def load(self) -> None:
        if STATE_FILE.exists():
            try:
                self.data.update(json.loads(STATE_FILE.read_text()))
            except Exception as exc:  # noqa: BLE001
                log.warning("counters load failed: %s", exc)

    def save(self) -> None:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(self.data))
        except Exception as exc:  # noqa: BLE001
            log.warning("counters save failed: %s", exc)

    # --- Accessors ----

    def _bump_day(self, bucket: str, day: str, delta: float) -> None:
        d = self.data.setdefault(bucket, {})
        d[day] = round(d.get(day, 0) + delta, 6)
        # prune older than 60 days
        keep = (_now_local().date() - timedelta(days=60)).isoformat()
        for k in list(d):
            if k < keep:
                d.pop(k, None)

    def add_pump_minute(self) -> None:
        self._bump_day("runtime_minutes", _today_key(), 1)

    def integrate_filter_power(self, watts: float) -> None:
        now = time.time()
        prev = self.data.get("last_pump_w_sample_ts", 0.0)
        if prev > 0:
            dt_h = (now - prev) / 3600
            self._bump_day("filter_kwh", _today_key(), watts * dt_h / 1000)
        self.data["last_pump_w_sample_ts"] = now

    def integrate_cleaner_power(self, watts: float) -> None:
        now = time.time()
        prev = self.data.get("last_cleaner_w_sample_ts", 0.0)
        if prev > 0:
            dt_h = (now - prev) / 3600
            self._bump_day("cleaner_kwh", _today_key(), watts * dt_h / 1000)
        self.data["last_cleaner_w_sample_ts"] = now

    def reset_today_runtime(self) -> None:
        self.data.setdefault("runtime_minutes", {}).pop(_today_key(), None)

    def runtime_today(self) -> int:
        return int(self.data.get("runtime_minutes", {}).get(_today_key(), 0))

    def runtime_week(self) -> int:
        keep = (_now_local().date() - timedelta(days=7)).isoformat()
        return int(sum(
            v for k, v in self.data.get("runtime_minutes", {}).items() if k > keep
        ))

    def filter_kwh_today(self) -> float:
        return round(self.data.get("filter_kwh", {}).get(_today_key(), 0), 3)

    def filter_kwh_week(self) -> float:
        keep = (_now_local().date() - timedelta(days=7)).isoformat()
        return round(sum(
            v for k, v in self.data.get("filter_kwh", {}).items() if k > keep
        ), 3)

    def cleaner_kwh_today(self) -> float:
        return round(self.data.get("cleaner_kwh", {}).get(_today_key(), 0), 3)

    def cleaner_kwh_week(self) -> float:
        keep = (_now_local().date() - timedelta(days=7)).isoformat()
        return round(sum(
            v for k, v in self.data.get("cleaner_kwh", {}).items() if k > keep
        ), 3)


COUNTERS = Counters()


# ----- Main aggregation loop ------------------------------------------------


class Aggregator:
    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}
        self._last_pump_minute_marked = 0.0

    async def tick(self) -> None:
        # 1. Fetch upstream
        cap = await CAPTURER.fetch_state()
        pump_state = await HA.get_state_value(SETTINGS.pump_switch_entity)
        pump_w = await HA.get_state_float(SETTINGS.pump_power_entity, 0.0) or 0.0
        cleaner_state = (
            await HA.get_state_value(SETTINGS.cleaner_switch_entity)
            if SETTINGS.cleaner_switch_entity
            else None
        )
        cleaner_w = (
            await HA.get_state_float(SETTINGS.cleaner_power_entity, 0.0)
            if SETTINGS.cleaner_power_entity
            else None
        ) or 0.0

        # 2. Update counters
        if pump_state == "on":
            now = time.time()
            if now - self._last_pump_minute_marked >= 60:
                COUNTERS.add_pump_minute()
                self._last_pump_minute_marked = now
        COUNTERS.integrate_filter_power(pump_w)
        if SETTINGS.cleaner_power_entity:
            COUNTERS.integrate_cleaner_power(cleaner_w)
        COUNTERS.save()

        # 3. Extract trusted values from capturer
        measurements = cap.get("measurements") or {}
        ls = cap.get("last_session") or {}
        ls_avg = (ls.get("aggregates") or {}) if ls else {}

        def _agg(field: str) -> float | None:
            v = (ls_avg.get(field) or {}).get("avg")
            return float(v) if v is not None else None

        ph = _agg("SG") or (measurements.get("ph") or {}).get("value")
        salt = _agg("IT") or (measurements.get("salinity") or {}).get("value")
        temp = _agg("CY") or (measurements.get("water_temperature") or {}).get(
            "value"
        )
        production = _agg("GY") or (
            measurements.get("chlorine_production") or {}
        ).get("value")

        first_minutes = self._in_first_minutes(cap)

        # 4. Bands
        h_in = HealthInput(
            ph=float(ph) if ph is not None else None,
            salt_g_l=float(salt) if salt is not None else None,
            temperature_c=float(temp) if temp is not None else None,
            production_pct=float(production) if production is not None else None,
            pump_anomaly=False,  # filled by pump_watch
            cleaner_anomaly=False,
        )
        score, bands = health_score(h_in)
        healthy = all_ok(bands) and not first_minutes

        # 5. Recommended minutes
        t_in = TimerInput(
            water_temp_c=h_in.temperature_c,
            bands=bands,
            volume_m3=SETTINGS.pool_volume_m3,
            nominal_flow_m3_h=nominal_flow_for_serial(
                cap.get("device_serial")
            ),
            target_turnovers_per_day=SETTINGS.target_turnovers_per_day,
        )
        rec_today = recommended_minutes_today(t_in)
        rec_week = recommended_minutes_week(t_in)

        # 6. Turnovers
        runtime_today = COUNTERS.runtime_today()
        turnovers_today = round(
            runtime_today / 60 * t_in.nominal_flow_m3_h / SETTINGS.pool_volume_m3, 2
        )

        # 7. Push to MQTT
        await MQTT.publish("sensor", "health_score", score)
        await MQTT.publish("sensor", "recommended_minutes_today", rec_today)
        await MQTT.publish("sensor", "recommended_minutes_week", rec_week)
        await MQTT.publish("sensor", "runtime_minutes_today", runtime_today)
        await MQTT.publish("sensor", "runtime_minutes_week", COUNTERS.runtime_week())
        await MQTT.publish("sensor", "filter_kwh_today", COUNTERS.filter_kwh_today())
        await MQTT.publish("sensor", "filter_kwh_week", COUNTERS.filter_kwh_week())
        await MQTT.publish("sensor", "cleaner_kwh_today", COUNTERS.cleaner_kwh_today())
        await MQTT.publish("sensor", "cleaner_kwh_week", COUNTERS.cleaner_kwh_week())
        await MQTT.publish("sensor", "pump_avg_power", round(pump_w, 1))
        await MQTT.publish("sensor", "turnovers_today", turnovers_today)
        await MQTT.publish("sensor", "ph_band", bands["ph"])
        await MQTT.publish("sensor", "salt_band", bands["salt"])
        await MQTT.publish("sensor", "temperature_band", bands["temperature"])
        await MQTT.publish("sensor", "production_band", bands["production"])
        await MQTT.publish(
            "binary_sensor", "water_healthy", "ON" if healthy else "OFF"
        )
        await MQTT.publish(
            "binary_sensor",
            "first_minutes_window",
            "ON" if first_minutes else "OFF",
        )

        # 8. Cache snapshot for HTTP API
        self.snapshot = {
            "ts": _now_local().isoformat(),
            "online": (cap.get("online") if isinstance(cap.get("online"), bool) else True),
            "first_minutes_window": first_minutes,
            "measurements": {
                "ph": h_in.ph,
                "salt_g_l": h_in.salt_g_l,
                "temperature_c": h_in.temperature_c,
                "production_pct": h_in.production_pct,
            },
            "bands": bands,
            "health_score": score,
            "recommended_minutes_today": rec_today,
            "recommended_minutes_week": rec_week,
            "runtime_minutes_today": runtime_today,
            "runtime_minutes_week": COUNTERS.runtime_week(),
            "filter_kwh_today": COUNTERS.filter_kwh_today(),
            "filter_kwh_week": COUNTERS.filter_kwh_week(),
            "cleaner_kwh_today": COUNTERS.cleaner_kwh_today(),
            "cleaner_kwh_week": COUNTERS.cleaner_kwh_week(),
            "pump_avg_power_w": round(pump_w, 1),
            "cleaner_power_w": round(cleaner_w, 1),
            "pump_switch": pump_state,
            "cleaner_switch": cleaner_state,
            "turnovers_today": turnovers_today,
        }

    @staticmethod
    def _in_first_minutes(cap: dict[str, Any]) -> bool:
        ses = cap.get("current_session") or {}
        if not ses or not ses.get("active"):
            return False
        start_ts = ses.get("start_ts")
        if not start_ts:
            return False
        try:
            start = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        except ValueError:
            return False
        age = (datetime.now(timezone.utc) - start).total_seconds()
        return age < SETTINGS.first_minutes_window_s

    async def run_forever(self, interval_s: int = 30) -> None:
        while True:
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001
                log.exception("aggregator tick failed: %s", exc)
            await asyncio.sleep(interval_s)


AGG = Aggregator()
