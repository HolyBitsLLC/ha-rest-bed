"""Config flow for ReST Performance Bed."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RestBedPump
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class RestBedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a ReST bed pump."""

    VERSION = 1

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
