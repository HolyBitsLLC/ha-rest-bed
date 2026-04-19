"""ReST Performance Bed integration for Home Assistant."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import RestBedPump
from .coordinator import RestBedCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
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

SERVICE_SAVE_PRESET = "save_preset"
SERVICE_RESTORE_PRESET = "restore_preset"
SERVICE_DELETE_PRESET = "delete_preset"

SERVICE_START_CALIBRATION = "start_calibration"
SERVICE_CANCEL_CALIBRATION = "cancel_calibration"
SERVICE_ADVANCE_CALIBRATION = "advance_calibration"

SERVICE_PRESET_NAME_SCHEMA = vol.Schema(
    {vol.Required("name"): cv.string}
)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.presets"

PREF_KEYS = (
    "mode", "firmness", "distortion", "tolerance", "sensitivity",
    "quiet", "manualprofile", "backprofile", "sideprofile",
)


async def _apply_prefs(coord: RestBedCoordinator, prefs: dict) -> None:
    """Send saved preference values to a pump."""
    p = coord.pump
    if "mode" in prefs:
        await p.set_mode(prefs["mode"])
    if "firmness" in prefs:
        await p.set_firmness(prefs["firmness"])
    if "distortion" in prefs:
        await p.set_distortion(prefs["distortion"])
    if "tolerance" in prefs:
        await p.set_tolerance(prefs["tolerance"])
    if "sensitivity" in prefs:
        await p.set_sensitivity(prefs["sensitivity"])
    if "quiet" in prefs:
        await p.set_quiet(prefs["quiet"])
    if "manualprofile" in prefs:
        await p.set_manual_profile(prefs["manualprofile"])
    if "backprofile" in prefs:
        await p.set_back_profile(prefs["backprofile"])
    if "sideprofile" in prefs:
        await p.set_side_profile(prefs["sideprofile"])


async def async_setup_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    session = async_get_clientsession(hass)
    pump = RestBedPump(entry.data[CONF_HOST], session)
    coordinator = RestBedCoordinator(hass, pump)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Initialize shared domain data once (preset storage, etc.)
    if DOMAIN not in hass.data:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        hass.data[DOMAIN] = {
            "store": store,
            "presets": await store.async_load() or {},
        }

    # Register domain services (once globally)
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

        async def handle_save_preset(call: ServiceCall) -> None:
            name = call.data["name"]
            domain_data = hass.data[DOMAIN]
            snapshot: dict[str, dict] = {}
            for ent in hass.config_entries.async_entries(DOMAIN):
                coord: RestBedCoordinator = ent.runtime_data
                prefs = coord.data.get("preferences", {})
                pump_id = coord.device_info_data["id"]
                snapshot[pump_id] = {
                    k: prefs[k] for k in PREF_KEYS if k in prefs
                }
            domain_data["presets"][name] = snapshot
            await domain_data["store"].async_save(domain_data["presets"])
            _LOGGER.info(
                "Saved preset '%s' for %d pump(s)", name, len(snapshot)
            )

        async def handle_restore_preset(call: ServiceCall) -> None:
            name = call.data["name"]
            domain_data = hass.data[DOMAIN]
            presets = domain_data["presets"]
            if name not in presets:
                _LOGGER.error("Preset '%s' not found", name)
                return
            snapshot = presets[name]
            for ent in hass.config_entries.async_entries(DOMAIN):
                coord: RestBedCoordinator = ent.runtime_data
                pump_id = coord.device_info_data["id"]
                saved = snapshot.get(pump_id)
                if not saved:
                    continue
                await _apply_prefs(coord, saved)
                coord.data.get("preferences", {}).update(saved)
                coord.async_set_updated_data(coord.data)
                _LOGGER.info(
                    "Restored preset '%s' on pump %s", name, pump_id
                )

        async def handle_delete_preset(call: ServiceCall) -> None:
            name = call.data["name"]
            domain_data = hass.data[DOMAIN]
            if name in domain_data["presets"]:
                del domain_data["presets"][name]
                await domain_data["store"].async_save(
                    domain_data["presets"]
                )
                _LOGGER.info("Deleted preset '%s'", name)
            else:
                _LOGGER.warning("Preset '%s' not found", name)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SAVE_PRESET,
            handle_save_preset,
            schema=SERVICE_PRESET_NAME_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESTORE_PRESET,
            handle_restore_preset,
            schema=SERVICE_PRESET_NAME_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_PRESET,
            handle_delete_preset,
            schema=SERVICE_PRESET_NAME_SCHEMA,
        )

        async def _get_first_coordinator() -> RestBedCoordinator:
            entries = hass.config_entries.async_entries(DOMAIN)
            return entries[0].runtime_data

        async def handle_start_calibration(call: ServiceCall) -> None:
            coord = await _get_first_coordinator()
            await coord.calibration.start()

        async def handle_cancel_calibration(call: ServiceCall) -> None:
            coord = await _get_first_coordinator()
            await coord.calibration.cancel()

        async def handle_advance_calibration(call: ServiceCall) -> None:
            coord = await _get_first_coordinator()
            await coord.calibration.advance()

        hass.services.async_register(
            DOMAIN, SERVICE_START_CALIBRATION, handle_start_calibration,
        )
        hass.services.async_register(
            DOMAIN, SERVICE_CANCEL_CALIBRATION, handle_cancel_calibration,
        )
        hass.services.async_register(
            DOMAIN, SERVICE_ADVANCE_CALIBRATION, handle_advance_calibration,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RestBedConfigEntry
) -> bool:
    await entry.runtime_data.async_shutdown()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Unregister services and clean up domain data if no entries remain
    if unloaded and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_WIFI)
        hass.services.async_remove(DOMAIN, SERVICE_SAVE_PRESET)
        hass.services.async_remove(DOMAIN, SERVICE_RESTORE_PRESET)
        hass.services.async_remove(DOMAIN, SERVICE_DELETE_PRESET)
        hass.services.async_remove(DOMAIN, SERVICE_START_CALIBRATION)
        hass.services.async_remove(DOMAIN, SERVICE_CANCEL_CALIBRATION)
        hass.services.async_remove(DOMAIN, SERVICE_ADVANCE_CALIBRATION)
        hass.data.pop(DOMAIN, None)
    return unloaded
