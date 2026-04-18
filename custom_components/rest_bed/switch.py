"""Switch entities for ReST Performance Bed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RestBedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([RestBedQuietSwitch(entry.runtime_data)])


class RestBedQuietSwitch(RestBedEntity, SwitchEntity):
    _attr_name = "Quiet Mode"
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "quiet")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("preferences", {}).get("quiet")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.pump.set_quiet(True)
        self.coordinator.data.get("preferences", {})["quiet"] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.pump.set_quiet(False)
        self.coordinator.data.get("preferences", {})["quiet"] = False
        self.async_write_ha_state()
