"""Select entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .const import MODES
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RestBedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([RestBedModeSelect(entry.runtime_data)])


class RestBedModeSelect(RestBedEntity, SelectEntity):
    _attr_name = "Mode"
    _attr_icon = "mdi:bed-king"
    _attr_options = MODES
    _description = (
        "Operating mode. Manual: set each zone independently. "
        "Automatic: AI dynamically adjusts based on body position and pressure. "
        "Position: uses Back/Side profiles when a position change is detected. "
        "Pressure: maintains the global firmness target uniformly across all zones."
    )

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "mode")

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get("preferences", {}).get("mode")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.pump.set_mode(option)
        self.coordinator.data.get("preferences", {})["mode"] = option
        self.async_write_ha_state()
