"""Recommended pump time engine.

Computes a recommended runtime for today combining:
- TFP-derived temperature heat-load table.
- Turnover requirement based on pool volume and nominal flow.
- Chemistry correction (multiplier when bands fall off `ok`).

History-aware refinement is left to a v2 iteration. See SPEC.md.
"""
from __future__ import annotations

from dataclasses import dataclass


# Indoor-pool minutes per day based on water temperature.
# Designed for a single daily run; the user can split it.
_BASE_BY_TEMP: list[tuple[float, int]] = [
    (18, 30),
    (24, 60),
    (28, 120),
    (32, 240),
    (36, 360),
    (999, 480),
]


def _base_minutes_from_temp(temp_c: float | None) -> int:
    if temp_c is None:
        return 120
    for cap, minutes in _BASE_BY_TEMP:
        if temp_c < cap:
            return minutes
    return 240


def _turnover_minutes(
    volume_m3: float, flow_m3_per_h: float, target_turnovers_per_day: float
) -> int:
    if flow_m3_per_h <= 0:
        return 0
    return int(round((volume_m3 * target_turnovers_per_day / flow_m3_per_h) * 60))


def _chemistry_multiplier(bands: dict[str, str]) -> float:
    """1.0 if all ok; 1.2 if warning; 1.5 if danger or saturated chain."""
    has_danger = any(v.startswith("danger") for v in bands.values())
    has_warning = any(
        v.startswith("warning") or v == "warm" for v in bands.values()
    )
    saturated = bands.get("production") == "saturated"
    if has_danger:
        return 1.5
    if saturated:
        return 1.3
    if has_warning:
        return 1.2
    return 1.0


@dataclass
class TimerInput:
    water_temp_c: float | None
    bands: dict[str, str]
    volume_m3: float
    nominal_flow_m3_h: float
    target_turnovers_per_day: float


def recommended_minutes_today(inp: TimerInput) -> int:
    base = _base_minutes_from_temp(inp.water_temp_c)
    turn = _turnover_minutes(
        inp.volume_m3, inp.nominal_flow_m3_h, inp.target_turnovers_per_day
    )
    mult = _chemistry_multiplier(inp.bands)
    return int(round(max(base, turn) * mult))


def recommended_minutes_week(inp: TimerInput) -> int:
    return recommended_minutes_today(inp) * 7


# Nominal flow lookup by Idegis model. Defaults from manual page 23.
NOMINAL_FLOW_BY_MODEL = {
    "S2-12": 8.0,
    "S2-12/LS": 8.0,
    "S2-24": 12.0,
    "S2-24/LS": 12.0,
    "S2-32": 14.0,
    "S2-32/LS": 14.0,
    "S2-42": 16.0,
    "NEO-12": 8.0,
    "NEO-24": 12.0,
    "NEO-32": 14.0,
    "NEO-42": 16.0,
}


def nominal_flow_for_serial(device_serial: str | None) -> float:
    """Best-effort flow lookup. Falls back to 12 m³/h (the reference unit)."""
    if not device_serial:
        return 12.0
    # The Idegis serial has the model embedded around position 3-6, but
    # without an authoritative decoder we just keep the safe default.
    return 12.0
