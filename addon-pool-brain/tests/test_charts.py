"""Smoke tests for the matplotlib-based chart generators.

We don't try to verify pixel layout — just that:
- The functions return a non-empty base64 string for realistic input.
- They survive empty / None-filled input without crashing.

Matplotlib is heavy; if it's not installed in the test environment the
suite skips these tests rather than fail.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

matplotlib = pytest.importorskip("matplotlib")

import charts  # noqa: E402


def _seven_day_history(values):
    today = date.today()
    return {
        (today - timedelta(days=6 - i)).isoformat(): v
        for i, v in enumerate(values)
    }


def test_runtime_7d_returns_b64():
    history = _seven_day_history([120, 0, 180, 60, 240, 180, 60])
    png = charts.runtime_7d(history)
    assert isinstance(png, str)
    assert len(png) > 100  # base64 of a real PNG, not empty


def test_runtime_7d_handles_empty():
    png = charts.runtime_7d({})
    assert isinstance(png, str)
    assert len(png) > 100


def test_health_7d_returns_b64():
    history = _seven_day_history([90, 85, 80, 60, 95, 100, 88])
    png = charts.health_7d(history)
    assert isinstance(png, str)
    assert len(png) > 100


def test_health_7d_handles_sparse():
    today = date.today()
    history = {today.isoformat(): 75}
    png = charts.health_7d(history)
    assert isinstance(png, str)
    assert len(png) > 100


def test_vitals_24h_returns_b64():
    snap = {
        "ph": [7.2, 7.3, 7.4, 7.4, 7.5, 7.5, 7.4],
        "salt_g_l": [2.5, 2.5, 2.6, 2.6, 2.5, 2.5, 2.4],
        "temperature_c": [28.0, 28.5, 29.0, 29.5, 30.0, 30.0, 29.8],
    }
    png = charts.vitals_24h(snap)
    assert isinstance(png, str)
    assert len(png) > 100


def test_vitals_24h_handles_all_none_series():
    snap = {
        "ph": [None] * 10,
        "salt_g_l": [],
        "temperature_c": [],
    }
    png = charts.vitals_24h(snap)
    assert isinstance(png, str)
    assert len(png) > 100
