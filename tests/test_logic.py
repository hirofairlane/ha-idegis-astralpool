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

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
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
    assert capturer.ADDON_VERSION == "0.6.6"


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
