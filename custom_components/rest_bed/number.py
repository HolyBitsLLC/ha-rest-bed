"""Number entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .const import MODE_POSITION, POSITION_PROFILE_TO_KEY, ZONE_NAMES
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity

PROFILE_KEYS = {
    "manualprofile": "Manual",
    "backprofile": "Back",
    "sideprofile": "Side",
}

# Descriptions exposed as extra-state attributes for user reference.
_DESC_FIRMNESS = (
    "Overall firmness target for the mattress. The pump adjusts all zone "
    "pressures proportionally toward this level. Higher = firmer."
)
_DESC_DISTORTION = (
    "Pressure variation allowed between zones. Higher values produce more "
    "differentiation between body areas (e.g. softer hips, firmer lumbar)."
)
_DESC_TOLERANCE = (
    "Acceptable pressure deviation (0-10) before the pump auto-corrects. "
    "Lower = tighter control with more frequent pump adjustments."
)
_DESC_SENSITIVITY = (
    "Sensor sensitivity for body detection. Higher values make the bed more "
    "responsive to small movements and lighter body weights."
)
_DESC_ZONE = {
    "manualprofile": "Target firmness for the {zone} zone in Manual mode.",
    "backprofile": (
        "Target firmness for the {zone} zone when Position mode "
        "detects back sleeping."
    ),
    "sideprofile": (
        "Target firmness for the {zone} zone when Position mode "
        "detects side sleeping."
    ),
}
_DESC_POSITION_ZONE = (
    "Target firmness for the {zone} zone in Position mode. "
    "Use the Position Profile select to choose whether you are editing "
    "the Back or Side profile."
)


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
    for profile_key, label in PROFILE_KEYS.items():
        for idx, zone in enumerate(ZONE_NAMES):
            entities.append(
                RestBedZoneNumber(coordinator, profile_key, label, idx, zone)
            )
    for idx, zone in enumerate(ZONE_NAMES):
        entities.append(RestBedPositionZoneNumber(coordinator, idx, zone))
    async_add_entities(entities)


class RestBedFirmnessNumber(RestBedEntity, NumberEntity):
    _attr_name = "Firmness"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 2
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _description = _DESC_FIRMNESS

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "firmness")

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get("preferences", {}).get("firmness")
        return raw * 2 if raw is not None else None

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value / 2)
        await self.coordinator.pump.set_firmness(raw)
        self.coordinator.data.get("preferences", {})["firmness"] = raw
        self._async_commit_coordinator_data()


class RestBedDistortionNumber(RestBedEntity, NumberEntity):
    _attr_name = "Distortion"
    _attr_icon = "mdi:tune-vertical"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 2
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _description = _DESC_DISTORTION

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "distortion")

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get("preferences", {}).get("distortion")
        return raw * 2 if raw is not None else None

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value / 2)
        await self.coordinator.pump.set_distortion(raw)
        self.coordinator.data.get("preferences", {})["distortion"] = raw
        self._async_commit_coordinator_data()


class RestBedToleranceNumber(RestBedEntity, NumberEntity):
    _attr_name = "Tolerance"
    _attr_icon = "mdi:arrow-expand-horizontal"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _description = _DESC_TOLERANCE

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "tolerance")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("tolerance")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_tolerance(int(value))
        self.coordinator.data.get("preferences", {})["tolerance"] = int(value)
        self._async_commit_coordinator_data()


class RestBedSensitivityNumber(RestBedEntity, NumberEntity):
    _attr_name = "Sensitivity"
    _attr_icon = "mdi:signal-variant"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG
    _description = _DESC_SENSITIVITY

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "sensitivity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("preferences", {}).get("sensitivity")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.pump.set_sensitivity(int(value))
        self.coordinator.data.get("preferences", {})["sensitivity"] = int(value)
        self._async_commit_coordinator_data()


class RestBedZoneNumber(RestBedEntity, NumberEntity):
    _attr_icon = "mdi:waves"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 2
    _attr_native_unit_of_measurement = PERCENTAGE
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
        self._description = _DESC_ZONE[profile_key].format(zone=zone_name)
        if profile_key in ("backprofile", "sideprofile"):
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        profile = self.coordinator.data.get("preferences", {}).get(
            self._profile_key, []
        )
        if self._zone_idx < len(profile):
            return profile[self._zone_idx] * 2
        return None

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value / 2)
        prefs = self.coordinator.data.get("preferences", {})
        profile = list(prefs.get(self._profile_key, [0, 0, 0, 0]))
        profile[self._zone_idx] = raw

        setter = {
            "manualprofile": self.coordinator.pump.set_manual_profile,
            "backprofile": self.coordinator.pump.set_back_profile,
            "sideprofile": self.coordinator.pump.set_side_profile,
        }[self._profile_key]
        await setter(profile)

        prefs[self._profile_key] = profile
        self._async_commit_coordinator_data()


class RestBedPositionZoneNumber(RestBedEntity, NumberEntity):
    _attr_icon = "mdi:waves"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 2
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: RestBedCoordinator, zone_idx: int, zone_name: str
    ) -> None:
        super().__init__(coordinator, f"positionprofile_{zone_idx}")
        self._zone_idx = zone_idx
        self._attr_name = f"Position {zone_name}"
        self._description = _DESC_POSITION_ZONE.format(zone=zone_name)

    @property
    def available(self) -> bool:
        return super().available and (
            self.coordinator.data.get("preferences", {}).get("mode")
            == MODE_POSITION
        )

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes or {}
        attrs["editing_profile"] = self.coordinator.selected_position_profile
        attrs["detected_position"] = self.coordinator.data.get("body", {}).get(
            "position"
        )
        return attrs

    @property
    def native_value(self) -> float | None:
        profile_key = POSITION_PROFILE_TO_KEY[
            self.coordinator.selected_position_profile
        ]
        profile = self.coordinator.data.get("preferences", {}).get(profile_key, [])
        if self._zone_idx < len(profile):
            return profile[self._zone_idx] * 2
        return None

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value / 2)
        prefs = self.coordinator.data.get("preferences", {})
        profile_key = POSITION_PROFILE_TO_KEY[
            self.coordinator.selected_position_profile
        ]
        profile = list(prefs.get(profile_key, [0, 0, 0, 0]))
        profile[self._zone_idx] = raw

        setter = {
            "backprofile": self.coordinator.pump.set_back_profile,
            "sideprofile": self.coordinator.pump.set_side_profile,
        }[profile_key]
        await setter(profile)

        prefs[profile_key] = profile
        self._async_commit_coordinator_data()
