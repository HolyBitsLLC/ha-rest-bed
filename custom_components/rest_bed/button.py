"""Button entities for ReST Performance Bed calibration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
            RestBedStartCalibrationButton(coordinator),
            RestBedCancelCalibrationButton(coordinator),
        ]
    )


class RestBedStartCalibrationButton(RestBedEntity, ButtonEntity):
    _attr_name = "Start Calibration"
    _attr_icon = "mdi:tune"
    _description = (
        "Start the multi-step pressure sensor calibration. "
        "The bed will switch to flat mode, capture an empty-bed baseline, "
        "then guide you to lie down to capture your body pressure profile. "
        "Optimal zone pressures are computed and applied automatically."
    )

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "start_calibration")

    async def async_press(self) -> None:
        await self.coordinator.calibration.start()


class RestBedCancelCalibrationButton(RestBedEntity, ButtonEntity):
    _attr_name = "Cancel Calibration"
    _attr_icon = "mdi:close-circle-outline"
    _description = "Cancel an in-progress calibration and restore the previous bed settings."

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        super().__init__(coordinator, "cancel_calibration")

    async def async_press(self) -> None:
        await self.coordinator.calibration.cancel()
