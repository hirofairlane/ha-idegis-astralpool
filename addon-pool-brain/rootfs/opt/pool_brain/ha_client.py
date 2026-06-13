"""Home Assistant Core API client via Supervisor.

Reads entity states, calls services, and forwards notifications. No
state of its own. Failures are logged and swallowed — the brain keeps
running on the latest snapshot it has.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from config import SETTINGS

log = logging.getLogger("pool_brain.ha")


class HAClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._headers = {
            "Authorization": f"Bearer {SETTINGS.supervisor_token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # -------- States ------------------------------------------------------

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        if not entity_id:
            return None
        try:
            session = await self._get_session()
            async with asyncio.timeout(5):
                async with session.get(
                    f"{SETTINGS.hass_api}/states/{entity_id}"
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    log.debug("get_state(%s) HTTP %s", entity_id, resp.status)
                    return None
        except Exception as exc:  # noqa: BLE001
            log.warning("get_state(%s) failed: %s", entity_id, exc)
            return None

    async def get_state_value(self, entity_id: str) -> str | None:
        st = await self.get_state(entity_id)
        if st is None:
            return None
        return st.get("state")

    async def get_state_float(
        self, entity_id: str, default: float | None = None
    ) -> float | None:
        v = await self.get_state_value(entity_id)
        if v in (None, "unknown", "unavailable", "NA"):
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # -------- Services ----------------------------------------------------

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        try:
            session = await self._get_session()
            async with asyncio.timeout(8):
                async with session.post(
                    f"{SETTINGS.hass_api}/services/{domain}/{service}",
                    json=data or {},
                ) as resp:
                    ok = resp.status in (200, 201)
                    if not ok:
                        log.warning(
                            "call_service(%s.%s) HTTP %s",
                            domain,
                            service,
                            resp.status,
                        )
                    return ok
        except Exception as exc:  # noqa: BLE001
            log.warning("call_service(%s.%s) failed: %s", domain, service, exc)
            return False

    async def turn_off(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        domain = entity_id.split(".", 1)[0]
        return await self.call_service(
            domain, "turn_off", {"entity_id": entity_id}
        )

    async def turn_on(
        self, entity_id: str, extras: dict[str, Any] | None = None
    ) -> bool:
        if not entity_id:
            return False
        domain = entity_id.split(".", 1)[0]
        data = {"entity_id": entity_id, **(extras or {})}
        return await self.call_service(domain, "turn_on", data)

    async def notify(
        self,
        service_full: str,
        message: str,
        title: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> bool:
        # service_full looks like 'notify.telegram_bot_xxx'
        if not service_full or not service_full.startswith("notify."):
            return False
        service = service_full.split(".", 1)[1]
        payload: dict[str, Any] = {"message": message}
        if title:
            payload["title"] = title
        if data:
            payload["data"] = data
        return await self.call_service("notify", service, payload)


# Module-level singleton for convenience
HA = HAClient()
