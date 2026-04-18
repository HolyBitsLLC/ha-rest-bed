"""Config flow for ReST Performance Bed."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import RestBedPump
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class RestBedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a ReST bed pump."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._discovered_id: str | None = None

    # ── Manual setup ────────────────────────────────────────────────

    async def async_step_user(
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
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    # ── Zeroconf auto-discovery ─────────────────────────────────────

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
