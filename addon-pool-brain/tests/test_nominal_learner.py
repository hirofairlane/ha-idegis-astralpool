"""Tests for the EMA nominal-W learner."""
from __future__ import annotations

import pytest
from nominal_learner import (
    DEFAULT_ALPHA,
    DEFAULT_NOISE_FLOOR_W,
    HARD_MIN_W,
    LearnerSample,
    LearnerState,
    update,
)


def test_default_alpha_value():
    assert DEFAULT_ALPHA == 0.02


def test_switch_off_is_ignored():
    s = LearnerSample(switch_state="off", power_w=1500)
    before = LearnerState(nominal_w=1100, samples_seen=42)
    after = update(before, s)
    assert after == before  # untouched


def test_unknown_switch_is_ignored():
    s = LearnerSample(switch_state=None, power_w=1500)
    before = LearnerState(nominal_w=1100, samples_seen=42)
    after = update(before, s)
    assert after == before


def test_below_noise_floor_is_ignored():
    """Coil-only readings (1-2 W typical) must not bias the estimate."""
    s = LearnerSample(switch_state="on", power_w=DEFAULT_NOISE_FLOOR_W - 1)
    before = LearnerState(nominal_w=1100, samples_seen=42)
    after = update(before, s)
    assert after == before


def test_first_valid_sample_pulls_estimate_a_bit():
    """One sample at 1200 W should nudge nominal toward 1200 by alpha."""
    s = LearnerSample(switch_state="on", power_w=1200)
    before = LearnerState(nominal_w=1100, samples_seen=0)
    after = update(before, s)
    # EMA: new = (1 - 0.02) * 1100 + 0.02 * 1200 = 1102
    assert after.nominal_w == 1102.0
    assert after.samples_seen == 1


def test_many_samples_converge_to_truth():
    """With ~500 steady samples, EMA should converge close to the input."""
    state = LearnerState(nominal_w=1100)
    for _ in range(500):
        state = update(state, LearnerSample(switch_state="on", power_w=1300))
    assert state.nominal_w == pytest.approx(1300.0, abs=1.0)
    assert state.samples_seen == 500


def test_hard_min_floor_applied():
    """Even if the EMA tries to converge to 30 W, we floor at HARD_MIN_W."""
    state = LearnerState(nominal_w=HARD_MIN_W + 1)
    # A pathological all-low scenario can't happen in real life because
    # we ignore samples < noise floor, but verify the clamp anyway by
    # passing a sample just above noise floor for a long time.
    for _ in range(10_000):
        state = update(
            state,
            LearnerSample(switch_state="on", power_w=DEFAULT_NOISE_FLOOR_W + 1),
        )
    assert state.nominal_w >= HARD_MIN_W


def test_alpha_override_speeds_convergence():
    state = LearnerState(nominal_w=1000)
    fast = update(state, LearnerSample(switch_state="on", power_w=1200), alpha=0.5)
    slow = update(state, LearnerSample(switch_state="on", power_w=1200), alpha=0.02)
    assert fast.nominal_w > slow.nominal_w


def test_noise_floor_override():
    """Lowering the noise floor should let an otherwise-rejected sample in."""
    state = LearnerState(nominal_w=1100)
    rejected = update(state, LearnerSample(switch_state="on", power_w=10))
    accepted = update(
        state,
        LearnerSample(switch_state="on", power_w=10),
        noise_floor_w=5,
    )
    assert rejected == state
    assert accepted != state
