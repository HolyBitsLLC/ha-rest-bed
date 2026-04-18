"""Sensor entities for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RestBedConfigEntry
from .const import ZONE_NAMES
from .coordinator import RestBedCoordinator
from .entity import RestBedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RestBedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        RestBedHeartRateSensor(coordinator),
        RestBedRespirationSensor(coordinator),
        RestBedPositionSensor(coordinator),
        RestBedCpuTempSensor(coordinator),
        RestBedEnclosureTempSensor(coordinator),
        RestBedFirmwareSensor(coordinator),
    ]
    for idx, zone in enumerate(ZONE_NAMES):
        entities.append(RestBedAirPressureSensor(coordinator, idx, zone))
    async_add_entities(entities)


class RestBedHeartRateSensor(RestBedEntity, SensorEntity):
    _attr_name = "Heart Rate"
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "bpm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "heartrate")

    @property
    def native_value(self) -> int | None:
        val = self.coordinator.data.get("body", {}).get("heartrate", 0)
        return val if val else None


class RestBedRespirationSensor(RestBedEntity, SensorEntity):
    _attr_name = "Respiration"
    _attr_icon = "mdi:lungs"
    _attr_native_unit_of_measurement = "br/min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "respiration")

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.get("body", {}).get("respiration", 0.0)
        return val if val else None


class RestBedPositionSensor(RestBedEntity, SensorEntity):
    _attr_name = "Position"
    _attr_icon = "mdi:human"

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "position")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("body", {}).get("position")


class RestBedCpuTempSensor(RestBedEntity, SensorEntity):
    _attr_name = "CPU Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "cpu_temp")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("temperature", {}).get("cpu")


class RestBedEnclosureTempSensor(RestBedEntity, SensorEntity):
    _attr_name = "Enclosure Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "enclosure_temp")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("temperature", {}).get("enclosure")


class RestBedAirPressureSensor(RestBedEntity, SensorEntity):
    _attr_icon = "mdi:gauge"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: RestBedCoordinator, zone_idx: int, zone_name: str
    ) -> None:
        super().__init__(coordinator, f"air_pressure_{zone_idx}")
        self._zone_idx = zone_idx
        self._attr_name = f"Pressure {zone_name}"

    @property
    def native_value(self) -> int | None:
        pressures = self.coordinator.data.get("air", {}).get("pressures", [])
        if self._zone_idx < len(pressures):
            return pressures[self._zone_idx]
        return None


class RestBedFirmwareSensor(RestBedEntity, SensorEntity):
    _attr_name = "Firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("firmware")
