"""Pump/cleaner anomaly watchdog.

Three families of anomaly per channel:

- **Overcurrent**: power > nominal * (1 + margin) for >30 s. Indicates the
  motor is fighting against something (closed valve, blocked impeller).
- **Dry running**: switch.state == on AND power < nominal * 0.2 for >60 s.
  Indicates the motor is spinning without water — burns the seal.
- **Stuck contactor**: switch.state == off AND power > 5 W for >60 s.
  Indicates the relay is welded closed; the user has to flip the breaker.

When an anomaly is detected the watchdog (a) raises
`binary_sensor.idegis_brain_<channel>_anomaly`, (b) fires a Telegram
notification, and (c) — if `auto_emergency_stop` is enabled — calls
`switch.turn_off` on the affected entity.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from config import SETTINGS
from ha_client import HA
from mqtt_pub import MQTT

log = logging.getLogger("pool_brain.pump_watch")

NOMINAL_PUMP_W = 1100.0  # baseline; learned in v2
NOMINAL_CLEANER_W = 600.0
OVERCURRENT_MARGIN_PCT = 20  # default; option later
DRY_RUNNING_THRESHOLD_PCT = 20
STUCK_W_THRESHOLD = 5


@dataclass
class Channel:
    label: str
    switch_entity: str
    power_entity: str
    nominal_w: float


@dataclass
class _State:
    overcurrent_since: float = 0.0
    dry_since: float = 0.0
    stuck_since: float = 0.0
    anomaly_on: bool = False
    last_notified_kind: str = ""


def _build_channels() -> list[tuple[Channel, _State]]:
    channels: list[tuple[Channel, _State]] = []
    channels.append(
        (
            Channel(
                "Depuradora",
                SETTINGS.pump_switch_entity,
                SETTINGS.pump_power_entity,
                NOMINAL_PUMP_W,
            ),
            _State(),
        )
    )
    if SETTINGS.cleaner_switch_entity and SETTINGS.cleaner_power_entity:
        channels.append(
            (
                Channel(
                    "Limpiafondos",
                    SETTINGS.cleaner_switch_entity,
                    SETTINGS.cleaner_power_entity,
                    NOMINAL_CLEANER_W,
                ),
                _State(),
            )
        )
    return channels


CHANNELS = _build_channels()


async def _notify(text: str) -> None:
    if SETTINGS.notify_telegram_service:
        await HA.notify(SETTINGS.notify_telegram_service, text)


async def _maybe_stop(channel: Channel, kind: str) -> None:
    if SETTINGS.auto_emergency_stop and kind == "dry":
        log.warning("auto-emergency-stop on %s (%s)", channel.label, kind)
        await HA.turn_off(channel.switch_entity)


async def _tick_channel(channel: Channel, state: _State) -> None:
    now = time.time()
    sw = await HA.get_state_value(channel.switch_entity)
    p = await HA.get_state_float(channel.power_entity, 0.0) or 0.0

    overcurrent = p > channel.nominal_w * (1 + OVERCURRENT_MARGIN_PCT / 100)
    dry = sw == "on" and p < channel.nominal_w * (DRY_RUNNING_THRESHOLD_PCT / 100)
    stuck = sw == "off" and p > STUCK_W_THRESHOLD

    state.overcurrent_since = (
        now if (overcurrent and state.overcurrent_since == 0) else
        0 if not overcurrent else state.overcurrent_since
    )
    state.dry_since = (
        now if (dry and state.dry_since == 0) else
        0 if not dry else state.dry_since
    )
    state.stuck_since = (
        now if (stuck and state.stuck_since == 0) else
        0 if not stuck else state.stuck_since
    )

    over_lasting = state.overcurrent_since and (now - state.overcurrent_since) > 30
    dry_lasting = state.dry_since and (now - state.dry_since) > 60
    stuck_lasting = state.stuck_since and (now - state.stuck_since) > 60

    fired = ""
    if over_lasting:
        fired = "overcurrent"
    elif dry_lasting:
        fired = "dry"
    elif stuck_lasting:
        fired = "stuck"

    if fired:
        if not state.anomaly_on or state.last_notified_kind != fired:
            messages = {
                "overcurrent": (
                    f"⚠️ {channel.label} consume {p:.0f} W "
                    f"(>{channel.nominal_w:.0f} W nominal +{OVERCURRENT_MARGIN_PCT}%). "
                    "Posible bloqueo del rodete o válvula cerrada."
                ),
                "dry": (
                    f"🚨 {channel.label} encendida marcando solo {p:.0f} W "
                    f"(<{channel.nominal_w * DRY_RUNNING_THRESHOLD_PCT / 100:.0f} W). "
                    "Probable marcha en seco. Apagar para no quemar el sello."
                ),
                "stuck": (
                    f"⚠️ {channel.label} en OFF pero consume {p:.0f} W. "
                    "Contactor pegado: revisar el cuadro eléctrico."
                ),
            }
            await _notify(messages[fired])
            await _maybe_stop(channel, fired)
            state.last_notified_kind = fired
        state.anomaly_on = True
    else:
        if state.anomaly_on:
            state.last_notified_kind = ""
        state.anomaly_on = False

    if channel.label == "Depuradora":
        await MQTT.publish(
            "binary_sensor",
            "pump_anomaly",
            "ON" if state.anomaly_on else "OFF",
        )
    else:
        await MQTT.publish(
            "binary_sensor",
            "cleaner_anomaly",
            "ON" if state.anomaly_on else "OFF",
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


# ----- Emergency stop entry points (called from MQTT button handlers) ------


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
