"""Client for the companion idegis_capturer add-on.

Reads the JSON snapshot exposed at /api/idegis/state from the capturer
running on the same HA host. All measurements, session aggregates and
pump_running flag come from here.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from config import SETTINGS

log = logging.getLogger("pool_brain.capturer")


class CapturerClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._last_snapshot: dict[str, Any] = {}
        self._last_error: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_state(self) -> dict[str, Any]:
        """Fetch and cache the full state from the capturer.

        On failure, returns the last successful snapshot (possibly empty).
        Callers should also check `is_fresh` if they care about staleness.
        """
        try:
            session = await self._get_session()
            async with asyncio.timeout(5):
                async with session.get(
                    f"{SETTINGS.capturer_base_url}/api/idegis/state"
                ) as resp:
                    if resp.status == 200:
                        self._last_snapshot = await resp.json()
                        self._last_error = None
                        return self._last_snapshot
                    self._last_error = f"HTTP {resp.status}"
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
        log.debug("capturer fetch failed: %s", self._last_error)
        return self._last_snapshot

    @property
    def last_snapshot(self) -> dict[str, Any]:
        return self._last_snapshot

    @property
    def last_error(self) -> str | None:
        return self._last_error


CAPTURER = CapturerClient()
