"""Binary sensor entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
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
    coordinator = entry.runtime_data
    async_add_entities(
        [
            RestBedBodyPresentSensor(coordinator),
            RestBedMovingSensor(coordinator),
            RestBedFillingSensor(coordinator),
            RestBedOverheatedSensor(coordinator),
        ]
    )


class RestBedBodyPresentSensor(RestBedEntity, BinarySensorEntity):
    _attr_name = "Occupancy"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _description = "Whether someone is currently lying on this side of the bed, detected via the pressure sensor fabric."

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "body_present")

    @property
    def is_on(self) -> bool | None:
        return bool(self.coordinator.data.get("body", {}).get("present"))


class RestBedMovingSensor(RestBedEntity, BinarySensorEntity):
    _attr_name = "Moving"
    _attr_device_class = BinarySensorDeviceClass.MOVING
    _description = "Whether the person is currently moving or shifting position."

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "moving")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("body", {}).get("moving")


class RestBedFillingSensor(RestBedEntity, BinarySensorEntity):
    _attr_name = "Air Filling"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:fan"
    _description = "Whether the pump is currently running to adjust air pressure in the chambers."

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "filling")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("air", {}).get("filling")


class RestBedOverheatedSensor(RestBedEntity, BinarySensorEntity):
    _attr_name = "Overheated"
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _description = "Whether the pump has exceeded its safe operating temperature and may throttle adjustments."

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "overheated")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("temperature", {}).get("overheated")
