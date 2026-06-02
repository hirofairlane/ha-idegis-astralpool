"""Sensor platform — surfaces what we already have from path A capture."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_DEFAULT
from .coordinator import IdegisCloudMitmCoordinator


@dataclass(frozen=True, kw_only=True)
class IdegisSensorDescription(SensorEntityDescription):
    """Sensor description with an extractor function over the coordinator data."""
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[IdegisSensorDescription, ...] = (
    IdegisSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        name="Last seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.get("last_seen"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="age_seconds",
        translation_key="age_seconds",
        name="Seconds since last request",
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("age_seconds"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="polling_rate",
        translation_key="polling_rate",
        name="Polling rate",
        native_unit_of_measurement="req/min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("polling_rate_per_min_5m"),
    ),
    IdegisSensorDescription(
        key="requests_total",
        translation_key="requests_total",
        name="Captured requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("requests_total"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="read_count",
        translation_key="read_count",
        name="Read.php calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("read_count"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="write_count",
        translation_key="write_count",
        name="Write.php calls",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("write_count"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="last_endpoint",
        translation_key="last_endpoint",
        name="Last endpoint",
        value_fn=lambda d: d.get("last_endpoint"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="last_upstream_time",
        translation_key="last_upstream_time",
        name="Last cloud upstream time",
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("last_upstream_time_s"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Raw B0 fields exposed verbatim until we decode them
    IdegisSensorDescription(
        key="li_raw",
        translation_key="li_raw",
        name="LI field raw",
        value_fn=lambda d: (d.get("last_fields") or {}).get("LI"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="cd_raw",
        translation_key="cd_raw",
        name="CD field raw",
        value_fn=lambda d: (d.get("last_fields") or {}).get("CD"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="sg_raw",
        translation_key="sg_raw",
        name="SG field raw",
        value_fn=lambda d: (d.get("last_fields") or {}).get("SG"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    IdegisSensorDescription(
        key="cy_raw",
        translation_key="cy_raw",
        name="CY field raw",
        value_fn=lambda d: (d.get("last_fields") or {}).get("CY"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IdegisCloudMitmCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IdegisSensor(coordinator, desc, entry.entry_id) for desc in SENSORS
    )


class IdegisSensor(CoordinatorEntity[IdegisCloudMitmCoordinator], SensorEntity):
    entity_description: IdegisSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IdegisCloudMitmCoordinator,
        description: IdegisSensorDescription,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, data.get("device_id") or self.coordinator.host)},
            manufacturer=MANUFACTURER,
            model=MODEL_DEFAULT,
            name="Idegis chlorinator",
            configuration_url=f"http://{self.coordinator.host}:{self.coordinator.port}/api/idegis/state",
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
