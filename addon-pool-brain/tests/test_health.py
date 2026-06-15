"""Tests for the TFP bands and the weighted health score.

Cover every boundary of every band so we don't get caught by a wrong
inequality, and a handful of representative full-snapshot inputs for
the weighted score.
"""
from __future__ import annotations

import pytest

from health import (
    HealthInput,
    all_ok,
    health_score,
    ph_band,
    production_band,
    salt_band,
    temperature_band,
)


# ---------- pH ---------------------------------------------------------------


@pytest.mark.parametrize(
    "ph,expected",
    [
        (None, "unknown"),
        (6.79, "danger_low"),
        (6.8, "warning_low"),
        (7.19, "warning_low"),
        (7.2, "ok"),
        (7.5, "ok"),
        (7.8, "ok"),
        (7.81, "warning_high"),
        (8.2, "warning_high"),
        (8.21, "danger_high"),
        (9.0, "danger_high"),
    ],
)
def test_ph_band(ph, expected):
    assert ph_band(ph) == expected


# ---------- Salt (low-salt Neolysis range) ----------------------------------


@pytest.mark.parametrize(
    "salt,expected",
    [
        (None, "unknown"),
        (0.0, "danger_low"),
        (0.99, "danger_low"),
        (1.0, "warning_low"),
        (1.49, "warning_low"),
        (1.5, "ok"),
        (2.5, "ok"),
        (3.5, "ok"),
        (3.51, "warning_high"),
        (5.0, "warning_high"),
        (5.01, "danger_high"),
        (10.0, "danger_high"),
    ],
)
def test_salt_band(salt, expected):
    assert salt_band(salt) == expected


# ---------- Temperature ------------------------------------------------------


@pytest.mark.parametrize(
    "temp,expected",
    [
        (None, "unknown"),
        (19.9, "warning_low"),
        (20.0, "ok"),
        (32.0, "ok"),
        (32.5, "warm"),
        (36.0, "warm"),
        (36.01, "hot"),
    ],
)
def test_temperature_band(temp, expected):
    assert temperature_band(temp) == expected


# ---------- Production ------------------------------------------------------


@pytest.mark.parametrize(
    "p,expected",
    [
        (None, "unknown"),
        (0, "ok"),
        (50, "ok"),
        (95, "ok"),
        (95.1, "saturated"),
        (100, "saturated"),
    ],
)
def test_production_band(p, expected):
    assert production_band(p) == expected


# ---------- Weighted score ---------------------------------------------------


def _perfect():
    return HealthInput(
        ph=7.4,
        salt_g_l=2.5,
        temperature_c=28.0,
        production_pct=50.0,
        pump_anomaly=False,
        cleaner_anomaly=False,
    )


def test_perfect_inputs_score_100():
    score, bands = health_score(_perfect())
    assert score == 100
    assert all_ok(bands)


def test_pump_anomaly_costs_15_points():
    snap = _perfect()
    snap = HealthInput(
        ph=snap.ph,
        salt_g_l=snap.salt_g_l,
        temperature_c=snap.temperature_c,
        production_pct=snap.production_pct,
        pump_anomaly=True,
        cleaner_anomaly=False,
    )
    score, _ = health_score(snap)
    assert score == 85


def test_ph_danger_drops_score_under_80():
    snap = HealthInput(
        ph=6.0,  # danger_low
        salt_g_l=2.5,
        temperature_c=28.0,
        production_pct=50.0,
        pump_anomaly=False,
        cleaner_anomaly=False,
    )
    score, bands = health_score(snap)
    assert bands["ph"] == "danger_low"
    assert score < 80
    assert not all_ok(bands)


def test_temperature_warm_still_high_score():
    snap = HealthInput(
        ph=7.4,
        salt_g_l=2.5,
        temperature_c=34.0,  # warm
        production_pct=50.0,
        pump_anomaly=False,
        cleaner_anomaly=False,
    )
    score, bands = health_score(snap)
    assert bands["temperature"] == "warm"
    # warm penalises 20 pts at 10% weight = 2 pts off
    assert 95 <= score <= 99


def test_saturated_production_penalises():
    snap = HealthInput(
        ph=7.4,
        salt_g_l=2.5,
        temperature_c=28.0,
        production_pct=99.0,  # saturated
        pump_anomaly=False,
        cleaner_anomaly=False,
    )
    score, bands = health_score(snap)
    assert bands["production"] == "saturated"
    # saturated penalises 40 pts at 25% weight = 10 pts off
    assert score == 90


def test_unknown_inputs_dont_explode():
    snap = HealthInput(
        ph=None,
        salt_g_l=None,
        temperature_c=None,
        production_pct=None,
        pump_anomaly=False,
        cleaner_anomaly=False,
    )
    score, bands = health_score(snap)
    assert all(v == "unknown" for v in bands.values())
    # unknown maps to 50 points; perfect would have been 100, so the
    # score with all-unknown should land around 50-65 range.
    assert 40 <= score <= 75


def test_all_ok_requires_every_band_ok():
    assert all_ok({"ph": "ok", "salt": "ok", "temperature": "ok", "production": "ok"})
    assert not all_ok({"ph": "ok", "salt": "ok", "temperature": "warm", "production": "ok"})
    assert not all_ok({"ph": "ok", "salt": "ok", "temperature": "ok", "production": "saturated"})
