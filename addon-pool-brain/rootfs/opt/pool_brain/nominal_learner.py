"""Auto-learn the nominal wattage of a pump/motor.

Maintains a low-pass filtered estimate of the steady-state power draw
of a motor while it's clearly running (switch on + power above a noise
floor). The estimate persists in the counters store so it survives
restarts of the add-on.

Exposed as `sensor.idegis_brain_<channel>_nominal_w_learned` via MQTT so
the user can see how the watchdog is calibrating itself over time.

Design notes:

- Exponential moving average with a configurable alpha (default 0.02).
  At one sample per ~10 s, alpha=0.02 means the EMA reaches ~63 % of a
  step change in roughly 500 s ≈ 8 min — slow enough to ignore startup
  inrush spikes but fast enough to track wear-in across days.
- Refuses to learn from samples below `noise_floor_w`: an unloaded
  contactor coil reads 1-2 W and we don't want it pulling the average
  down to zero.
- Also refuses samples while the switch is off — those are stuck-
  contactor scenarios that should not bias the nominal estimate.
- The learner is a pure transformer over (state, sample). Persistence
  is done by the caller via the counters object.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ALPHA = 0.02
DEFAULT_NOISE_FLOOR_W = 50.0
HARD_MIN_W = 100.0  # never report below this (avoids zero pathologies)


@dataclass
class LearnerSample:
    switch_state: str | None  # "on" / "off" / None
    power_w: float


@dataclass
class LearnerState:
    """The persistent state of a learner for one channel."""

    nominal_w: float = 1100.0
    samples_seen: int = 0


def update(
    state: LearnerState,
    sample: LearnerSample,
    *,
    alpha: float = DEFAULT_ALPHA,
    noise_floor_w: float = DEFAULT_NOISE_FLOOR_W,
) -> LearnerState:
    """Return a new LearnerState after consuming `sample`.

    The original state is not modified. Pure function.
    """
    # Reject samples that should not bias the nominal.
    if sample.switch_state != "on":
        return state
    if sample.power_w < noise_floor_w:
        return state

    new_nominal = (1 - alpha) * state.nominal_w + alpha * sample.power_w
    new_nominal = max(new_nominal, HARD_MIN_W)
    return LearnerState(
        nominal_w=round(new_nominal, 2),
        samples_seen=state.samples_seen + 1,
    )
