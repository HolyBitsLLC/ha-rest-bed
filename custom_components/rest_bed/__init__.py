"""ReST Performance Bed integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RestBedPump
from .coordinator import RestBedCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type RestBedConfigEntry = ConfigEntry[RestBedCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    session = async_get_clientsession(hass)
    pump = RestBedPump(entry.data[CONF_HOST], session)
    coordinator = RestBedCoordinator(hass, pump)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
