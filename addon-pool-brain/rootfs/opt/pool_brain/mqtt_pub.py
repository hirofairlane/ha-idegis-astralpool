"""MQTT publisher with Home Assistant auto-discovery.

Owns the connection to the Mosquitto broker that the Pool Brain add-on
declares as a dependency. On first connect it publishes the discovery
payload for every synthetic entity (sensors, binary_sensors, buttons,
numbers). Then it publishes state updates as values change.

All entities aggregate under a single HA device card named
"Idegis Pool Brain" via the `device` block.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiomqtt

from config import SETTINGS

log = logging.getLogger("pool_brain.mqtt")

DEVICE_ID = "idegis_pool_brain"
DEVICE_NAME = "Idegis Pool Brain"
DISCOVERY_PREFIX = "homeassistant"
STATE_PREFIX = "idegis_brain"


def _device_block() -> dict[str, Any]:
    return {
        "identifiers": [DEVICE_ID],
        "name": DEVICE_NAME,
        "manufacturer": "Sergio (hirofairlane)",
        "model": "Pool Brain v0.1",
        "sw_version": "0.1.0",
    }


@dataclass
class EntityDef:
    domain: str  # sensor | binary_sensor | button | number
    key: str  # unique slug; e.g. "health_score"
    name: str  # user-facing
    state_topic: str = ""
    command_topic: str = ""
    extra_config: dict[str, Any] = field(default_factory=dict)

    @property
    def object_id(self) -> str:
        return f"{STATE_PREFIX}_{self.key}"

    @property
    def unique_id(self) -> str:
        return f"{DEVICE_ID}_{self.key}"

    @property
    def discovery_topic(self) -> str:
        return f"{DISCOVERY_PREFIX}/{self.domain}/{self.object_id}/config"

    def discovery_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "unique_id": self.unique_id,
            "object_id": self.object_id,
            "device": _device_block(),
        }
        if self.state_topic:
            payload["state_topic"] = self.state_topic
        if self.command_topic:
            payload["command_topic"] = self.command_topic
        payload.update(self.extra_config)
        return payload


# ---- The full entity catalogue --------------------------------------------


def _state_topic(key: str) -> str:
    return f"{DISCOVERY_PREFIX}/sensor/{STATE_PREFIX}_{key}/state"


def _state_topic_for(domain: str, key: str) -> str:
    return f"{DISCOVERY_PREFIX}/{domain}/{STATE_PREFIX}_{key}/state"


def _cmd_topic(domain: str, key: str) -> str:
    return f"{DISCOVERY_PREFIX}/{domain}/{STATE_PREFIX}_{key}/set"


ENTITIES: list[EntityDef] = [
    # ----- Numeric sensors -----
    EntityDef(
        "sensor",
        "health_score",
        "Pool health score",
        state_topic=_state_topic_for("sensor", "health_score"),
        extra_config={
            "unit_of_measurement": "score",
            "state_class": "measurement",
            "icon": "mdi:heart-pulse",
        },
    ),
    EntityDef(
        "sensor",
        "recommended_minutes_today",
        "Recommended pump minutes today",
        state_topic=_state_topic_for("sensor", "recommended_minutes_today"),
        extra_config={
            "unit_of_measurement": "min",
            "state_class": "measurement",
            "icon": "mdi:timer-cog",
        },
    ),
    EntityDef(
        "sensor",
        "recommended_minutes_week",
        "Recommended pump minutes week",
        state_topic=_state_topic_for("sensor", "recommended_minutes_week"),
        extra_config={
            "unit_of_measurement": "min",
            "state_class": "measurement",
            "icon": "mdi:timer-cog-outline",
        },
    ),
    EntityDef(
        "sensor",
        "runtime_minutes_today",
        "Pump runtime today",
        state_topic=_state_topic_for("sensor", "runtime_minutes_today"),
        extra_config={
            "unit_of_measurement": "min",
            "state_class": "total_increasing",
            "icon": "mdi:timer-outline",
        },
    ),
    EntityDef(
        "sensor",
        "runtime_minutes_week",
        "Pump runtime week",
        state_topic=_state_topic_for("sensor", "runtime_minutes_week"),
        extra_config={
            "unit_of_measurement": "min",
            "state_class": "measurement",
            "icon": "mdi:timer-sand",
        },
    ),
    EntityDef(
        "sensor",
        "filter_kwh_today",
        "Filter kWh today",
        state_topic=_state_topic_for("sensor", "filter_kwh_today"),
        extra_config={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
            "icon": "mdi:flash",
        },
    ),
    EntityDef(
        "sensor",
        "filter_kwh_week",
        "Filter kWh week",
        state_topic=_state_topic_for("sensor", "filter_kwh_week"),
        extra_config={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "measurement",
            "icon": "mdi:flash-outline",
        },
    ),
    EntityDef(
        "sensor",
        "cleaner_kwh_today",
        "Cleaner kWh today",
        state_topic=_state_topic_for("sensor", "cleaner_kwh_today"),
        extra_config={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
            "icon": "mdi:robot-vacuum",
        },
    ),
    EntityDef(
        "sensor",
        "cleaner_kwh_week",
        "Cleaner kWh week",
        state_topic=_state_topic_for("sensor", "cleaner_kwh_week"),
        extra_config={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "measurement",
            "icon": "mdi:robot-vacuum-variant",
        },
    ),
    EntityDef(
        "sensor",
        "pump_avg_power",
        "Pump average power last session",
        state_topic=_state_topic_for("sensor", "pump_avg_power"),
        extra_config={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "icon": "mdi:engine",
        },
    ),
    EntityDef(
        "sensor",
        "turnovers_today",
        "Pool turnovers today",
        state_topic=_state_topic_for("sensor", "turnovers_today"),
        extra_config={
            "unit_of_measurement": "x",
            "state_class": "measurement",
            "icon": "mdi:recycle",
        },
    ),
    # ----- Text/diagnostic sensors -----
    EntityDef(
        "sensor",
        "ph_band",
        "pH band",
        state_topic=_state_topic_for("sensor", "ph_band"),
        extra_config={"icon": "mdi:test-tube"},
    ),
    EntityDef(
        "sensor",
        "salt_band",
        "Salt band",
        state_topic=_state_topic_for("sensor", "salt_band"),
        extra_config={"icon": "mdi:shaker-outline"},
    ),
    EntityDef(
        "sensor",
        "temperature_band",
        "Water temperature band",
        state_topic=_state_topic_for("sensor", "temperature_band"),
        extra_config={"icon": "mdi:thermometer-water"},
    ),
    EntityDef(
        "sensor",
        "production_band",
        "Chlorine production band",
        state_topic=_state_topic_for("sensor", "production_band"),
        extra_config={"icon": "mdi:flask"},
    ),
    # ----- Binary sensors -----
    EntityDef(
        "binary_sensor",
        "water_healthy",
        "Water healthy",
        state_topic=_state_topic_for("binary_sensor", "water_healthy"),
        extra_config={
            "device_class": "safety",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:water-check",
        },
    ),
    EntityDef(
        "binary_sensor",
        "pump_anomaly",
        "Pump anomaly",
        state_topic=_state_topic_for("binary_sensor", "pump_anomaly"),
        extra_config={
            "device_class": "problem",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:engine-off",
        },
    ),
    EntityDef(
        "binary_sensor",
        "cleaner_anomaly",
        "Cleaner anomaly",
        state_topic=_state_topic_for("binary_sensor", "cleaner_anomaly"),
        extra_config={
            "device_class": "problem",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:robot-vacuum-alert",
        },
    ),
    EntityDef(
        "binary_sensor",
        "first_minutes_window",
        "First minutes window (data unreliable)",
        state_topic=_state_topic_for("binary_sensor", "first_minutes_window"),
        extra_config={
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:clock-alert-outline",
        },
    ),
    # ----- Buttons -----
    EntityDef(
        "button",
        "emergency_stop_all",
        "Emergency stop ALL pumps",
        command_topic=_cmd_topic("button", "emergency_stop_all"),
        extra_config={
            "payload_press": "PRESS",
            "icon": "mdi:alert-octagon",
        },
    ),
    EntityDef(
        "button",
        "emergency_stop_pump",
        "Emergency stop filter pump",
        command_topic=_cmd_topic("button", "emergency_stop_pump"),
        extra_config={
            "payload_press": "PRESS",
            "icon": "mdi:engine-off",
        },
    ),
    EntityDef(
        "button",
        "emergency_stop_cleaner",
        "Emergency stop cleaner",
        command_topic=_cmd_topic("button", "emergency_stop_cleaner"),
        extra_config={
            "payload_press": "PRESS",
            "icon": "mdi:robot-vacuum-off",
        },
    ),
    EntityDef(
        "button",
        "run_weekly_report_now",
        "Send weekly report now",
        command_topic=_cmd_topic("button", "run_weekly_report_now"),
        extra_config={
            "payload_press": "PRESS",
            "icon": "mdi:email-send",
        },
    ),
]


# ----- Client ----------------------------------------------------------------


class MqttPublisher:
    """Holds a persistent connection and re-publishes discovery on reconnect.

    Command topics route to handler callbacks set with `on_command`.
    """

    def __init__(self) -> None:
        self._client: aiomqtt.Client | None = None
        self._state: dict[str, str] = {}
        self._handlers: dict[str, Any] = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def on_command(self, key: str, handler):
        self._handlers[key] = handler

    async def start(self) -> None:
        if not SETTINGS.mqtt_host:
            log.error("MQTT_HOST not set; pool_brain cannot publish entities")
            return
        self._task = asyncio.create_task(self._runner())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _runner(self) -> None:
        while not self._stop.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=SETTINGS.mqtt_host,
                    port=SETTINGS.mqtt_port,
                    username=SETTINGS.mqtt_username or None,
                    password=SETTINGS.mqtt_password or None,
                    identifier="idegis-pool-brain",
                ) as client:
                    self._client = client
                    log.info(
                        "MQTT connected %s:%s",
                        SETTINGS.mqtt_host,
                        SETTINGS.mqtt_port,
                    )
                    await self._publish_discovery()
                    await self._republish_cached_state()
                    await self._subscribe_commands()
                    async for message in client.messages:
                        await self._handle_message(message)
            except aiomqtt.MqttError as exc:
                log.warning("MQTT disconnect: %s; retrying in 5 s", exc)
                self._client = None
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
            except Exception as exc:  # noqa: BLE001
                log.exception("MQTT runner crashed: %s", exc)
                await asyncio.sleep(5)

    async def _publish_discovery(self) -> None:
        assert self._client is not None
        for ent in ENTITIES:
            payload = json.dumps(ent.discovery_payload())
            await self._client.publish(ent.discovery_topic, payload, retain=True)
        log.info("discovery published for %d entities", len(ENTITIES))

    async def _republish_cached_state(self) -> None:
        assert self._client is not None
        for topic, value in self._state.items():
            await self._client.publish(topic, value, retain=True)

    async def _subscribe_commands(self) -> None:
        assert self._client is not None
        for ent in ENTITIES:
            if ent.command_topic:
                await self._client.subscribe(ent.command_topic, qos=1)

    async def _handle_message(self, msg) -> None:
        topic = str(msg.topic)
        for ent in ENTITIES:
            if ent.command_topic == topic:
                handler = self._handlers.get(ent.key)
                if handler is None:
                    log.debug("no handler for %s", ent.key)
                    return
                try:
                    await handler()
                except Exception as exc:  # noqa: BLE001
                    log.exception("handler %s failed: %s", ent.key, exc)
                return

    # ------ public publish ------------------------------------------------

    async def publish(self, domain: str, key: str, value: Any) -> None:
        topic = _state_topic_for(domain, key)
        payload = str(value) if not isinstance(value, str) else value
        self._state[topic] = payload
        if self._client is None:
            return
        try:
            await self._client.publish(topic, payload, retain=True)
        except aiomqtt.MqttError as exc:
            log.warning("publish %s failed: %s", topic, exc)


MQTT = MqttPublisher()
