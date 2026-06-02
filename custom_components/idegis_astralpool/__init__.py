"""Idegis / AstralPool pool chlorinator integration.

Currently supports only the cloud-MITM capture mode (path A). Modbus RTU
(path B) and Poolstation cloud (path C) are placeholders for future
releases — see docs/09-roadmap.md in the repository.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_MITM_HOST,
    DEFAULT_MITM_PORT,
    DEFAULT_SCAN_INTERVAL_S,
    DOMAIN,
    MODE_CLOUD_MITM,
)
from .coordinator import IdegisCloudMitmCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Idegis from a config entry."""
    mode = entry.data.get(CONF_MODE, MODE_CLOUD_MITM)

    if mode != MODE_CLOUD_MITM:
        _LOGGER.error("mode %s is not implemented yet", mode)
        return False

    host = entry.data.get(CONF_HOST, DEFAULT_MITM_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_MITM_PORT)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_S),
    )

    coordinator = IdegisCloudMitmCoordinator(
        hass, host=host, port=port, scan_interval_s=scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: IdegisCloudMitmCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
