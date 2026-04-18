"""ReST Performance Bed integration for Home Assistant."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RestBedPump
from .coordinator import RestBedCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type RestBedConfigEntry = ConfigEntry[RestBedCoordinator]

SERVICE_SET_WIFI = "set_wifi"
SERVICE_SET_WIFI_SCHEMA = vol.Schema(
    {
        vol.Required("ssid"): cv.string,
        vol.Required("password"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    session = async_get_clientsession(hass)
    pump = RestBedPump(entry.data[CONF_HOST], session)
    coordinator = RestBedCoordinator(hass, pump)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register per-entry set_wifi service (once globally)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_WIFI):

        async def handle_set_wifi(call: ServiceCall) -> None:
            ssid = call.data["ssid"]
            password = call.data["password"]
            for ent in hass.config_entries.async_entries(DOMAIN):
                coord: RestBedCoordinator = ent.runtime_data
                _LOGGER.info(
                    "Setting WiFi on pump %s to SSID '%s'",
                    coord.pump.host,
                    ssid,
                )
                try:
                    await coord.pump.set_wifi(ssid, password)
                except Exception:
                    _LOGGER.exception(
                        "Failed to set WiFi on pump %s", coord.pump.host
                    )

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_WIFI,
            handle_set_wifi,
            schema=SERVICE_SET_WIFI_SCHEMA,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    await entry.runtime_data.async_shutdown()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Unregister service if no entries remain
    if unloaded and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_WIFI)
    return unloaded
