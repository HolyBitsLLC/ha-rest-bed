"""DataUpdateCoordinator backed by pump SSE stream."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import RestBedPump

_LOGGER = logging.getLogger(__name__)

SSE_RECONNECT_DELAY = 5
POLL_INTERVAL = timedelta(seconds=60)


class RestBedCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that keeps pump state up-to-date via SSE with REST fallback."""

    def __init__(self, hass: HomeAssistant, pump: RestBedPump) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"ReST Bed ({pump.host})",
            update_interval=POLL_INTERVAL,
        )
        self.pump = pump
        self._sse_task: asyncio.Task | None = None
        self._sse_stop = asyncio.Event()
        self.device_info_data: dict[str, Any] = {}

    # ── lifecycle ───────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Fetch initial state and start SSE listener."""
        await self._full_poll()
        self._start_sse()

    async def async_shutdown(self) -> None:
        self._sse_stop.set()
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except (asyncio.CancelledError, Exception):
                pass
        await super().async_shutdown()

    # ── REST polling ────────────────────────────────────────────────

    async def _full_poll(self) -> None:
        try:
            device = await self.pump.get_device()
            preferences = await self.pump.get_preferences()
            body = await self.pump.get_body()
            air = await self.pump.get_air()
            temperature = await self.pump.get_temperature()
            firmware = await self.pump.get_firmware_version()
        except Exception as err:
            raise UpdateFailed(f"Failed to poll pump: {err}") from err

        self.device_info_data = device
        self.async_set_updated_data(
            {
                "device": device,
                "preferences": preferences,
                "body": body,
                "air": air,
                "temperature": temperature,
                "firmware": firmware,
            }
        )

    async def _async_update_data(self) -> dict[str, Any]:
        await self._full_poll()
        return self.data

    # ── SSE stream ──────────────────────────────────────────────────

    def _start_sse(self) -> None:
        self._sse_stop.clear()
        self._sse_task = self.hass.async_create_background_task(
            self._sse_loop(), f"rest_bed_sse_{self.pump.host}"
        )

    async def _sse_loop(self) -> None:
        while not self._sse_stop.is_set():
            try:
                _LOGGER.debug("Connecting SSE to %s", self.pump.host)
                await self.pump.listen_sse(self._on_sse_event, self._sse_stop)
            except Exception:
                if self._sse_stop.is_set():
                    return
                _LOGGER.debug(
                    "SSE disconnected from %s, reconnecting in %ss",
                    self.pump.host,
                    SSE_RECONNECT_DELAY,
                )
            try:
                await asyncio.wait_for(
                    self._sse_stop.wait(), timeout=SSE_RECONNECT_DELAY
                )
                return
            except asyncio.TimeoutError:
                pass

    @callback
    def _on_sse_event(self, event_type: str, data: Any) -> None:
        if self.data is None:
            return
        if event_type in (
            "device",
            "preferences",
            "body",
            "air",
            "temperature",
        ):
            if event_type == "device":
                self.device_info_data = data
            self.async_set_updated_data({**self.data, event_type: data})
