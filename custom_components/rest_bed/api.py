"""Async API client for ReST Performance Bed pumps."""

import asyncio
import json
import logging
from typing import Any, Callable

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RestBedPump:
    """Client for a single ReST bed pump."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        self._base = f"http://{host}"

    @property
    def host(self) -> str:
        return self._host

    async def _get(self, path: str) -> Any:
        async with self._session.get(
            f"{self._base}{path}",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _put(self, path: str, data: Any) -> None:
        async with self._session.put(
            f"{self._base}{path}",
            json=data,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()

    # ── GET endpoints ───────────────────────────────────────────────

    async def get_device(self) -> dict:
        return await self._get("/api/device")

    async def get_preferences(self) -> dict:
        return await self._get("/api/preferences")

    async def get_body(self) -> dict:
        return await self._get("/api/body")

    async def get_air(self) -> dict:
        return await self._get("/api/air")

    async def get_temperature(self) -> dict:
        return await self._get("/api/temperature")

    async def get_firmware_version(self) -> str:
        return await self._get("/api/firmware/version")

    async def get_wifi(self) -> dict:
        return await self._get("/api/wifi")

    # ── PUT endpoints ───────────────────────────────────────────────

    async def set_mode(self, mode: str) -> None:
        await self._put("/api/preferences/mode", mode)

    async def set_firmness(self, value: int) -> None:
        await self._put("/api/preferences/firmness", value)

    async def set_distortion(self, value: int) -> None:
        await self._put("/api/preferences/distortion", value)

    async def set_quiet(self, value: bool) -> None:
        await self._put("/api/preferences/quiet", value)

    async def set_tolerance(self, value: int) -> None:
        await self._put("/api/preferences/tolerance", value)

    async def set_sensitivity(self, value: int) -> None:
        await self._put("/api/preferences/sensitivity", value)

    async def set_manual_profile(self, values: list[int]) -> None:
        await self._put("/api/preferences/manualprofile", values)

    async def set_back_profile(self, values: list[int]) -> None:
        await self._put("/api/preferences/backprofile", values)

    async def set_side_profile(self, values: list[int]) -> None:
        await self._put("/api/preferences/sideprofile", values)

    # ── SSE stream ──────────────────────────────────────────────────

    async def listen_sse(
        self,
        callback: Callable[[str, Any], None],
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Connect to the pump SSE stream and invoke *callback(event_type, data)*."""
        timeout = aiohttp.ClientTimeout(total=0, connect=10, sock_read=30)
        async with self._session.get(
            f"{self._base}/api/sse", timeout=timeout
        ) as resp:
            resp.raise_for_status()
            event_type: str | None = None
            while True:
                if stop_event and stop_event.is_set():
                    break
                line_bytes = await resp.content.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n\r")
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: ") and event_type:
                    raw = line[6:]
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = raw.strip('"')
                    callback(event_type, data)
                    event_type = None
                elif line == "":
                    event_type = None
