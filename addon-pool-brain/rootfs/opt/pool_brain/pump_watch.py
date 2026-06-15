"""Pump/cleaner anomaly watchdog.

Owns the orchestration loop (HA reads + MQTT publish + Telegram + auto
stop). The decision logic itself lives in `anomaly.py`; the nominal-W
self-calibration lives in `nominal_learner.py`. Both are pure modules
covered by unit tests.

For each watched Shelly channel, every 10 s we:

1. Sample the HA switch state and the live wattage.
2. Update the nominal-W EMA (only when the switch is on and power is
   above the noise floor).
3. Persist the new nominal so it survives restarts.
4. Ask `anomaly.decide` whether an anomaly is firing.
5. If just_fired, send a Telegram alert and optionally call
   `switch.turn_off` (dry running only, and only when
   `auto_emergency_stop` is true).
6. Publish the binary_sensor + the learned nominal to MQTT.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import anomaly
import nominal_learner
from aggregator import COUNTERS
from config import SETTINGS
from ha_client import HA
from mqtt_pub import MQTT

log = logging.getLogger("pool_brain.pump_watch")


@dataclass
class Channel:
    label: str
    mqtt_key: str  # "pump" or "cleaner" — used to derive entity names
    switch_entity: str
    power_entity: str


@dataclass
class _PerChannelState:
    latched: anomaly.Latched
    learner: nominal_learner.LearnerState


def _build_channels() -> list[tuple[Channel, _PerChannelState]]:
    out: list[tuple[Channel, _PerChannelState]] = []
    out.append(
        (
            Channel(
                "Depuradora",
                "pump",
                SETTINGS.pump_switch_entity,
                SETTINGS.pump_power_entity,
            ),
            _PerChannelState(
                latched=anomaly.Latched(),
                learner=nominal_learner.LearnerState(
                    nominal_w=COUNTERS.data.get("pump_nominal_w", 1100.0)
                ),
            ),
        )
    )
    if SETTINGS.cleaner_switch_entity and SETTINGS.cleaner_power_entity:
        out.append(
            (
                Channel(
                    "Limpiafondos",
                    "cleaner",
                    SETTINGS.cleaner_switch_entity,
                    SETTINGS.cleaner_power_entity,
                ),
                _PerChannelState(
                    latched=anomaly.Latched(),
                    learner=nominal_learner.LearnerState(
                        nominal_w=COUNTERS.data.get("cleaner_nominal_w", 600.0)
                    ),
                ),
            )
        )
    return out


CHANNELS = _build_channels()

_MESSAGES = {
    "overcurrent": (
        "⚠️ {label} consume {p:.0f} W (>{th:.0f} W = nominal {n:.0f} W + {m:.0f}%). "
        "Posible bloqueo del rodete o válvula cerrada."
    ),
    "dry": (
        "🚨 {label} encendida marcando solo {p:.0f} W (<{th:.0f} W = {dt:.0f}% de "
        "nominal {n:.0f} W). Probable marcha en seco. Apagar para no quemar el sello."
    ),
    "stuck": (
        "⚠️ {label} en OFF pero consume {p:.0f} W. "
        "Contactor pegado: revisar el cuadro eléctrico."
    ),
}


async def _notify(text: str) -> None:
    if SETTINGS.notify_telegram_service:
        await HA.notify(SETTINGS.notify_telegram_service, text)


async def _maybe_stop(channel: Channel, kind: anomaly.Kind) -> None:
    if SETTINGS.auto_emergency_stop and kind == "dry":
        log.warning("auto-emergency-stop on %s (%s)", channel.label, kind)
        await HA.turn_off(channel.switch_entity)


def _format_message(kind: anomaly.Kind, channel: Channel, sample: anomaly.Sample) -> str:
    if kind == "overcurrent":
        th = sample.nominal_w * (1 + sample.overcurrent_margin_pct / 100)
        return _MESSAGES["overcurrent"].format(
            label=channel.label,
            p=sample.power_w,
            th=th,
            n=sample.nominal_w,
            m=sample.overcurrent_margin_pct,
        )
    if kind == "dry":
        th = sample.nominal_w * (sample.dry_threshold_pct / 100)
        return _MESSAGES["dry"].format(
            label=channel.label,
            p=sample.power_w,
            th=th,
            dt=sample.dry_threshold_pct,
            n=sample.nominal_w,
        )
    if kind == "stuck":
        return _MESSAGES["stuck"].format(label=channel.label, p=sample.power_w)
    return ""


async def _tick_channel(channel: Channel, state: _PerChannelState) -> None:
    now = time.time()
    sw = await HA.get_state_value(channel.switch_entity)
    p = await HA.get_state_float(channel.power_entity, 0.0) or 0.0

    # 1. Update the nominal EMA.
    state.learner = nominal_learner.update(
        state.learner,
        nominal_learner.LearnerSample(switch_state=sw, power_w=p),
    )
    if channel.mqtt_key == "pump":
        COUNTERS.data["pump_nominal_w"] = state.learner.nominal_w
    else:
        COUNTERS.data["cleaner_nominal_w"] = state.learner.nominal_w
    COUNTERS.save()

    # 2. Decide.
    sample = anomaly.Sample(
        switch_state=sw,
        power_w=p,
        nominal_w=state.learner.nominal_w,
    )
    decision = anomaly.decide(sample, state.latched, now)
    state.latched = decision.latched

    # 3. React on transitions.
    if decision.just_fired:
        msg = _format_message(decision.active_kind, channel, sample)
        if msg:
            await _notify(msg)
        await _maybe_stop(channel, decision.active_kind)

    # 4. Publish entities.
    await MQTT.publish(
        "binary_sensor",
        f"{channel.mqtt_key}_anomaly",
        "ON" if decision.active_kind else "OFF",
    )
    await MQTT.publish(
        "sensor",
        f"{channel.mqtt_key}_nominal_w_learned",
        round(state.learner.nominal_w, 0),
    )


async def run_forever(interval_s: int = 10) -> None:
    log.info("pump_watch started for %d channel(s)", len(CHANNELS))
    while True:
        for channel, state in CHANNELS:
            try:
                await _tick_channel(channel, state)
            except Exception as exc:  # noqa: BLE001
                log.exception("pump_watch %s failed: %s", channel.label, exc)
        await asyncio.sleep(interval_s)


# ----- Emergency stop entry points -----------------------------------------


async def emergency_stop_pump() -> None:
    log.warning("emergency_stop_pump invoked")
    await HA.turn_off(SETTINGS.pump_switch_entity)
    await _notify("🛑 Parada de emergencia: depuradora apagada manualmente desde Pool Brain.")


async def emergency_stop_cleaner() -> None:
    log.warning("emergency_stop_cleaner invoked")
    if SETTINGS.cleaner_switch_entity:
        await HA.turn_off(SETTINGS.cleaner_switch_entity)
        await _notify("🛑 Parada de emergencia: limpiafondos apagado manualmente desde Pool Brain.")


async def emergency_stop_all() -> None:
    log.warning("emergency_stop_all invoked")
    await HA.turn_off(SETTINGS.pump_switch_entity)
    if SETTINGS.cleaner_switch_entity:
        await HA.turn_off(SETTINGS.cleaner_switch_entity)
    await _notify(
        "🛑 Parada de emergencia GENERAL desde Pool Brain — depuradora y limpiafondos apagados."
    )
