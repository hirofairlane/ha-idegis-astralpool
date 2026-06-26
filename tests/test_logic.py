"""Repo-level smoke + regression tests.

These cover the cross-component invariants and the pure logic of the
*capturer* add-on, complementing the in-tree pool-brain suite
(``addon-pool-brain/tests/``).

Scope:
  * codec.py — the Idegis B0 base-10 payload codec. Pure, stdlib-only;
    exercised against the empirically validated examples in its own
    docstring (timestamp, decimals, markers, booleans).
  * capturer.py — imported with IDEGIS_TESTING=1 so it has no import-time
    filesystem side effects. Regression test for the bug where the cloud
    *response* (last_response / last_response_fields) was never captured
    because the capture block had been orphaned into force_close_session()
    referencing an undefined ``record`` (would raise NameError if reached).
  * the HACS integration manifest — required fields, without importing
    Home Assistant.

Run: `IDEGIS_TESTING=1 pytest tests/test_logic.py`
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
from datetime import datetime, timedelta

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _td(**kw) -> timedelta:
    return timedelta(**kw)
_IDEGIS_SRC = ROOT / "addon" / "rootfs" / "opt" / "idegis"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def codec():
    return _load("idegis_codec", _IDEGIS_SRC / "codec.py")


@pytest.fixture(scope="session")
def capturer(tmp_path_factory):
    os.environ["IDEGIS_TESTING"] = "1"
    os.environ["IDEGIS_DATA"] = str(tmp_path_factory.mktemp("idegis_data"))
    # capturer.py does `from codec import ...`, so its dir must be importable.
    import sys

    if str(_IDEGIS_SRC) not in sys.path:
        sys.path.insert(0, str(_IDEGIS_SRC))
    return _load("idegis_capturer", _IDEGIS_SRC / "capturer.py")


# ── codec: base-10 custom alphabet ──────────────────────────────────────────

def test_int_base10_simple(codec):
    # a=0 b=1 c=2 ... -> "bc" == 12
    assert codec.int_base10("bc") == 12


def test_int_base10_full_alphabet(codec):
    assert codec.int_base10("abcdefUVWX") == 123456789  # noqa: leading 0 dropped


def test_int_base10_bad_char_returns_none(codec):
    assert codec.int_base10("zz") is None


def test_int_base10_empty_returns_none(codec):
    assert codec.int_base10("") is None


# ── codec: decimals + markers ───────────────────────────────────────────────

def test_decode_decimal_no_point(codec):
    assert codec.decode_decimal("be") == 14.0  # b=1 e=4


def test_decode_decimal_with_point(codec):
    # f g Wb -> 5.81  (f=5, g=point, W=8 b=1)
    assert codec.decode_decimal("fgWb") == pytest.approx(5.81)


def test_split_marker_strips_unit(codec):
    num, marker = codec.split_marker("adbgcM")  # trailing M is a unit marker
    assert marker == "M"
    assert num == "adbgc"


def test_decode_value_returns_number_and_marker(codec):
    num, marker = codec.decode_value("adbgcM")
    assert marker == "M"
    assert num == pytest.approx(31.2)  # adb -> 031 == 31; g (point); c=2 -> .2


# ── codec: semantic field decode (the documented, validated examples) ───────

def test_decode_field_timestamp(codec):
    # Docstring-validated: 'bVWaedfcbc' -> 1780435212 (Unix seconds, UTC).
    fd = codec.decode_field("CD", "bVWaedfcbc")
    assert fd["decoded"] == 1780435212.0
    assert fd["as_iso_utc"].startswith("2026-06-02T")


def test_decode_field_bool(codec):
    fd = codec.decode_field("9C", "b")  # b == 1 -> True
    assert fd["type"] == "bool"
    assert fd["bool"] is True


def test_decode_field_empty_value(codec):
    fd = codec.decode_field("SG", "")
    assert fd["decoded"] is None


def test_decode_fields_skips_dunder(codec):
    out = codec.decode_fields({"__prefix__": "x", "9C": "b"})
    assert "__prefix__" not in out
    assert "9C" in out


def test_summarise_measurements_keeps_only_measures(codec):
    decoded = codec.decode_fields({"SG": "Ugfb", "LI": "bc"})  # SG=measure, LI=counter
    summary = codec.summarise_measurements(decoded)
    assert set(summary) == {"ph"}
    assert summary["ph"]["unit"] == "pH"


# ── capturer: importable without side effects, version exposed ──────────────

def test_capturer_imports_and_version(capturer):
    assert capturer.ADDON_VERSION == "0.6.12"


def test_capturer_data_dir_is_temp(capturer):
    # Must honour IDEGIS_DATA, not the hardcoded /data.
    assert not str(capturer.JSONL_PATH).startswith("/data/")


# ── capturer: regression — cloud response capture in ingest() ───────────────

def test_ingest_captures_last_response(capturer):
    """The cloud reply (response body + fields) must be captured by ingest().

    Regression for the orphaned capture block that lived in
    force_close_session() referencing an undefined `record`: last_response
    was therefore never populated for the /last_response API.
    """
    st = capturer.State()
    assert st.last_response is None
    st.ingest(
        {
            "ts": "2026-06-02T21:20:12+00:00",
            "endpoint": "write",
            "fields": {},
            "response_body_b64": "YWJj",
            "response_size_bytes": 3,
            "response_fields": {"GY": "ce"},
        }
    )
    assert st.last_response is not None
    assert st.last_response["body_b64"] == "YWJj"
    assert st.last_response["endpoint"] == "write"
    assert st.last_response_fields == {"GY": "ce"}


def test_ingest_no_response_leaves_last_response_none(capturer):
    st = capturer.State()
    st.ingest({"ts": "2026-06-02T21:20:12+00:00", "endpoint": "read", "fields": {}})
    assert st.last_response is None


def test_force_close_session_does_not_crash(capturer):
    """Regression: force_close_session() used to reference undefined names
    (record / ep) and would raise NameError once a session was open."""
    from datetime import datetime, timezone

    st = capturer.State()
    now = datetime.now(timezone.utc)
    st.current_session["last_ts"] = now
    st.current_session["n_writes"] = 1
    st.force_close_session()  # must not raise
    assert st.current_session["n_writes"] == 0


def test_closed_session_snapshot_schema(capturer):
    """The closed-session snapshot must expose the schema the dashboard
    renderers consume: a ``measurements`` map keyed by the codec's *semantic*
    names (ph / salinity / temperature / production_percent), plus
    ``duration_s`` and ``last_ts``.

    Regression for the d4f4ba3 codec-key rename: the snapshot started
    emitting semantic keys (ph, …) under ``measurements`` while both
    consumers (app.js + the desktop HTML in show_status) still read the old
    ``aggregates`` map keyed by raw codec codes (SG/IT/CY/GY) and
    ``duration_seconds`` — so "Última sesión" rendered blank and the UI
    permanently showed "ninguna sesión cerrada todavía".
    """
    st = capturer.State()
    # Two writes carrying pH (SG) and temperature (CY); IT/GY absent.
    st.ingest({
        "ts": "2026-06-02T21:20:00+00:00", "endpoint": "write",
        "fields": {"SG": "Ugfb", "CY": "adbgcI"},
    })
    st.ingest({
        "ts": "2026-06-02T21:25:00+00:00", "endpoint": "write",
        "fields": {"SG": "Ugfc", "CY": "adbgdI"},
    })
    assert st.last_session_closed is None  # still open
    st.force_close_session()

    snap = st.last_session_closed
    assert snap is not None
    # The contract the renderers depend on:
    assert "measurements" in snap and "aggregates" not in snap
    assert "duration_s" in snap and "duration_seconds" not in snap
    assert "last_ts" in snap
    # Measurements keyed by semantic names, not raw codec codes.
    assert set(snap["measurements"]) == {"ph", "temperature"}
    assert "SG" not in snap["measurements"]
    ph = snap["measurements"]["ph"]
    assert ph["n"] == 2 and ph["avg"] is not None
    assert snap["duration_s"] == pytest.approx(300.0)  # 5 min between writes
    assert snap["n_writes"] == 2


# ── capturer: slow-metric carry-forward in the session snapshot ─────────────

def test_session_snapshot_carries_slow_metrics(capturer):
    """Salinity/production are emitted only every few hours, so a session can
    capture zero samples for them. The snapshot must fall back to the last-known
    (sticky) value flagged `carried`, instead of dropping the metric — which
    rendered "Sal avg"/"Prod avg" as "—". Regression for the 2026-06-25 report.
    """
    st = capturer.State()
    # Session 1: a write carrying pH (SG) + salinity (IT). Salinity enters
    # sticky here and never appears in a write again.
    st.ingest({"ts": "2026-06-02T10:00:00+00:00", "endpoint": "write",
               "fields": {"SG": "Vgfb", "IT": "bgfcM"}})
    st.force_close_session()
    # Session 2: only pH reported across two writes — no salinity sample.
    st.ingest({"ts": "2026-06-02T11:00:00+00:00", "endpoint": "write",
               "fields": {"SG": "Vgfb"}})
    st.ingest({"ts": "2026-06-02T11:05:00+00:00", "endpoint": "write",
               "fields": {"SG": "Vgfc"}})
    st.force_close_session()

    snap = st.last_session_closed
    assert "salinity" in snap["measurements"], "salinity dropped from session 2"
    sal = snap["measurements"]["salinity"]
    assert sal["carried"] is True and sal["avg"] is not None
    # pH was really measured this session — must NOT be flagged carried.
    assert snap["measurements"]["ph"].get("carried") is not True


def test_backfill_sticky_from_full_store(capturer):
    """Salinity reported >MAX_HISTORY records ago falls outside the warm replay
    window. The backfill must scan the full store so sticky keeps the last-known
    value (otherwise the session snapshot has nothing to carry forward)."""
    st = capturer.State()
    # Simulate a replay that only re-hydrated recent pH/temperature writes.
    st.sticky_fields = {"SG": "Vgfb", "CY": "degWI"}
    lines = [
        # Oldest line carries salinity (IT) + production (GY); newer ones don't.
        '{"ts":"2026-06-01T00:00:00+00:00","endpoint":"write","fields":{"IT":"bgfcM","GY":"Xaga"}}',
        '{"ts":"2026-06-02T00:00:00+00:00","endpoint":"write","fields":{"SG":"Vgfb"}}',
        '{"ts":"2026-06-02T01:00:00+00:00","endpoint":"read","fields":{"CI":"a"}}',
    ]
    capturer._backfill_sticky_measurements(lines, st)
    assert "IT" in st.sticky_fields and "GY" in st.sticky_fields
    carry = capturer.State._carry_from(st.sticky_fields)
    assert "salinity" in carry and "production_percent" in carry


# ── capturer: persistent store location + legacy migration ──────────────────

def test_capture_store_not_in_data_volume(capturer):
    """The store must not live in the add-on's volatile /data volume — that
    is wiped on uninstall / slug migration (how the corpus was lost once).
    The legacy pointer, by contrast, intentionally points at /data."""
    assert "captures" in str(capturer.JSONL_PATH)
    assert not str(capturer.JSONL_PATH).startswith("/data/")
    assert str(capturer._LEGACY_JSONL) == "/data/captures/idegis_full.jsonl"


def test_migrate_legacy_store(capturer, tmp_path, monkeypatch):
    """Upgrading from <=0.6.7 must carry the old /data store forward, and the
    migration must be idempotent and non-destructive."""
    new = tmp_path / "share" / "captures" / "idegis_full.jsonl"
    legacy = tmp_path / "data" / "captures" / "idegis_full.jsonl"
    new.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"ts":"2026-06-01T00:00:00+00:00","endpoint":"read"}\n')
    monkeypatch.setattr(capturer, "JSONL_PATH", new)
    monkeypatch.setattr(capturer, "_LEGACY_JSONL", legacy)

    capturer._migrate_legacy_store()
    assert new.exists()
    assert new.read_text() == legacy.read_text()  # copied forward
    assert legacy.exists()  # not destructive

    # Idempotent: a second run must not clobber a store that now has new data.
    new.write_text("NEWER\n")
    capturer._migrate_legacy_store()
    assert new.read_text() == "NEWER\n"


def test_migrate_legacy_store_noop_without_legacy(capturer, tmp_path, monkeypatch):
    new = tmp_path / "captures" / "idegis_full.jsonl"
    monkeypatch.setattr(capturer, "JSONL_PATH", new)
    monkeypatch.setattr(capturer, "_LEGACY_JSONL", tmp_path / "nope.jsonl")
    capturer._migrate_legacy_store()  # must not raise
    assert not new.exists()


# ── capturer: time-of-use tariff + solar/grid cost split ────────────────────

def _ph(ts_iso, w):
    return {"last_changed": ts_iso, "state": str(w)}


def test_tariff_period_weekday(capturer):
    # 2026-01-15 is a Thursday. Madrid is UTC+1 in January.
    f = capturer.tariff_period
    assert f(_dt("2026-01-15T11:00:00+00:00")) == "peak"      # 12:00 Madrid
    assert f(_dt("2026-01-15T03:00:00+00:00")) == "valley"    # 04:00 Madrid
    assert f(_dt("2026-01-15T08:30:00+00:00")) == "mid"       # 09:30 Madrid


def test_tariff_period_weekend_is_valley(capturer):
    # 2026-01-17 is a Saturday — valley all day even at a peak hour.
    assert capturer.tariff_period(_dt("2026-01-17T11:00:00+00:00")) == "valley"


def test_tariff_price_matches_period(capturer):
    assert capturer.tariff_price(_dt("2026-01-15T11:00:00+00:00")) == capturer.TARIFF["peak"]


def test_cost_breakdown_all_grid_without_sensor(capturer):
    """No grid sensor -> everything is grid, priced by ToU period."""
    t0 = _dt("2026-01-15T11:00:00+00:00")  # peak
    pump = [_ph("2026-01-15T11:00:00+00:00", 1000), _ph("2026-01-15T12:00:00+00:00", 0)]
    b = capturer.cost_breakdown(
        pump, [], t0 - _td(hours=1), t0 + _td(hours=2), cap_seconds=7200
    )
    assert b["grid_kwh"] == pytest.approx(1.0, abs=1e-6)
    assert b["solar_kwh"] == 0.0
    assert b["grid_eur"] == pytest.approx(capturer.TARIFF["peak"], abs=1e-4)
    assert b["by_period_eur"]["peak"] == pytest.approx(capturer.TARIFF["peak"], abs=1e-4)
    assert b["solar_pct"] == 0.0


def test_cost_breakdown_solar_when_exporting(capturer):
    """House exporting (PV surplus) at run time -> solar, 0 € grid cost."""
    t0 = _dt("2026-01-15T11:00:00+00:00")
    pump = [_ph("2026-01-15T11:00:00+00:00", 1000), _ph("2026-01-15T12:00:00+00:00", 0)]
    grid = [_ph("2026-01-15T10:59:00+00:00", 2000)]  # +2000 W = exporting
    b = capturer.cost_breakdown(
        pump, grid, t0 - _td(hours=1), t0 + _td(hours=2), cap_seconds=7200
    )
    assert b["solar_kwh"] == pytest.approx(1.0, abs=1e-6)
    assert b["grid_kwh"] == 0.0
    assert b["grid_eur"] == 0.0
    assert b["solar_export_value_eur"] == pytest.approx(capturer.TARIFF["export"], abs=1e-4)
    assert b["solar_pct"] == 100.0


def test_cost_breakdown_grid_when_importing(capturer):
    t0 = _dt("2026-01-15T11:00:00+00:00")
    pump = [_ph("2026-01-15T11:00:00+00:00", 1000), _ph("2026-01-15T12:00:00+00:00", 0)]
    grid = [_ph("2026-01-15T10:59:00+00:00", -500)]  # -500 W = importing
    b = capturer.cost_breakdown(
        pump, grid, t0 - _td(hours=1), t0 + _td(hours=2), cap_seconds=7200
    )
    assert b["grid_kwh"] == pytest.approx(1.0, abs=1e-6)
    assert b["grid_eur"] == pytest.approx(capturer.TARIFF["peak"], abs=1e-4)
    assert b["solar_kwh"] == 0.0


# ── HACS integration manifest (no Home Assistant import needed) ─────────────

def test_manifest_has_required_fields():
    manifest = json.loads(
        (ROOT / "custom_components" / "idegis_astralpool" / "manifest.json").read_text()
    )
    assert manifest["domain"] == "idegis_astralpool"
    assert manifest["version"]  # non-empty
    assert manifest["config_flow"] is True


def test_hacs_json_valid():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs.get("name")
