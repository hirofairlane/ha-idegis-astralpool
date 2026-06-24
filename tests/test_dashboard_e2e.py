"""End-to-end visualization tests for the *capturer* dashboard.

These render the **real** dashboard (``static/index.html`` + ``app.js``) in a
headless Chromium against the **real** aiohttp app (``build_api_app``) seeded
with fixture captures, then assert on the rendered SVG/DOM.

Why this exists: the Python suites cover the backend contract (codec, session
snapshot schema, …) but nothing exercised ``app.js``. A renderer bug that
poisoned the chart autoscale with ``±Infinity`` band bounds blanked every
vitals chart (NaN path coordinates, ``—`` axis labels) while every backend
test stayed green. This module closes that gap: it would have caught it.

Run locally:
    pip install aiohttp pytest pytest-asyncio playwright
    playwright install chromium      # or rely on a system chromium
    IDEGIS_TESTING=1 pytest tests/test_dashboard_e2e.py -q

The test auto-discovers a browser: it prefers Playwright's bundled Chromium and
falls back to a system ``chromium``/``chromium-browser``/``google-chrome``.
If neither Playwright nor a browser is available the module is skipped, so the
rest of the suite still runs in minimal environments.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("playwright", reason="playwright not installed")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
_IDEGIS_SRC = ROOT / "addon" / "rootfs" / "opt" / "idegis"


# ── Fixture payload encoder ─────────────────────────────────────────────────
# The Idegis B0 codec uses a custom base-10 alphabet (a=0 … X=9) with 'g' as
# the decimal point. We synthesise capture records so the charts have real,
# multi-point series. Validated against codec.decode_field in the test below.
_DIGITS = "abcdefUVWX"


def _enc(value: float, decimals: int, marker: str = "") -> str:
    s = f"{value:.{decimals}f}"
    return "".join("g" if c == "." else _DIGITS[int(c)] for c in s) + marker


def _fields(ph: float, salt: float, temp: float, prod: float) -> dict:
    return {
        "SG": _enc(ph, 2),          # pH (no marker)
        "IT": _enc(salt, 2, "M"),   # salinity g/L
        "CY": _enc(temp, 1, "I"),   # temperature °C
        "GY": _enc(prod, 1),        # production %
    }


# Six motor-on writes spread over the last few hours, each metric moving so the
# series has >= 2 distinct points (the renderer only emits a point on change).
_SAMPLES = [
    # minutes_ago, ph,    salt, temp, prod
    (300, 7.40, 1.50, 34.5, 88.0),
    (240, 7.45, 1.51, 34.6, 89.0),
    (180, 7.48, 1.52, 34.7, 90.0),
    (120, 7.50, 1.52, 34.8, 90.0),
    (60,  7.51, 1.53, 34.8, 91.0),
    (10,  7.49, 1.52, 34.9, 90.0),
]


def _load_capturer(data_dir: pathlib.Path):
    os.environ["IDEGIS_TESTING"] = "1"
    os.environ["IDEGIS_DATA"] = str(data_dir)
    if str(_IDEGIS_SRC) not in sys.path:
        sys.path.insert(0, str(_IDEGIS_SRC))
    spec = importlib.util.spec_from_file_location(
        "idegis_capturer_e2e", _IDEGIS_SRC / "capturer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _launch_browser(p):
    """Prefer the bundled browser; fall back to a system Chromium."""
    try:
        return p.chromium.launch(headless=True)
    except Exception:  # noqa: BLE001 — bundled browser absent (no `playwright install`)
        for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
            path = shutil.which(name)
            if path:
                return p.chromium.launch(headless=True, executable_path=path)
        pytest.skip("no Chromium available for Playwright")


@pytest.fixture(scope="module")
def dashboard(tmp_path_factory):
    """Seed fixtures, start the real dashboard server, yield its base URL."""
    data_dir = tmp_path_factory.mktemp("idegis_e2e")
    cap = _load_capturer(data_dir)

    now = datetime.now(timezone.utc)
    records = []
    for minutes_ago, ph, salt, temp, prod in _SAMPLES:
        ts = (now - timedelta(minutes=minutes_ago)).isoformat()
        records.append({
            "ts": ts,
            "endpoint": "write",
            "fields": _fields(ph, salt, temp, prod),
            "pump_power_w": 1100.0,
            "pump_running": True,
        })

    # 1) Seed the JSONL store the timeseries endpoint reads from.
    cap.JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with cap.JSONL_PATH.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    # 2) Seed the in-memory state (tiles) and a *closed* session (Última sesión).
    for rec in records:
        cap.state.ingest(rec)
    cap.state.force_close_session()

    # 3) Start the real app on an ephemeral port in a background event loop.
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    ready = threading.Event()
    loop = asyncio.new_event_loop()

    def _serve():
        asyncio.set_event_loop(loop)
        from aiohttp import web
        app = cap.build_api_app()
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", port)
        loop.run_until_complete(site.start())
        ready.set()
        loop.run_forever()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    assert ready.wait(timeout=10), "dashboard server did not start"

    yield base

    loop.call_soon_threadsafe(loop.stop)


@pytest.fixture(scope="module")
def page(dashboard):
    """A loaded dashboard page plus a list of console/page errors."""
    errors: list[str] = []
    bad_responses: list[str] = []

    def _on_console(m):
        # Ignore generic "Failed to load resource" network notes (favicon etc.);
        # real HTTP failures are asserted via bad_responses below. We still want
        # JS "Error: <path> ... NaN" style messages here.
        if m.type == "error" and "Failed to load resource" not in m.text:
            errors.append(m.text)

    def _on_response(r):
        if r.status >= 400 and "favicon" not in r.url:
            bad_responses.append(f"{r.status} {r.url}")

    with sync_playwright() as p:
        browser = _launch_browser(p)
        pg = browser.new_page()
        pg.on("console", _on_console)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("response", _on_response)
        pg.goto(dashboard, wait_until="networkidle")
        # Wait until every vitals chart has rendered a line path.
        pg.wait_for_function(
            """() => ['ph','salt','temp','prod'].every(
                k => document.querySelector('#chart-' + k + ' path.line'))""",
            timeout=10000,
        )
        pg.console_errors = errors  # type: ignore[attr-defined]
        pg.bad_responses = bad_responses  # type: ignore[attr-defined]
        yield pg
        browser.close()


# ── Sanity: the encoder produces values the real codec decodes back ─────────

def test_fixture_encoder_roundtrips_through_codec():
    spec = importlib.util.spec_from_file_location("idegis_codec_e2e", _IDEGIS_SRC / "codec.py")
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    fd = codec.decode_field("SG", _enc(7.51, 2))
    assert fd["semantic_name"] == "ph" and fd["decoded"] == pytest.approx(7.51)
    fd = codec.decode_field("IT", _enc(1.52, 2, "M"))
    assert fd["semantic_name"] == "salinity" and fd["decoded"] == pytest.approx(1.52)


# ── The visualization regression tests ──────────────────────────────────────

CHARTS = ["ph", "salt", "temp", "prod"]


@pytest.mark.parametrize("chart", CHARTS)
def test_vitals_chart_draws_a_finite_line(page, chart):
    """Each vitals chart must draw a real polyline with finite coordinates.

    Regression for the ±Infinity band bounds poisoning the autoscale: the line
    path's ``d`` came out as ``M NaN NaN L NaN NaN …`` (an invisible line) and
    the axis labels rendered as ``—``. We assert the path has >= 2 segments and
    contains no ``NaN``.
    """
    d = page.eval_on_selector(f"#chart-{chart} path.line", "el => el.getAttribute('d')")
    assert d, f"{chart}: no line path drawn"
    assert "NaN" not in d, f"{chart}: line path has NaN coordinates -> {d!r}"
    assert d.count("L") + d.count("M") >= 2, f"{chart}: line has < 2 points -> {d!r}"

    # Every command's coordinates must parse as finite floats.
    import re
    nums = re.findall(r"-?\d+\.?\d*", d)
    assert nums, f"{chart}: no numeric coordinates in path"
    assert all(abs(float(n)) < 1e6 for n in nums), f"{chart}: non-finite path coords -> {d!r}"


@pytest.mark.parametrize("chart", CHARTS)
def test_vitals_chart_axis_labels_are_numeric(page, chart):
    """The Y-axis labels must be numbers, not the ``—`` em-dash that the NaN
    range produced."""
    labels = page.eval_on_selector_all(
        f"#chart-{chart} text.axis-label",
        "els => els.map(e => e.textContent)",
    )
    assert labels, f"{chart}: no axis labels rendered"
    numeric = [t for t in labels if t and t not in ("—", "NaN")]
    assert numeric, f"{chart}: all axis labels are '—'/NaN -> {labels!r}"


@pytest.mark.parametrize(
    "tile_id",
    ["ph-now", "salt-now", "temp-now", "prod-now"],
)
def test_vital_tiles_show_numbers(page, tile_id):
    txt = page.eval_on_selector(f"#{tile_id}", "el => el.textContent")
    assert txt and txt.strip() not in ("—", ""), f"{tile_id} empty -> {txt!r}"
    assert any(ch.isdigit() for ch in txt), f"{tile_id} non-numeric -> {txt!r}"


def test_activity_chart_has_bars(page):
    n = page.eval_on_selector_all("#chart-activity rect.bar", "els => els.length")
    assert n >= 1, "activity chart drew no bars"


def test_last_session_panel_is_populated(page):
    """Última sesión must show a closed session with a numeric pH avg.

    Regression-adjacent to the d4f4ba3 snapshot-key rename that blanked this
    panel; now asserted at the render layer too.
    """
    status = page.eval_on_selector("#ses-status", "el => el.textContent")
    assert status and "cerrada" in status, f"session not closed -> {status!r}"
    ph = page.eval_on_selector("#ses-ph", "el => el.textContent")
    assert ph and any(c.isdigit() for c in ph), f"session pH avg empty -> {ph!r}"


def test_no_console_errors(page):
    assert not page.console_errors, f"console errors: {page.console_errors}"


def test_no_failed_api_responses(page):
    """No API endpoint may return >= 400. Regression for /state 500ing on a
    history record without the optional `path` field, which blanked the tiles."""
    assert not page.bad_responses, f"failed responses: {page.bad_responses}"
