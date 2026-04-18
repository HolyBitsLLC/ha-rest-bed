"""Number entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .const import ZONE_NAMES
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity

PROFILE_KEYS = {
    "manualprofile": ("Manual", RestBedCoordinator),
    "backprofile": ("Back", RestBedCoordinator),
    "sideprofile": ("Side", RestBedCoordinator),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RestBedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        RestBedFirmnessNumber(coordinator),
        RestBedDistortionNumber(coordinator),
        RestBedToleranceNumber(coordinator),
        RestBedSensitivityNumber(coordinator),
    ]
    for profile_key, (label, _) in PROFILE_KEYS.items():
        for idx, zone in enumerate(ZONE_NAMES):
            entities.append(
                RestBedZoneNumber(coordinator, profile_key, label, idx, zone)
            )
    async_add_entities(entities)


class RestBedFirmnessNumber(RestBedEntity, NumberEntity):
    _attr_name = "Firmness"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = 0
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "firmness")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("firmness")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_firmness(int(value))
        self.coordinator.data.get("preferences", {})["firmness"] = int(value)
        self.async_write_ha_state()


class RestBedDistortionNumber(RestBedEntity, NumberEntity):
    _attr_name = "Distortion"
    _attr_icon = "mdi:tune-vertical"
    _attr_native_min_value = 0
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "distortion")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("distortion")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_distortion(int(value))
        self.coordinator.data.get("preferences", {})["distortion"] = int(value)
        self.async_write_ha_state()


class RestBedToleranceNumber(RestBedEntity, NumberEntity):
    _attr_name = "Tolerance"
    _attr_icon = "mdi:arrow-expand-horizontal"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "tolerance")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("tolerance")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_tolerance(int(value))
        self.coordinator.data.get("preferences", {})["tolerance"] = int(value)
        self.async_write_ha_state()


class RestBedSensitivityNumber(RestBedEntity, NumberEntity):
    _attr_name = "Sensitivity"
    _attr_icon = "mdi:signal-variant"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "sensitivity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("sensitivity")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_sensitivity(int(value))
        self.coordinator.data.get("preferences", {})["sensitivity"] = int(value)
        self.async_write_ha_state()


class RestBedZoneNumber(RestBedEntity, NumberEntity):
    _attr_icon = "mdi:waves"
    _attr_native_min_value = 0
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: RestBedCoordinator,
        profile_key: str,
        profile_label: str,
        zone_idx: int,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator, f"{profile_key}_{zone_idx}")
        self._profile_key = profile_key
        self._zone_idx = zone_idx
        self._attr_name = f"{profile_label} {zone_name}"

    @property
    def native_value(self) -> float | None:
        profile = self.coordinator.data.get("preferences", {}).get(
            self._profile_key, []
        )
        if self._zone_idx < len(profile):
            return profile[self._zone_idx]
        return None

    async def async_set_native_value(self, value: float) -> None:
        prefs = self.coordinator.data.get("preferences", {})
        profile = list(prefs.get(self._profile_key, [0, 0, 0, 0]))
        profile[self._zone_idx] = int(value)

        setter = {
            "manualprofile": self.coordinator.pump.set_manual_profile,
            "backprofile": self.coordinator.pump.set_back_profile,
            "sideprofile": self.coordinator.pump.set_side_profile,
        }[self._profile_key]
        await setter(profile)

        prefs[self._profile_key] = profile
        self.async_write_ha_state()
