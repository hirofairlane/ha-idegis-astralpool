"""Tests for the recommended-minutes engine.

Exercise the temperature table, the turnover formula, the chemistry
multiplier and the combined recommendation.
"""
from __future__ import annotations

import pytest
from timer_engine import (
    TimerInput,
    _base_minutes_from_temp,
    _chemistry_multiplier,
    _turnover_minutes,
    nominal_flow_for_serial,
    recommended_minutes_today,
    recommended_minutes_week,
)

_OK_BANDS = {
    "ph": "ok",
    "salt": "ok",
    "temperature": "ok",
    "production": "ok",
}


# ---------- Temperature table -----------------------------------------------


@pytest.mark.parametrize(
    "temp,expected",
    [
        (None, 120),
        (10, 30),
        (17.99, 30),
        (18, 60),
        (23, 60),
        (24, 120),
        (28, 240),
        (32, 360),
        (36, 480),
        (40, 480),
    ],
)
def test_base_minutes_from_temp(temp, expected):
    assert _base_minutes_from_temp(temp) == expected


# ---------- Turnover -------------------------------------------------------


def test_turnover_reference_install():
    # 37 m³, 12 m³/h, 1 turnover/day = 185 min
    assert _turnover_minutes(37, 12, 1.0) == 185


def test_turnover_two_per_day_doubles():
    a = _turnover_minutes(37, 12, 1.0)
    b = _turnover_minutes(37, 12, 2.0)
    assert b == 2 * a


def test_turnover_zero_flow_returns_zero():
    assert _turnover_minutes(37, 0, 1.0) == 0


# ---------- Chemistry multiplier --------------------------------------------


def test_chemistry_all_ok_is_one():
    assert _chemistry_multiplier(_OK_BANDS) == 1.0


def test_chemistry_warning_is_1_2():
    bands = {**_OK_BANDS, "ph": "warning_low"}
    assert _chemistry_multiplier(bands) == 1.2


def test_chemistry_warm_treated_as_warning():
    bands = {**_OK_BANDS, "temperature": "warm"}
    assert _chemistry_multiplier(bands) == 1.2


def test_chemistry_saturated_is_1_3():
    bands = {**_OK_BANDS, "production": "saturated"}
    assert _chemistry_multiplier(bands) == 1.3


def test_chemistry_danger_beats_saturated():
    bands = {**_OK_BANDS, "ph": "danger_low", "production": "saturated"}
    assert _chemistry_multiplier(bands) == 1.5


# ---------- Combined recommendation -----------------------------------------


def _ref_input(temp=28, bands=None) -> TimerInput:
    return TimerInput(
        water_temp_c=temp,
        bands=bands or _OK_BANDS,
        volume_m3=37.0,
        nominal_flow_m3_h=12.0,
        target_turnovers_per_day=1.0,
    )


def test_recommended_uses_max_of_base_and_turnover():
    # at 28 °C base=240, turnover=185 → uses 240
    assert recommended_minutes_today(_ref_input(28)) == 240
    # at 18 °C base=60, turnover=185 → uses 185
    assert recommended_minutes_today(_ref_input(18)) == 185


def test_recommended_applies_chemistry_multiplier():
    bands_warn = {**_OK_BANDS, "ph": "warning_low"}
    base_ok = recommended_minutes_today(_ref_input(28, _OK_BANDS))
    base_warn = recommended_minutes_today(_ref_input(28, bands_warn))
    assert base_warn == round(base_ok * 1.2)


def test_recommended_danger_capped_at_1_5():
    bands_danger = {**_OK_BANDS, "ph": "danger_low"}
    base_ok = recommended_minutes_today(_ref_input(28, _OK_BANDS))
    base_danger = recommended_minutes_today(_ref_input(28, bands_danger))
    assert base_danger == round(base_ok * 1.5)


def test_weekly_is_seven_times_daily():
    inp = _ref_input(28)
    assert recommended_minutes_week(inp) == 7 * recommended_minutes_today(inp)


# ---------- Flow lookup -----------------------------------------------------


def test_nominal_flow_unknown_falls_back_to_12():
    assert nominal_flow_for_serial(None) == 12.0
    assert nominal_flow_for_serial("") == 12.0
    assert nominal_flow_for_serial("2101812099010") == 12.0  # reference unit
