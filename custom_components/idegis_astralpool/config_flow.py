"""Config flow for the Idegis / AstralPool integration."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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


async def _probe_capturer(hass, host: str, port: int) -> dict[str, Any] | None:
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}:{port}/api/idegis/health", timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return None


class IdegisConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Mode picker. For now we only show cloud-MITM."""
        return await self.async_step_cloud_mitm()

    async def async_step_cloud_mitm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            health = await _probe_capturer(self.hass, host, port)
            if health is None:
                errors["base"] = "capturer_unreachable"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Idegis capturer @ {host}",
                    data={
                        CONF_MODE: MODE_CLOUD_MITM,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )

        return self.async_show_form(
            step_id="cloud_mitm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_MITM_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_MITM_PORT): int,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_S
                    ): int,
                }
            ),
            errors=errors,
        )
