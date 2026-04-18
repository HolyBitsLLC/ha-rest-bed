"""Config flow for ReST Performance Bed."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import RestBedPump
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

# Timeout per pump when scanning (seconds)
_SCAN_TIMEOUT = 4


class RestBedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a ReST bed pump."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._discovered_id: str | None = None
        self._discovered_pumps: list[dict[str, str]] = []

    # ── helpers ─────────────────────────────────────────────────────

    async def _probe_pump(self, host: str) -> dict[str, str] | None:
        """Try to reach a pump and return its device info, or None."""
        session = async_get_clientsession(self.hass)
        pump = RestBedPump(host, session)
        try:
            device = await pump.get_device()
            if device.get("class") == "ReST Bed":
                return {
                    "host": host,
                    "id": device["id"],
                    "name": device.get("name", f"ReST Bed {device['id']}"),
                }
        except Exception:
            pass
        return None

    def _already_configured(self, pump_id: str) -> bool:
        """Check whether a pump_id already has a config entry."""
        for entry in self._async_current_entries():
            if entry.unique_id == pump_id:
                return True
        return False

    # ── User-initiated setup ────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show discovered pumps or hand off to manual entry."""
        if user_input is not None:
            # User picked a discovered pump or chose manual
            chosen = user_input.get("pump")
            if chosen == "__manual__":
                return await self.async_step_manual()

            # Find the picked pump in our scan results
            for pump in self._discovered_pumps:
                if pump["id"] == chosen:
                    await self.async_set_unique_id(pump["id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=pump["name"],
                        data={CONF_HOST: pump["host"]},
                    )
            # Shouldn't happen, fall through to manual
            return await self.async_step_manual()

        # ── Scan the network for pumps via zeroconf ─────────────────
        self._discovered_pumps = await self._scan_for_pumps()

        # Filter already-configured pumps
        new_pumps = [
            p for p in self._discovered_pumps if not self._already_configured(p["id"])
        ]

        if not new_pumps:
            # Nothing discovered, go straight to manual entry
            return await self.async_step_manual()

        # Build a selection menu with discovered pumps + manual option
        options = {p["id"]: f"{p['name']} ({p['host']})" for p in new_pumps}
        options["__manual__"] = "Enter host manually…"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("pump"): vol.In(options)}
            ),
        )

    async def _scan_for_pumps(self) -> list[dict[str, str]]:
        """Discover ReST bed pumps via the zeroconf cache."""
        from homeassistant.components.zeroconf import async_get_instance

        try:
            zc = await async_get_instance(self.hass)
        except Exception:
            return []

        from zeroconf import ServiceBrowser

        found_hosts: set[str] = set()
        discovered: asyncio.Queue[str] = asyncio.Queue()

        class _Listener:
            def add_service(self, zc_inst, svc_type, name):  # noqa: N802
                info = zc_inst.get_service_info(svc_type, name)
                if info and info.parsed_addresses():
                    addr = info.parsed_addresses()[0]
                    if addr not in found_hosts:
                        found_hosts.add(addr)
                        discovered.put_nowait(addr)

            def remove_service(self, *args, **kwargs):
                pass

            def update_service(self, *args, **kwargs):
                pass

        browser = ServiceBrowser(zc, "_http._tcp.local.", _Listener())

        # Collect for up to 3 seconds
        await asyncio.sleep(3)
        browser.cancel()

        # Probe each discovered host in parallel
        hosts = []
        while not discovered.empty():
            hosts.append(discovered.get_nowait())

        tasks = [self._probe_pump(h) for h in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    # ── Manual host entry ───────────────────────────────────────────

    async def async_step_manual(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            pump = RestBedPump(host, session)
            try:
                device = await pump.get_device()
            except Exception:
                _LOGGER.exception("Cannot connect to pump at %s", host)
                errors["base"] = "cannot_connect"
            else:
                pump_id: str = device["id"]
                await self.async_set_unique_id(pump_id)
                self._abort_if_unique_id_configured()
                name = device.get("name", f"ReST Bed {pump_id}")
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    # ── Zeroconf auto-discovery (passive) ───────────────────────────

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        host = str(discovery_info.ip_address)
        session = async_get_clientsession(self.hass)
        pump = RestBedPump(host, session)
        try:
            device = await pump.get_device()
        except Exception:
            return self.async_abort(reason="cannot_connect")

        if device.get("class") != "ReST Bed":
            return self.async_abort(reason="not_rest_bed")

        pump_id: str = device["id"]
        await self.async_set_unique_id(pump_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_name = device.get("name", f"ReST Bed {pump_id}")
        self._discovered_id = pump_id

        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name or "ReST Bed",
                data={CONF_HOST: self._discovered_host},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._discovered_name},
        )
