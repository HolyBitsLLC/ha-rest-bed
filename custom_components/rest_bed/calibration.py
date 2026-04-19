"""Multi-step pressure-sensor calibration workflow for ReST bed pumps.

Mirrors the mobile app calibration:
  1. Ensure bed is empty → switch to "flat" mode → wait for chambers to equalize.
  2. Capture the empty-bed pressure surface baseline.
  3. User lies on bed → wait for presence detection → capture body-on-bed surface.
  4. Compute optimal zone pressure targets from the pressure delta.
  5. Apply new profiles and restore the previous operating mode.

The workflow is driven as a state machine. Each transition can be triggered
by the user (via HA service calls) or auto-advanced when the pump state
meets the required conditions (e.g. body detected for step 3).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import RestBedCoordinator

_LOGGER = logging.getLogger(__name__)

# How long to wait for chamber pressure equalization (seconds)
EQUALIZE_TIMEOUT = 120
# Max delta between target and actual pressure (per zone) to consider equalized
EQUALIZE_THRESHOLD = 3
# How many surface samples to average for a stable baseline
SURFACE_SAMPLES = 3
SURFACE_SAMPLE_INTERVAL = 2  # seconds between samples


class CalibrationStep(str, Enum):
    """Steps in the calibration workflow."""

    IDLE = "idle"
    PREPARING = "preparing"           # Switching to flat mode, waiting to equalize
    WAITING_EMPTY = "waiting_empty"   # Waiting for user to get off bed
    EQUALIZING = "equalizing"         # Chambers equalizing
    CAPTURING_BASELINE = "capturing_baseline"
    WAITING_BODY = "waiting_body"     # Waiting for user to lie down
    CAPTURING_BODY = "capturing_body"
    COMPUTING = "computing"           # Computing optimal profiles
    APPLYING = "applying"             # Applying new profiles
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class CalibrationState:
    """Tracks current calibration progress for one pump."""

    step: CalibrationStep = CalibrationStep.IDLE
    message: str = ""
    previous_mode: str = "pressure"
    previous_preferences: dict = field(default_factory=dict)
    baseline_surface: list[int] | None = None
    body_surface: list[int] | None = None
    computed_targets: list[int] | None = None
    progress_pct: int = 0


class CalibrationManager:
    """Manages the multi-step calibration workflow for a single pump."""

    def __init__(self, coordinator: RestBedCoordinator) -> None:
        self._coord = coordinator
        self.state = CalibrationState()
        self._task: asyncio.Task | None = None

    @property
    def step(self) -> CalibrationStep:
        return self.state.step

    # ── Public API ───────────────────────────────────────────────────

    async def start(self) -> None:
        """Begin calibration. The bed should ideally be empty already."""
        if self.state.step not in (
            CalibrationStep.IDLE,
            CalibrationStep.COMPLETE,
            CalibrationStep.FAILED,
        ):
            raise RuntimeError(
                f"Calibration already in progress (step={self.state.step.value})"
            )

        self.state = CalibrationState()
        self.state.step = CalibrationStep.PREPARING
        self.state.message = "Saving current settings and preparing bed…"

        # Save current settings so we can restore after calibration
        prefs = self._coord.data.get("preferences", {})
        self.state.previous_mode = prefs.get("mode", "pressure")
        self.state.previous_preferences = dict(prefs)

        self._notify()

        # Run the workflow in a background task
        self._task = asyncio.create_task(self._run_workflow())

    async def cancel(self) -> None:
        """Cancel an in-progress calibration and restore previous settings."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Restore previous mode
        try:
            await self._coord.pump.set_mode(self.state.previous_mode)
        except Exception:
            _LOGGER.exception("Failed to restore mode after cancellation")

        self.state.step = CalibrationStep.IDLE
        self.state.message = "Calibration cancelled"
        self._notify()

    async def advance(self) -> None:
        """Manually advance to the next step (for steps that require user confirmation)."""
        # Some steps auto-advance; this is for user-driven transitions
        if self.state.step == CalibrationStep.WAITING_BODY:
            # User confirms they're on the bed
            body = self._coord.data.get("body", {})
            if body.get("present"):
                self.state.step = CalibrationStep.CAPTURING_BODY
                self.state.message = "Capturing body pressure profile…"
                self._notify()

    # ── Workflow ─────────────────────────────────────────────────────

    async def _run_workflow(self) -> None:
        """Execute the full calibration sequence."""
        try:
            await self._step_prepare()
            await self._step_wait_empty()
            await self._step_equalize()
            await self._step_capture_baseline()
            await self._step_wait_body()
            await self._step_capture_body()
            await self._step_compute()
            await self._step_apply()

            self.state.step = CalibrationStep.COMPLETE
            self.state.message = "Calibration complete! New profiles applied."
            self.state.progress_pct = 100
            self._notify()

        except asyncio.CancelledError:
            _LOGGER.info("Calibration cancelled")
            raise
        except Exception as exc:
            _LOGGER.exception("Calibration failed")
            self.state.step = CalibrationStep.FAILED
            self.state.message = f"Calibration failed: {exc}"
            self._notify()

    async def _step_prepare(self) -> None:
        """Switch to flat mode for equalization."""
        self.state.step = CalibrationStep.PREPARING
        self.state.message = "Switching to flat mode…"
        self.state.progress_pct = 5
        self._notify()

        await self._coord.pump.set_mode("flat")
        _LOGGER.info("Calibration: switched to flat mode")

    async def _step_wait_empty(self) -> None:
        """Wait for the bed to be empty."""
        body = self._coord.data.get("body", {})
        if body.get("present"):
            self.state.step = CalibrationStep.WAITING_EMPTY
            self.state.message = "Please get out of bed so the sensors can calibrate."
            self.state.progress_pct = 10
            self._notify()

            for _ in range(300):  # Up to 5 min
                await asyncio.sleep(1)
                body = self._coord.data.get("body", {})
                if not body.get("present"):
                    break
            else:
                raise TimeoutError("Bed was not emptied within 5 minutes")

        # Give a moment for the sensor to settle after person leaves
        await asyncio.sleep(5)

    async def _step_equalize(self) -> None:
        """Wait for all air chambers to reach their targets."""
        self.state.step = CalibrationStep.EQUALIZING
        self.state.message = "Equalizing air chambers…"
        self.state.progress_pct = 20
        self._notify()

        for elapsed in range(EQUALIZE_TIMEOUT):
            air = self._coord.data.get("air", {})
            targets = air.get("targets", [])
            pressures = air.get("pressures", [])

            if targets and pressures and len(targets) == len(pressures):
                deltas = [abs(t - p) for t, p in zip(targets, pressures)]
                if all(d <= EQUALIZE_THRESHOLD for d in deltas):
                    _LOGGER.info(
                        "Calibration: chambers equalized (deltas=%s)", deltas
                    )
                    break

            pct = 20 + int(30 * elapsed / EQUALIZE_TIMEOUT)
            self.state.progress_pct = min(pct, 49)
            self._notify()
            await asyncio.sleep(1)
        else:
            _LOGGER.warning("Chambers did not fully equalize within timeout")

        # Extra settle time
        await asyncio.sleep(5)

    async def _step_capture_baseline(self) -> None:
        """Capture empty-bed surface pressure as baseline."""
        self.state.step = CalibrationStep.CAPTURING_BASELINE
        self.state.message = "Capturing empty-bed pressure baseline…"
        self.state.progress_pct = 50
        self._notify()

        self.state.baseline_surface = await self._capture_surface_average()
        _LOGGER.info(
            "Calibration: baseline captured (%d cells)",
            len(self.state.baseline_surface),
        )

    async def _step_wait_body(self) -> None:
        """Wait for the user to lie on the bed."""
        self.state.step = CalibrationStep.WAITING_BODY
        self.state.message = (
            "Baseline captured! Please lie on the bed in your normal sleeping "
            "position and stay still for 30 seconds."
        )
        self.state.progress_pct = 60
        self._notify()

        for _ in range(300):  # Up to 5 min
            await asyncio.sleep(1)
            body = self._coord.data.get("body", {})
            if body.get("present") and not body.get("moving"):
                # Wait a bit longer for them to settle
                await asyncio.sleep(10)
                break
        else:
            raise TimeoutError("Nobody detected on the bed within 5 minutes")

    async def _step_capture_body(self) -> None:
        """Capture body-on-bed surface pressure."""
        self.state.step = CalibrationStep.CAPTURING_BODY
        self.state.message = "Capturing body pressure profile… Hold still."
        self.state.progress_pct = 70
        self._notify()

        # Wait for movement to stop
        for _ in range(30):
            body = self._coord.data.get("body", {})
            if not body.get("moving"):
                break
            await asyncio.sleep(1)

        self.state.body_surface = await self._capture_surface_average()
        _LOGGER.info(
            "Calibration: body profile captured (%d cells)",
            len(self.state.body_surface),
        )

    async def _step_compute(self) -> None:
        """Compute optimal zone pressure targets from baseline vs body delta."""
        self.state.step = CalibrationStep.COMPUTING
        self.state.message = "Computing optimal pressure profiles…"
        self.state.progress_pct = 85
        self._notify()

        baseline = self.state.baseline_surface
        body = self.state.body_surface

        if not baseline or not body or len(baseline) != len(body):
            raise ValueError("Surface captures are missing or mismatched")

        # Compute per-cell pressure delta (body load on each cell)
        delta = [max(0, b - bl) for b, bl in zip(body, baseline)]

        # The pump has a 16-column x 58-row grid; 4 zones from bottom to top:
        #   Zone 0 (Feet):   rows 0-14   (bottom 25%)
        #   Zone 1 (Hips):   rows 15-29
        #   Zone 2 (Lumbar): rows 30-44
        #   Zone 3 (Head):   rows 45-57  (top 25%)
        air = self._coord.data.get("air", {})
        cols = 16
        rows = 58
        zone_rows = [
            (0, 15),    # Feet
            (15, 30),   # Hips
            (30, 45),   # Lumbar
            (45, 58),   # Head
        ]

        zone_loads: list[float] = []
        for row_start, row_end in zone_rows:
            zone_sum = 0
            zone_count = 0
            for r in range(row_start, row_end):
                for c in range(cols):
                    idx = r * cols + c
                    if idx < len(delta):
                        zone_sum += delta[idx]
                        zone_count += 1
            zone_loads.append(zone_sum / zone_count if zone_count > 0 else 0)

        # Normalize loads and map to pressure targets
        # Heavier zones need more pressure support
        min_pressure = air.get("minimum", 5)
        max_pressure = air.get("maximum", 50)
        pressure_range = max_pressure - min_pressure

        max_load = max(zone_loads) if max(zone_loads) > 0 else 1
        targets = []
        for load in zone_loads:
            # Scale: higher body load → higher pressure target
            # Base of 40% + proportional load
            ratio = load / max_load
            target = int(min_pressure + pressure_range * (0.4 + 0.5 * ratio))
            target = max(min_pressure, min(max_pressure, target))
            targets.append(target)

        self.state.computed_targets = targets
        _LOGGER.info("Calibration: computed zone targets: %s", targets)

    async def _step_apply(self) -> None:
        """Apply computed profiles and restore operating mode."""
        self.state.step = CalibrationStep.APPLYING
        self.state.message = "Applying new pressure profiles…"
        self.state.progress_pct = 95
        self._notify()

        targets = self.state.computed_targets
        if not targets or len(targets) != 4:
            raise ValueError("Computed targets are invalid")

        # Apply as the back profile (primary sleeping position)
        await self._coord.pump.set_back_profile(targets)
        _LOGGER.info("Calibration: applied back profile: %s", targets)

        # Also update manual profile for immediate use
        await self._coord.pump.set_manual_profile(targets)

        # Restore the previous mode
        await self._coord.pump.set_mode(self.state.previous_mode)
        _LOGGER.info(
            "Calibration: restored mode to '%s'", self.state.previous_mode
        )

    # ── Helpers ──────────────────────────────────────────────────────

    async def _capture_surface_average(self) -> list[int]:
        """Capture multiple surface readings and return the averaged grid."""
        samples: list[list[int]] = []
        for _ in range(SURFACE_SAMPLES):
            resp = await self._coord.pump._get("/api/surface")
            pressures = resp.get("pressures", [])
            if pressures:
                samples.append(pressures)
            await asyncio.sleep(SURFACE_SAMPLE_INTERVAL)

        if not samples:
            raise RuntimeError("No surface data returned from pump")

        # Average each cell across samples
        n_cells = len(samples[0])
        averaged = []
        for i in range(n_cells):
            total = sum(s[i] for s in samples if i < len(s))
            averaged.append(round(total / len(samples)))
        return averaged

    def _notify(self) -> None:
        """Push updated calibration state to HA via coordinator."""
        self._coord.async_set_updated_data(self._coord.data)
