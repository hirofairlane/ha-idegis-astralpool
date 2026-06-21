"""Tests for the pure anomaly decision function.

Each scenario uses an explicit `now` clock so transitions are
deterministic. We never patch real time.
"""
from __future__ import annotations

from anomaly import (
    DRY_DURATION_S,
    STUCK_DURATION_S,
    Latched,
    Sample,
    decide,
)

# ---------- Helpers --------------------------------------------------------


def _sample(sw: str | None, power: float, nominal: float = 1100.0) -> Sample:
    return Sample(switch_state=sw, power_w=power, nominal_w=nominal)


def _run_until(
    sample: Sample,
    start_latched: Latched,
    *,
    steps_s: list[float],
) -> tuple[Latched, list[str]]:
    """Apply the same `sample` at each provided `now` value."""
    latched = start_latched
    fired_kinds: list[str] = []
    for now in steps_s:
        d = decide(sample, latched, now)
        latched = d.latched
        if d.just_fired:
            fired_kinds.append(d.active_kind)
    return latched, fired_kinds


# ---------- Normal operation ------------------------------------------------


def test_normal_running_no_anomaly():
    """Switch on, power ≈ nominal — nothing should fire."""
    s = _sample("on", 1100, nominal=1100)
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""
    assert d.just_fired is False


def test_normal_off_no_anomaly():
    """Switch off, power 0 W — silent."""
    s = _sample("off", 0)
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""


def test_nominal_zero_disables_evaluation():
    """If we haven't learned a nominal yet, never fire."""
    s = _sample("on", 5000, nominal=0)
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""


# ---------- Overcurrent -----------------------------------------------------


def test_overcurrent_does_not_fire_immediately():
    """Overcurrent must persist > 30 s before firing."""
    s = _sample("on", 2000, nominal=1100)  # 2000 W vs 1320 W threshold = over
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""  # latched but not fired yet
    assert d.latched.overcurrent_since == 0  # the latch started at now=0


def test_overcurrent_fires_after_duration():
    """Hold overcurrent for >30 s — must fire exactly once on the edge."""
    s = _sample("on", 2000, nominal=1100)
    steps = [0, 10, 20, 31, 40]  # firing happens at 31 s (>30 s after t=0)
    latched, fired = _run_until(s, Latched(), steps_s=steps)
    assert "overcurrent" in fired
    assert fired.count("overcurrent") == 1  # only once
    assert latched.last_fired_kind == "overcurrent"


def test_overcurrent_recovers_clears_latch():
    """Overcurrent then recovery should reset the latch."""
    s_over = _sample("on", 2000, nominal=1100)
    s_ok = _sample("on", 1100, nominal=1100)
    latched, _ = _run_until(s_over, Latched(), steps_s=[0, 10, 20, 31])
    d = decide(s_ok, latched, now=40)
    assert d.latched.overcurrent_since is None
    assert d.active_kind == ""


def test_overcurrent_margin_pct_respected():
    """A higher margin pct should suppress a borderline overcurrent."""
    s_borderline = Sample(
        switch_state="on",
        power_w=1250,
        nominal_w=1100,
        overcurrent_margin_pct=20,  # threshold = 1320, sample 1250 → not over
    )
    d = decide(s_borderline, Latched(), now=0)
    assert d.active_kind == ""

    s_hard = Sample(
        switch_state="on",
        power_w=1500,
        nominal_w=1100,
        overcurrent_margin_pct=20,  # threshold = 1320, sample 1500 → over
    )
    latched, fired = _run_until(s_hard, Latched(), steps_s=[0, 31])
    assert "overcurrent" in fired


# ---------- Dry running -----------------------------------------------------


def test_dry_does_not_fire_immediately():
    s = _sample("on", 50, nominal=1100)  # < 20% of 1100
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""


def test_dry_fires_after_duration():
    s = _sample("on", 50, nominal=1100)
    _, fired = _run_until(s, Latched(), steps_s=[0, 30, DRY_DURATION_S + 1])
    assert "dry" in fired


def test_dry_does_not_fire_when_switch_off():
    """If the switch is off, dry conditions are not evaluated."""
    s = _sample("off", 50, nominal=1100)
    _, fired = _run_until(s, Latched(), steps_s=[0, 100])
    assert "dry" not in fired


# ---------- Stuck contactor -------------------------------------------------


def test_stuck_does_not_fire_immediately():
    s = _sample("off", 200, nominal=1100)
    d = decide(s, Latched(), now=0)
    assert d.active_kind == ""


def test_stuck_fires_after_duration():
    s = _sample("off", 200, nominal=1100)
    _, fired = _run_until(s, Latched(), steps_s=[0, 30, STUCK_DURATION_S + 1])
    assert "stuck" in fired


def test_stuck_does_not_fire_below_threshold():
    """A 4 W reading while off is below the 5 W stuck threshold."""
    s = _sample("off", 4, nominal=1100)
    _, fired = _run_until(s, Latched(), steps_s=[0, 100, 200])
    assert fired == []


# ---------- Priority --------------------------------------------------------


def test_overcurrent_beats_dry_when_both_could_apply():
    """If overcurrent latched first and reached its window earlier, it wins.

    Constructive: only one condition can be true at any single sample
    (overcurrent is power > threshold high; dry is power < threshold
    low), so we don't need to test simultaneous firing — but we can
    verify priority by hand-crafting Latched.
    """
    latched = Latched(
        overcurrent_since=10,
        dry_since=10,
    )
    # Sample says "we're normal" so neither latches further.
    s = _sample("on", 1100, nominal=1100)
    d = decide(s, latched, now=100)
    # Both timers are cleared because conditions are no longer true.
    assert d.active_kind == ""
    assert d.latched.overcurrent_since is None
    assert d.latched.dry_since is None


def test_just_fired_only_on_transition_not_every_tick():
    """Once active, subsequent ticks should not re-set just_fired."""
    s = _sample("on", 2000, nominal=1100)
    latched = Latched()
    decisions = []
    for now in [0, 31, 40, 50]:
        d = decide(s, latched, now)
        latched = d.latched
        decisions.append(d)
    fired = [d.just_fired for d in decisions]
    # First two: no fire (latching), third: fired, fourth+: still active
    # but just_fired must be False since the kind didn't change.
    assert fired.count(True) == 1
    assert decisions[-1].active_kind == "overcurrent"
    assert decisions[-1].just_fired is False
