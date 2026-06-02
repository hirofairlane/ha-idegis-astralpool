"""DataUpdateCoordinator for the Idegis cloud-MITM capturer.

For now only the cloud-MITM mode is implemented. It talks to the small
FastAPI service that runs alongside the nginx reverse proxy on the host
that intercepts api.idegis.net traffic.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_S

_LOGGER = logging.getLogger(__name__)


class IdegisCloudMitmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the local idegis-state capturer for the latest snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        scan_interval_s: int = DEFAULT_SCAN_INTERVAL_S,
    ) -> None:
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"
        self._session = aiohttp.ClientSession()
        super().__init__(
            hass,
            _LOGGER,
            name="idegis_astralpool_cloud_mitm",
            update_interval=timedelta(seconds=scan_interval_s),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(5):
                async with self._session.get(
                    f"{self._base_url}/api/idegis/state"
                ) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status}")
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"capturer unreachable: {err}") from err

    async def async_shutdown(self) -> None:
        await self._session.close()
        await super().async_shutdown()
