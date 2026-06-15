"""Tests for the ring-buffer time series store."""
from __future__ import annotations

from history import DEFAULT_CAPACITY, History, Series


def test_series_keeps_capacity():
    s = Series(capacity=3)
    for v in [1, 2, 3, 4, 5]:
        s.push(v)
    assert s.as_list() == [3, 4, 5]


def test_series_accepts_none():
    s = Series(capacity=4)
    s.push(None)
    s.push(1.0)
    s.push(None)
    assert s.as_list() == [None, 1.0, None]


def test_history_decimation_skips_intermediate_samples():
    h = History(capacity=10, decimation=3)
    # First two calls are decimated, third commits.
    assert h.record({"ph": 7.4}) is False
    assert h.record({"ph": 7.4}) is False
    assert h.record({"ph": 7.4}) is True
    assert h.series["ph"].as_list() == [7.4]


def test_history_records_multiple_metrics():
    h = History(capacity=5, decimation=1)
    h.record({"ph": 7.2, "salt": 2.5})
    h.record({"ph": 7.3, "salt": 2.6})
    snap = h.snapshot()
    assert snap["ph"] == [7.2, 7.3]
    assert snap["salt"] == [2.5, 2.6]


def test_history_capacity_enforced_per_metric():
    h = History(capacity=2, decimation=1)
    for v in range(5):
        h.record({"ph": v})
    assert h.series["ph"].as_list() == [3, 4]


def test_history_defaults_make_sense():
    h = History()
    assert h.capacity == DEFAULT_CAPACITY
    assert h.decimation > 0


def test_snapshot_is_a_copy_not_a_reference():
    h = History(capacity=5, decimation=1)
    h.record({"ph": 7.0})
    snap = h.snapshot()
    h.record({"ph": 7.1})
    assert snap["ph"] == [7.0]  # snapshot was a copy

    # Just for sanity: the live view did change.
    assert h.series["ph"].as_list() == [7.0, 7.1]
