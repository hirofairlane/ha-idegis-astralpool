"""Pure decision function for pump / cleaner anomalies.

Side-effect free. Receives the current sample plus the latched timers and
returns the new latched timers + which (if any) anomaly is now firing.
This lives separately from `pump_watch.py` so it can be unit-tested
without HA or MQTT.

Definitions:

- **overcurrent**: power > nominal * (1 + margin) for > 30 s. Possibly a
  blocked impeller or a closed valve.
- **dry**: switch == "on" AND power < nominal * 0.2 for > 60 s. The motor
  is spinning without water; the seal will degrade quickly.
- **stuck**: switch == "off" AND power > 5 W for > 60 s. The contactor
  is welded closed; the user has to flip the breaker.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Default thresholds — also exposed as constants so tests can reuse them.
OVERCURRENT_DURATION_S = 30
DRY_DURATION_S = 60
STUCK_DURATION_S = 60
OVERCURRENT_MARGIN_PCT_DEFAULT = 20
DRY_THRESHOLD_PCT_DEFAULT = 20
STUCK_W_THRESHOLD = 5

Kind = Literal["overcurrent", "dry", "stuck", ""]


@dataclass
class Sample:
    """Live snapshot from the Shelly channel + HA switch state."""

    switch_state: str | None  # "on" / "off" / None if unavailable
    power_w: float
    nominal_w: float
    overcurrent_margin_pct: float = OVERCURRENT_MARGIN_PCT_DEFAULT
    dry_threshold_pct: float = DRY_THRESHOLD_PCT_DEFAULT


@dataclass
class Latched:
    """Per-channel state that persists between samples.

    `*_since` is the epoch seconds when the corresponding condition
    started being continuously true (None means not currently true —
    using `None` rather than 0 sidesteps the ambiguity at the epoch).
    `last_fired_kind` is the anomaly currently in effect — used to avoid
    re-firing the same Telegram message every tick.
    """

    overcurrent_since: float | None = None
    dry_since: float | None = None
    stuck_since: float | None = None
    last_fired_kind: Kind = ""


@dataclass
class Decision:
    """Outcome of one tick."""

    latched: Latched
    active_kind: Kind = ""  # currently-on anomaly (overcurrent / dry / stuck / "")
    just_fired: bool = False  # True only on the tick the anomaly transitions on


def _update_since(active: bool, since: float | None, now: float) -> float | None:
    """Latch helper: starts the timer on first True, resets on False."""
    if not active:
        return None
    if since is None:
        return now
    return since


def decide(sample: Sample, latched: Latched, now: float) -> Decision:
    """Apply the three rules and return the resulting Decision.

    The function is deterministic and idempotent on a given (sample,
    latched, now) tuple. It updates the latched timers and resolves the
    *currently firing* anomaly with this priority order:
    overcurrent > dry > stuck.
    """
    if sample.nominal_w <= 0:
        # Without a nominal we cannot evaluate % thresholds; fall back to
        # a passive "no anomaly" stance and reset every latch.
        return Decision(latched=Latched(), active_kind="", just_fired=False)

    overcurrent_threshold = sample.nominal_w * (
        1 + sample.overcurrent_margin_pct / 100
    )
    dry_threshold = sample.nominal_w * (sample.dry_threshold_pct / 100)

    overcurrent = sample.power_w > overcurrent_threshold
    dry = sample.switch_state == "on" and sample.power_w < dry_threshold
    stuck = sample.switch_state == "off" and sample.power_w > STUCK_W_THRESHOLD

    new_latched = Latched(
        overcurrent_since=_update_since(overcurrent, latched.overcurrent_since, now),
        dry_since=_update_since(dry, latched.dry_since, now),
        stuck_since=_update_since(stuck, latched.stuck_since, now),
        last_fired_kind=latched.last_fired_kind,
    )

    over_lasting = (
        new_latched.overcurrent_since is not None
        and (now - new_latched.overcurrent_since) > OVERCURRENT_DURATION_S
    )
    dry_lasting = (
        new_latched.dry_since is not None
        and (now - new_latched.dry_since) > DRY_DURATION_S
    )
    stuck_lasting = (
        new_latched.stuck_since is not None
        and (now - new_latched.stuck_since) > STUCK_DURATION_S
    )

    active: Kind = ""
    if over_lasting:
        active = "overcurrent"
    elif dry_lasting:
        active = "dry"
    elif stuck_lasting:
        active = "stuck"

    just_fired = bool(active) and active != latched.last_fired_kind
    new_latched.last_fired_kind = active

    return Decision(
        latched=new_latched,
        active_kind=active,
        just_fired=just_fired,
    )
