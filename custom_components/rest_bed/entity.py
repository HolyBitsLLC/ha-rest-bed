"""Base entity for ReST Performance Bed."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import RestBedCoordinator


class RestBedEntity(CoordinatorEntity[RestBedCoordinator]):
    """Base class for all ReST bed entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RestBedCoordinator, key: str) -> None:
        super().__init__(coordinator)
        device = coordinator.device_info_data
        self._pump_id: str = device["id"]
        self._attr_unique_id = f"{self._pump_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.device_info_data
        model_code = device.get("model", "")
        return DeviceInfo(
            identifiers={(DOMAIN, device["id"])},
            name=device.get("name", f"ReST Bed {device['id']}"),
            manufacturer="ReST Performance",
            model=MODEL_NAMES.get(model_code, model_code),
            sw_version=self.coordinator.data.get("firmware", ""),
            configuration_url=f"http://{self.coordinator.pump.host}",
        )
