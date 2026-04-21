"""Base entity for ReST Performance Bed."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import RestBedCoordinator


class RestBedEntity(CoordinatorEntity[RestBedCoordinator]):
    """Base class for all ReST bed entities."""

    _attr_has_entity_name = True
    _description: str | None = None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose an optional human-readable description as a state attribute."""
        if self._description:
            return {"description": self._description}
        return None

    def __init__(self, coordinator: RestBedCoordinator, key: str) -> None:
        super().__init__(coordinator)
        device = coordinator.device_info_data
        self._pump_id: str = device["id"]
        self._attr_unique_id = f"{self._pump_id}_{key}"

    def _async_commit_coordinator_data(self) -> None:
        """Publish local coordinator mutations to all listening entities."""
        if self.coordinator.data is None:
            self.async_write_ha_state()
            return

        self.coordinator.async_set_updated_data(dict(self.coordinator.data))

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
