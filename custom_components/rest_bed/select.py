"""Select entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .const import MODE_POSITION, MODES, POSITION_PROFILE_OPTIONS
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RestBedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            RestBedModeSelect(coordinator),
            RestBedPositionProfileSelect(coordinator),
        ]
    )


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

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes or {}
        attrs["detected_position"] = self.coordinator.data.get("body", {}).get(
            "position"
        )
        attrs["position_profile_editor"] = (
            self.coordinator.selected_position_profile
        )
        return attrs

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.pump.set_mode(option)
        self.coordinator.data.get("preferences", {})["mode"] = option
        self._async_commit_coordinator_data()


class RestBedPositionProfileSelect(RestBedEntity, SelectEntity):
    _attr_name = "Position Profile"
    _attr_icon = "mdi:account-switch"
    _attr_options = POSITION_PROFILE_OPTIONS
    _description = (
        "Select which Position-mode profile the Position zone sliders edit. "
        "This does not override the bed's live body-position detection."
    )

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "position_profile")

    @property
    def available(self) -> bool:
        return super().available and (
            self.coordinator.data.get("preferences", {}).get("mode")
            == MODE_POSITION
        )

    @property
    def current_option(self) -> str | None:
        return self.coordinator.selected_position_profile

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes or {}
        attrs["detected_position"] = self.coordinator.data.get("body", {}).get(
            "position"
        )
        return attrs

    async def async_select_option(self, option: str) -> None:
        self.coordinator.set_selected_position_profile(option)
