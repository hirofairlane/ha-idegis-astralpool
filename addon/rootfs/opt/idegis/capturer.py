"""Idegis capturer — full Python proxy + API.

Two responsibilities running in a single aiohttp application:

1. Port 80 — transparent reverse proxy.
   Every request the chlorinator sends to api.idegis.net lands here.
   We forward it to the real Imperva-fronted backend (literal IP from
   options.json) and stream the response back. While doing so we
   capture both the request URL (with the B0 / H parameters) and the
   raw response body (176 bytes on /read.php — the cloud's reply to
   the device, where the setpoints/commands live).

2. Port 8765 — JSON API for the Home Assistant integration.
   /api/idegis/health, /state, /history, /analyze, /last_response.

Persistent history is appended as JSON-Lines to
/data/captures/idegis_full.jsonl so it survives add-on restarts and can
be reprocessed offline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, TCPConnector, web

from codec import decode_field, decode_fields, summarise_measurements  # noqa: E402

# ---------- Configuration --------------------------------------------------

_OPTIONS_FILE = Path("/data/options.json")

DEFAULTS = {
    "upstream_host": "45.60.153.189",
    "upstream_host_header": "api.idegis.net",
    "log_level": "info",
    "max_history": 1000,
    "online_timeout_s": 90,
    "pump_power_entity": "sensor.shellypro4pm_30c6f7836a6c_power_3",
    "cleaner_power_entity": "sensor.shellypro4pm_30c6f7836a6c_power_1",
    "pump_switch_entity": "switch.depuradora",
    "cleaner_switch_entity": "switch.limpiafondos",
    "pool_volume_m3": 37.0,
    "pump_nominal_flow_m3_h": 12.0,
    "energy_price_eur_kwh": 0.18,
    "cell_capacity_g_h": 24.0,
    "target_production_pct": 100,
    "chlorine_demand_ppm_per_day": 1.0,
    "min_turnovers_per_day": 0.5,
    "indoor_pool": True,
    "pump_running_threshold_w": 1.0,
    "pump_poll_interval_s": 5,
}


def load_options() -> dict[str, Any]:
    opts = dict(DEFAULTS)
    if _OPTIONS_FILE.exists():
        try:
            opts.update(json.loads(_OPTIONS_FILE.read_text()))
        except Exception:  # noqa: BLE001
            pass
    return opts


OPTS = load_options()

UPSTREAM_HOST = OPTS["upstream_host"]
UPSTREAM_HOST_HEADER = OPTS["upstream_host_header"]
MAX_HISTORY = int(OPTS["max_history"])
ONLINE_TIMEOUT_S = int(OPTS["online_timeout_s"])
PUMP_ENTITY = OPTS.get("pump_power_entity") or ""
CLEANER_ENTITY = OPTS.get("cleaner_power_entity") or ""
PUMP_SWITCH_ENTITY = OPTS.get("pump_switch_entity") or ""
CLEANER_SWITCH_ENTITY = OPTS.get("cleaner_switch_entity") or ""
POOL_VOLUME_M3 = float(OPTS.get("pool_volume_m3") or 37.0)
PUMP_NOMINAL_FLOW_M3_H = float(OPTS.get("pump_nominal_flow_m3_h") or 12.0)
ENERGY_PRICE_EUR_KWH = float(OPTS.get("energy_price_eur_kwh") or 0.18)
CELL_CAPACITY_G_H = float(OPTS.get("cell_capacity_g_h") or 24.0)
TARGET_PRODUCTION_PCT = int(OPTS.get("target_production_pct") or 100)
CHLORINE_DEMAND_PPM_PER_DAY = float(OPTS.get("chlorine_demand_ppm_per_day") or 1.0)
MIN_TURNOVERS_PER_DAY = float(OPTS.get("min_turnovers_per_day") or 0.5)
INDOOR_POOL = bool(OPTS.get("indoor_pool") if OPTS.get("indoor_pool") is not None else True)
PUMP_THRESHOLD_W = float(OPTS.get("pump_running_threshold_w") or 100.0)
PUMP_POLL_S = int(OPTS.get("pump_poll_interval_s") or 5)

# Supervisor injects these when homeassistant_api is true.
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HASS_API = "http://supervisor/core/api"

JSONL_PATH = Path("/data/captures/idegis_full.jsonl")
JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=OPTS["log_level"].upper(),
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("idegis_capturer")

# ---------- B0 decomposition ----------------------------------------------

FIELD_SEP = "4fU0W430"
KV_SEP = "4fUX2d24"


def split_b0(b0: str) -> dict[str, str]:
    parts = b0.split(FIELD_SEP)
    out: dict[str, str] = {"__prefix__": parts[0]}
    for p in parts[1:]:
        if KV_SEP in p:
            k, _, v = p.partition(KV_SEP)
            out[k] = v
        else:
            out[f"__bare_{len(out)}__"] = p
    return out


REQ_RE = re.compile(r"^/interface/(?P<endpoint>\w+)\.php$")

# ---------- In-memory state ------------------------------------------------


SESSION_IDLE_TIMEOUT_S = 1800  # 30 min fallback only (idle close)
# A session is primarily delimited by the pump_running edges (the
# chlorinator keeps sending writes with measurements even on standby,
# so silence-based closing is unreliable). The timeout above only
# kicks in when there are no pump_running transitions for that long.


class State:
    @staticmethod
    def _empty_session() -> dict[str, Any]:
        return {
            "start_ts": None,
            "last_ts": None,
            "n_writes": 0,
            "measurements": {},  # metric -> {n, sum, min, max, last}
        }

    def __init__(self) -> None:
        self.history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self.read_count = 0
        self.write_count = 0
        self.last_seen: datetime | None = None
        self.last_fields: dict[str, str] = {}
        # Only updated when a write.php arrives (where measurements live)
        self.last_write_fields: dict[str, str] = {}
        # Sticky per-field last-known value: each Bn field keeps the
        # most recent value we have ever seen for it, even if the
        # next requests omit it. This is how we keep the measurements
        # populated when individual writes only carry a subset.
        self.sticky_fields: dict[str, str] = {}
        self.sticky_field_ts: dict[str, datetime] = {}
        # Session tracking: a 'session' is a contiguous stretch of
        # write.php requests carrying measurements. We open one when a
        # measurement-bearing write arrives after >IDLE_S of silence,
        # accumulate per-metric samples while it stays active, and
        # close it (stashing the stats into `last_session_closed`)
        # when no new measurements arrive for IDLE_S seconds.
        self.current_session: dict[str, Any] = self._empty_session()
        self.last_session_closed: dict[str, Any] | None = None
        self.last_response: dict | None = None  # body of latest cloud response
        self.last_response_fields: dict[str, str] = {}
        self.device_id: str | None = None
        self.session_token: str | None = None
        self.first_seen_session: datetime | None = None
        # Pump correlation (filled by background HA poller)
        self.pump_power_w: float | None = None
        self.pump_running: bool = False
        self.pump_last_check: datetime | None = None
        self.pump_running_since: datetime | None = None
        self.pump_entity_state: str | None = None

    def ingest(self, record: dict) -> None:
        self.history.append(record)
        ts = datetime.fromisoformat(record["ts"])
        self.last_seen = ts
        if self.first_seen_session is None:
            self.first_seen_session = ts
        fields = record.get("fields") or {}
        if fields:
            self.last_fields = fields
            if not self.device_id:
                self.device_id = fields.get("__prefix__")
            if not self.session_token:
                self.session_token = fields.get("TD")
        ep = record.get("endpoint")
        if ep == "read":
            self.read_count += 1
        elif ep == "write":
            self.write_count += 1
            if fields:
                self.last_write_fields = fields
                # Merge each field individually into sticky state.
                for k, v in fields.items():
                    if k.startswith("__"):
                        continue
                    self.sticky_fields[k] = v
                    self.sticky_field_ts[k] = ts
                # Session tracking. Decode the measurements that this
                # write carries and accumulate them into the open
                # session (or open a new one).
                ms = summarise_measurements(decode_fields(fields))
                if ms:
                    self._roll_session(ts)
                    self.current_session["last_ts"] = ts
                    if self.current_session["start_ts"] is None:
                        self.current_session["start_ts"] = ts
                    self.current_session["n_writes"] += 1
                    for name, payload in ms.items():
                        val = payload.get("value")
                        if val is None:
                            continue
                        agg = self.current_session["measurements"].setdefault(
                            name,
                            {"n": 0, "sum": 0.0, "min": val, "max": val,
                             "last": val, "unit": payload.get("unit")},
                        )
                        agg["n"] += 1
                        agg["sum"] += val
                        agg["min"] = min(agg["min"], val)
                        agg["max"] = max(agg["max"], val)
                        agg["last"] = val

    def _roll_session(self, ts: datetime) -> None:
        """Close the current session if it's been idle too long."""
        last = self.current_session.get("last_ts")
        if last is None:
            return
        if (ts - last).total_seconds() < SESSION_IDLE_TIMEOUT_S:
            return
        # Idle too long — snapshot and reset.
        self.last_session_closed = self._snapshot_session(self.current_session)
        self.current_session = self._empty_session()

    @staticmethod
    def _snapshot_session(s: dict[str, Any]) -> dict[str, Any]:
        out = {
            "start_ts": s["start_ts"].isoformat() if s["start_ts"] else None,
            "last_ts": s["last_ts"].isoformat() if s["last_ts"] else None,
            "duration_s": (
                (s["last_ts"] - s["start_ts"]).total_seconds()
                if s["start_ts"] and s["last_ts"] else None
            ),
            "n_writes": s["n_writes"],
            "measurements": {},
        }
        for name, agg in s["measurements"].items():
            n = agg["n"]
            out["measurements"][name] = {
                "n": n,
                "avg": agg["sum"] / n if n else None,
                "min": agg["min"],
                "max": agg["max"],
                "last": agg["last"],
                "unit": agg.get("unit"),
            }
        return out

    def close_session_if_idle(self, now: datetime) -> None:
        """External hook: called periodically by a background task."""
        s = self.current_session
        if s.get("last_ts") is None or s["n_writes"] == 0:
            return
        if (now - s["last_ts"]).total_seconds() >= SESSION_IDLE_TIMEOUT_S:
            self.last_session_closed = self._snapshot_session(s)
            self.current_session = self._empty_session()

    def force_close_session(self) -> None:
        """External hook: close the current session immediately
        (called when the pump goes off — pump-edge has priority over
        the idle-timeout heuristic)."""
        s = self.current_session
        if s.get("last_ts") is None or s["n_writes"] == 0:
            return
        self.last_session_closed = self._snapshot_session(s)
        self.current_session = self._empty_session()

        if record.get("response_body_b64"):
            self.last_response = {
                "ts": record["ts"],
                "endpoint": ep,
                "size_bytes": record.get("response_size_bytes"),
                "body_b64": record["response_body_b64"],
                "fields": record.get("response_fields"),
            }
        rfields = record.get("response_fields")
        if rfields:
            # Merge response fields too — these are what the cloud told
            # the device to do next.
            self.last_response_fields = rfields


state = State()


def append_jsonl(record: dict) -> None:
    try:
        with JSONL_PATH.open("a") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to append to jsonl: %s", exc)


def warm_from_jsonl() -> None:
    if not JSONL_PATH.exists():
        return
    try:
        lines = JSONL_PATH.read_text().splitlines()
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to read jsonl: %s", exc)
        return
    for line in lines[-MAX_HISTORY:]:
        try:
            state.ingest(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    log.info("warmed %d records from %s", len(state.history), JSONL_PATH)


# ---------- HTTP proxy on port 80 ------------------------------------------

import base64


async def proxy_handler(request: web.Request) -> web.StreamResponse:
    """Forward every request to the real cloud backend."""
    method = request.method
    path = request.path
    qs = request.rel_url.query_string
    url = f"http://{UPSTREAM_HOST}{path}"
    if qs:
        url = f"{url}?{qs}"

    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    headers["Host"] = UPSTREAM_HOST_HEADER
    headers["X-Forwarded-For"] = request.remote or ""

    body = await request.read()
    ts = datetime.now(timezone.utc)

    upstream_status: int | None = None
    upstream_body: bytes = b""
    upstream_time_s: float | None = None
    err: str | None = None

    started = asyncio.get_event_loop().time()
    try:
        client: ClientSession = request.app["http_client"]
        async with client.request(
            method, url, headers=headers, data=body, allow_redirects=False,
        ) as resp:
            upstream_status = resp.status
            upstream_body = await resp.read()
        upstream_time_s = asyncio.get_event_loop().time() - started
    except Exception as exc:  # noqa: BLE001
        err = repr(exc)
        log.warning("upstream error: %s", err)

    # Build record
    m = REQ_RE.match(path)
    endpoint = m.group("endpoint") if m else None
    h = request.rel_url.query.get("H")

    # The chlorinator may split its payload across B0/B1/B2/... when it
    # gets too large for a single GET parameter. Concatenate them in
    # order before decomposing into fields. We pick up any Bn key with
    # a single decimal digit.
    chunks: list[tuple[int, str]] = []
    for k, v in request.rel_url.query.items():
        if len(k) == 2 and k[0] == "B" and k[1].isdigit():
            chunks.append((int(k[1]), v))
    chunks.sort()
    b0 = "".join(c[1] for c in chunks) if chunks else None
    fields = split_b0(b0) if b0 else None

    # Also try to parse the response body if it looks like a B0=...&H=...
    # payload (the cloud replies in the same format).
    response_fields = None
    response_h = None
    if upstream_body and upstream_body[:5] in (b"00#B0", b"00#B1") or (
        upstream_body and b"B0=" in upstream_body[:10]
    ):
        try:
            text = upstream_body.decode("ascii", errors="ignore")
            # Strip leading status prefix like "00#" or trailing NULs.
            text = text.lstrip("0#")
            text = text.rstrip("\x00")
            # crude split on & key=value pairs
            parts: dict[str, str] = {}
            for kv in text.split("&"):
                if "=" in kv:
                    k, _, v = kv.partition("=")
                    parts[k.lstrip("#0")] = v
            # Same chunked B0/B1/... handling
            rchunks = sorted(
                (int(k[1]), v) for k, v in parts.items()
                if len(k) == 2 and k[0] == "B" and k[1].isdigit()
            )
            if rchunks:
                response_fields = split_b0("".join(v for _, v in rchunks))
            response_h = parts.get("H")
        except Exception as exc:  # noqa: BLE001
            log.debug("response parse failed: %s", exc)

    record = {
        "ts": ts.isoformat(),
        "client": request.remote,
        "method": method,
        "path": path,
        "endpoint": endpoint,
        "b0": b0,
        "h": h,
        "fields": fields,
        "n_chunks": len(chunks),
        "upstream_status": upstream_status,
        "upstream_time_s": upstream_time_s,
        "upstream_error": err,
        "request_body_size": len(body),
        "response_size_bytes": len(upstream_body),
        "response_body_b64": (
            base64.b64encode(upstream_body).decode() if upstream_body else None
        ),
        "response_fields": response_fields,
        "response_h": response_h,
        # Correlation snapshot: the chlorinator only sends real telemetry
        # (write.php with B0+B1+B2) while the filter motor is actually
        # running, so we tag every record with the latest known pump
        # power to filter the corpus offline.
        "pump_power_w": state.pump_power_w,
        "pump_running": state.pump_running,
    }
    state.ingest(record)
    append_jsonl(record)

    # Reply to the chlorinator with whatever the cloud said.
    if upstream_status is None:
        return web.Response(status=502, text="upstream_unreachable")
    return web.Response(status=upstream_status, body=upstream_body)


# ---------- JSON API on port 8765 ------------------------------------------


async def api_health(request: web.Request) -> web.Response:  # noqa: ARG001
    return web.json_response({
        "ok": True,
        "history_size": len(state.history),
        "options": {
            "upstream_host": UPSTREAM_HOST,
            "upstream_host_header": UPSTREAM_HOST_HEADER,
            "max_history": MAX_HISTORY,
            "online_timeout_s": ONLINE_TIMEOUT_S,
        },
        "jsonl_path": str(JSONL_PATH),
        "jsonl_size_bytes": JSONL_PATH.stat().st_size if JSONL_PATH.exists() else 0,
    })


async def api_state(request: web.Request) -> web.Response:  # noqa: ARG001
    now = datetime.now(timezone.utc)
    online = False
    age_s: float | None = None
    if state.last_seen:
        age_s = (now - state.last_seen).total_seconds()
        online = age_s < ONLINE_TIMEOUT_S

    window_s = 5 * 60
    cutoff = now.timestamp() - window_s
    recent = 0
    for r in reversed(state.history):
        try:
            if datetime.fromisoformat(r["ts"]).timestamp() < cutoff:
                break
        except Exception:  # noqa: BLE001
            continue
        recent += 1
    rate_per_min = (recent / (window_s / 60)) if recent else 0.0

    last = state.history[-1] if state.history else None
    session_age_s: float | None = None
    if state.first_seen_session and state.last_seen:
        session_age_s = (state.last_seen - state.first_seen_session).total_seconds()

    return web.json_response({
        "online": online,
        "last_seen": state.last_seen.isoformat() if state.last_seen else None,
        "age_seconds": age_s,
        "polling_rate_per_min_5m": round(rate_per_min, 2),
        "requests_total": len(state.history),
        "read_count": state.read_count,
        "write_count": state.write_count,
        "device_id": state.device_id,
        "session_token": state.session_token,
        "last_fields": state.last_fields,
        "last_endpoint": last["path"] if last else None,
        "last_upstream_status": last["upstream_status"] if last else None,
        "last_upstream_time_s": last["upstream_time_s"] if last else None,
        "last_response_size_bytes": (
            state.last_response["size_bytes"] if state.last_response else None
        ),
        "last_response_endpoint": (
            state.last_response.get("endpoint") if state.last_response else None
        ),
        "last_response_fields": state.last_response_fields,
        "last_fields_decoded": decode_fields(state.last_fields),
        "last_response_fields_decoded": decode_fields(state.last_response_fields),
        "last_write_fields_decoded": decode_fields(state.last_write_fields),
        "sticky_fields_decoded": decode_fields(state.sticky_fields),
        "measurements": summarise_measurements(
            decode_fields(state.sticky_fields)
        ),
        "current_session": State._snapshot_session(state.current_session),
        "last_session": state.last_session_closed,
        "session_age_seconds": session_age_s,
        # Pump correlation
        "pump_power_w": state.pump_power_w,
        "pump_running": state.pump_running,
        "pump_entity": PUMP_ENTITY or None,
        "pump_entity_state": state.pump_entity_state,
        "pump_last_check": (
            state.pump_last_check.isoformat() if state.pump_last_check else None
        ),
        "pump_running_seconds": (
            (datetime.now(timezone.utc) - state.pump_running_since).total_seconds()
            if state.pump_running_since else None
        ),
    })


async def api_history(request: web.Request) -> web.Response:
    try:
        n = int(request.rel_url.query.get("n", "50"))
    except ValueError:
        n = 50
    n = max(1, min(n, MAX_HISTORY))
    return web.json_response({"items": list(state.history)[-n:]})


# ----- Time-series endpoints (used by the ingress dashboard) ---------------


def _read_jsonl_window(hours: float) -> list[dict]:
    """Stream the persistent jsonl and return records inside the last
    `hours` hours. Skips malformed lines silently. Optimised to avoid
    loading the whole file when it grows large."""
    if not JSONL_PATH.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: list[dict] = []
    try:
        with JSONL_PATH.open("r") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    ts = datetime.fromisoformat(rec["ts"])
                    if ts >= cutoff:
                        out.append(rec)
                except Exception:  # noqa: BLE001
                    continue
    except Exception as exc:  # noqa: BLE001
        log.warning("read jsonl failed: %s", exc)
    return out


def _decimate(samples: list[dict], target: int) -> list[dict]:
    """Down-sample a series to roughly `target` points."""
    if len(samples) <= target:
        return samples
    step = len(samples) / target
    return [samples[int(i * step)] for i in range(target)]


async def api_timeseries(request: web.Request) -> web.Response:
    """Return decimated time series of measurements over the last N hours.

    Query: ?hours=24&points=200 (defaults shown).
    Response: { ph: [{t, v}], salinity: [...], temperature: [...],
                production: [...] }
    """
    try:
        hours = float(request.rel_url.query.get("hours", "24"))
    except ValueError:
        hours = 24.0
    try:
        points = int(request.rel_url.query.get("points", "240"))
    except ValueError:
        points = 240
    points = max(10, min(points, 2000))

    records = _read_jsonl_window(hours)
    # Order the records chronologically — _read_jsonl_window streams the
    # file in append order but a defensive sort costs nothing.
    records.sort(key=lambda r: r.get("ts", ""))

    raw: dict[str, list[dict]] = {
        "ph": [],
        "salinity": [],
        "temperature": [],
        "production": [],
    }
    metric_map = {
        # codec key -> dashboard series key
        "ph": "ph",
        "salinity": "salinity",
        "temperature": "temperature",
        "production_percent": "production",
    }
    # Sticky decoding: not every write carries every field (the
    # chlorinator rotates which Bn fields go in each request). Carry
    # the last known value forward and emit a new point only when the
    # value actually changes — that gives us continuous series for
    # every metric without bloating the JSON.
    sticky_fields_local: dict[str, str] = {}
    last_emitted: dict[str, float | None] = {dst: None for dst in metric_map.values()}

    for rec in records:
        if rec.get("endpoint") != "write":
            continue
        fields = rec.get("fields") or {}
        if not fields:
            continue
        # Merge incoming fields into the local sticky state.
        for k, v in fields.items():
            if k.startswith("__"):
                continue
            sticky_fields_local[k] = v
        ms = summarise_measurements(decode_fields(sticky_fields_local))
        if not ms:
            continue
        ts = rec["ts"]
        for src, dst in metric_map.items():
            m = ms.get(src)
            if not isinstance(m, dict):
                continue
            val = m.get("value")
            if val is None:
                continue
            # Only emit when the value actually moves (or first point).
            if last_emitted[dst] is None or abs(val - last_emitted[dst]) > 1e-9:
                raw[dst].append({"t": ts, "v": val})
                last_emitted[dst] = val

    result = {k: _decimate(v, points) for k, v in raw.items()}
    return web.json_response({
        "hours_requested": hours,
        "points": points,
        "series": result,
    })


async def _ha_state(entity_id: str) -> dict | None:
    """Read a single HA state via the Supervisor-proxied Core API."""
    if not entity_id or not SUPERVISOR_TOKEN:
        return None
    try:
        async with ClientSession() as s:
            async with s.get(
                f"{HASS_API}/states/{entity_id}",
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                timeout=ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as exc:  # noqa: BLE001
        log.debug("HA state(%s) failed: %s", entity_id, exc)
    return None


async def _ha_history(
    entity_id: str,
    start: datetime,
    end: datetime | None = None,
) -> list[dict]:
    """Read state changes for an entity within [start, end] from HA history."""
    if not entity_id or not SUPERVISOR_TOKEN:
        return []
    start_iso = start.isoformat()
    url = f"{HASS_API}/history/period/{start_iso}"
    params = {
        "filter_entity_id": entity_id,
        "minimal_response": "true",
    }
    if end is not None:
        params["end_time"] = end.isoformat()
    try:
        async with ClientSession() as s:
            async with s.get(
                url,
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                params=params,
                timeout=ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data[0] if data else []
    except Exception as exc:  # noqa: BLE001
        log.debug("HA history(%s) failed: %s", entity_id, exc)
        return []


def _kwh_from_history(
    history: list[dict],
    floor_w: float = 5.0,
    cap_seconds: float = 600.0,
) -> tuple[float, float]:
    """Integrate kWh from a list of HA state changes (power, W).

    Returns (kwh_total, motor_running_seconds): the second value sums
    only intervals where power was above `floor_w` so the user can
    distinguish real motor activity from contactor coil draw.
    Intervals longer than `cap_seconds` are clipped (HA may have been
    down or the entity unavailable).
    """
    if not history:
        return 0.0, 0.0
    kwh = 0.0
    motor_s = 0.0
    prev_ts: datetime | None = None
    prev_w: float | None = None
    for rec in history:
        ts_str = rec.get("last_changed") or rec.get("last_updated")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        try:
            w = float(rec.get("state", "0"))
        except (TypeError, ValueError):
            w = None
        if prev_ts is not None and prev_w is not None:
            dt = min((ts - prev_ts).total_seconds(), cap_seconds)
            if dt > 0:
                kwh += prev_w * dt / 3600 / 1000
                if prev_w > floor_w:
                    motor_s += dt
        prev_ts = ts
        prev_w = w
    return round(kwh, 3), round(motor_s, 1)


async def api_pumps(request: web.Request) -> web.Response:  # noqa: ARG001
    """Live + 24h/7d/30d energy use of the two pump channels.

    Returns:
      {
        "pump":    {now_w, switch, kwh_24h, kwh_7d, kwh_30d,
                    motor_hours_24h, motor_hours_7d, eur_30d},
        "cleaner": { ... same shape ... },
        "price_eur_kwh": float,
      }
    """
    now = datetime.now(timezone.utc)

    async def _channel(power_ent: str, switch_ent: str) -> dict:
        out: dict = {
            "power_entity": power_ent,
            "switch_entity": switch_ent,
            "now_w": None,
            "switch": None,
            "kwh_24h": 0.0,
            "kwh_7d": 0.0,
            "kwh_30d": 0.0,
            "motor_hours_24h": 0.0,
            "motor_hours_7d": 0.0,
            "eur_30d": 0.0,
        }
        if not power_ent:
            return out
        state_now = await _ha_state(power_ent)
        if state_now:
            try:
                out["now_w"] = float(state_now.get("state", "0"))
            except (TypeError, ValueError):
                out["now_w"] = None
        sw_state = await _ha_state(switch_ent) if switch_ent else None
        if sw_state:
            out["switch"] = sw_state.get("state")
        # 30 days of history (enough for the longest aggregate); slice it.
        hist30 = await _ha_history(power_ent, now - timedelta(days=30), now)
        kwh30, motor30 = _kwh_from_history(hist30)
        # Sub-window: filter records inside 7d / 24h
        cutoff_7d = (now - timedelta(days=7)).isoformat()
        cutoff_24h = (now - timedelta(hours=24)).isoformat()
        hist7 = [r for r in hist30 if (r.get("last_changed") or "") >= cutoff_7d]
        hist24 = [r for r in hist30 if (r.get("last_changed") or "") >= cutoff_24h]
        kwh7, motor7 = _kwh_from_history(hist7)
        kwh24, motor24 = _kwh_from_history(hist24)
        out["kwh_30d"] = round(kwh30, 3)
        out["kwh_7d"] = round(kwh7, 3)
        out["kwh_24h"] = round(kwh24, 3)
        out["motor_hours_7d"] = round(motor7 / 3600, 2)
        out["motor_hours_24h"] = round(motor24 / 3600, 2)
        out["eur_30d"] = round(kwh30 * ENERGY_PRICE_EUR_KWH, 2)
        return out

    pump = await _channel(PUMP_ENTITY, PUMP_SWITCH_ENTITY)
    cleaner = await _channel(CLEANER_ENTITY, CLEANER_SWITCH_ENTITY)

    return web.json_response({
        "pump": pump,
        "cleaner": cleaner,
        "price_eur_kwh": ENERGY_PRICE_EUR_KWH,
    })


def _temp_multiplier(temp_c: float | None) -> float:
    """Chlorine demand scales with water temperature: warmer water
    consumes chlorine faster (kinetics + bacteriostatic margin).
    """
    if temp_c is None:
        return 1.0
    if temp_c < 20:
        return 0.7
    if temp_c < 24:
        return 0.85
    if temp_c < 28:
        return 1.0
    if temp_c < 32:
        return 1.15
    if temp_c < 36:
        return 1.3
    return 1.5


def _compute_recommendation(
    volume_m3: float,
    flow_m3_h: float,
    cell_g_h: float,
    target_pct: int,
    chlorine_demand_ppm_day: float,
    min_turnovers_per_day: float,
    temp_c: float | None,
) -> dict:
    """Combine chlorine-demand and filter-turnover constraints.

    The driver for an indoor pool is **chlorine production**, not
    turnover. With the cover on and zero UV exposure the chlorine
    decay is slow, so the pump's job is mainly to electrolyse and
    distribute. We compute two candidates and take the larger:

    1. **Chlorine-demand minutes** — how long the cell has to run at
       the target production percentage to replace the daily chlorine
       consumption.

       daily_demand_g = chlorine_demand_ppm_day * volume_m3   (mg/L * m³ → g)
       cl_per_min     = cell_g_h * (target_pct/100) / 60      (g/min)
       chl_minutes    = (daily_demand_g / cl_per_min) * temp_mult

    2. **Turnover minutes** — minimal hydraulic mixing.

       turnover_minutes = (volume_m3 / flow_m3_h) * 60 * min_turnovers_per_day

    The driver field tells the dashboard which constraint won.
    """
    cl_per_min = cell_g_h * (target_pct / 100) / 60.0
    daily_demand_g = chlorine_demand_ppm_day * volume_m3
    temp_mult = _temp_multiplier(temp_c)
    chl_minutes = (daily_demand_g / cl_per_min) * temp_mult if cl_per_min > 0 else 0
    turnover_minutes = (
        (volume_m3 / flow_m3_h) * 60 * min_turnovers_per_day if flow_m3_h > 0 else 0
    )
    rec = max(chl_minutes, turnover_minutes)
    driver = "chlorine_demand" if chl_minutes >= turnover_minutes else "turnover"
    return {
        "recommended_minutes_today": round(rec),
        "driver": driver,
        "chlorine_demand_minutes": round(chl_minutes),
        "turnover_minutes": round(turnover_minutes),
        "temperature_multiplier": temp_mult,
        "daily_chlorine_demand_g": round(daily_demand_g, 1),
        "cell_output_g_per_min": round(cl_per_min, 3),
    }


async def api_recommendation(request: web.Request) -> web.Response:  # noqa: ARG001
    """Recommend a daily and weekly filtration time.

    Hybrid model that picks the larger of two constraints:
    - **Chlorine demand**: minutes for the cell to electrolyse enough
      chlorine to replace daily decay (driven by volume × demand vs
      cell output × target %).
    - **Turnover**: minimal hydraulic mixing.

    Indoor covered pools without UV exposure use far less chlorine,
    so chlorine_demand typically wins at low values and the
    recommendation drops well below the historical "1 turnover/day"
    rule of thumb.
    """
    ms = summarise_measurements(decode_fields(state.sticky_fields)) or {}
    temp_c = (ms.get("temperature") or {}).get("value")

    calc = _compute_recommendation(
        volume_m3=POOL_VOLUME_M3,
        flow_m3_h=PUMP_NOMINAL_FLOW_M3_H,
        cell_g_h=CELL_CAPACITY_G_H,
        target_pct=TARGET_PRODUCTION_PCT,
        chlorine_demand_ppm_day=CHLORINE_DEMAND_PPM_PER_DAY,
        min_turnovers_per_day=MIN_TURNOVERS_PER_DAY,
        temp_c=temp_c,
    )
    rec_min_today = calc["recommended_minutes_today"]
    rec_min_week = rec_min_today * 7

    # Real runtime from the activity log (uses pump_running edges).
    now = datetime.now(timezone.utc)
    records = _read_jsonl_window(hours=7 * 24)
    by_day: dict[str, float] = {}
    prev_running = False
    prev_ts: datetime | None = None
    for rec in records:
        try:
            ts = datetime.fromisoformat(rec["ts"])
        except Exception:  # noqa: BLE001
            continue
        if rec.get("pump_running") and prev_running and prev_ts is not None:
            delta = (ts - prev_ts).total_seconds() / 60
            if 0 < delta <= 15:
                day_key = prev_ts.astimezone().date().isoformat()
                by_day[day_key] = by_day.get(day_key, 0) + delta
        prev_running = bool(rec.get("pump_running"))
        prev_ts = ts
    today_key = now.astimezone().date().isoformat()
    real_min_today = round(by_day.get(today_key, 0))
    real_min_week = round(sum(by_day.values()))

    coverage_today = (
        round(real_min_today / rec_min_today * 100) if rec_min_today else 0
    )
    coverage_week = (
        round(real_min_week / rec_min_week * 100) if rec_min_week else 0
    )

    return web.json_response({
        "pool_volume_m3": POOL_VOLUME_M3,
        "nominal_flow_m3_h": PUMP_NOMINAL_FLOW_M3_H,
        "cell_capacity_g_h": CELL_CAPACITY_G_H,
        "target_production_pct": TARGET_PRODUCTION_PCT,
        "chlorine_demand_ppm_per_day": CHLORINE_DEMAND_PPM_PER_DAY,
        "min_turnovers_per_day": MIN_TURNOVERS_PER_DAY,
        "indoor_pool": INDOOR_POOL,
        "water_temperature_c": temp_c,
        "temperature_multiplier": calc["temperature_multiplier"],
        "daily_chlorine_demand_g": calc["daily_chlorine_demand_g"],
        "cell_output_g_per_min": calc["cell_output_g_per_min"],
        "chlorine_demand_minutes": calc["chlorine_demand_minutes"],
        "turnover_minutes": calc["turnover_minutes"],
        "driver": calc["driver"],
        "recommended_minutes_today": rec_min_today,
        "recommended_minutes_week": rec_min_week,
        "real_minutes_today": real_min_today,
        "real_minutes_week": real_min_week,
        "coverage_today_pct": coverage_today,
        "coverage_week_pct": coverage_week,
    })


async def api_activity(request: web.Request) -> web.Response:
    """Pump-running activity aggregated per day over the last N days.

    Two sources of truth, fused:
    1. **Primary** — HA history of the `pump_switch_entity` (switch on/off
       transitions). Survives Shelly outages because HA keeps the state
       in its recorder even when the device goes unavailable.
    2. **Fallback** — `pump_running` flag in the jsonl (derived from the
       Shelly power reading at write time). Only used to cover gaps
       where the switch entity wasn't set or HA history was empty.
    """
    try:
        days = int(request.rel_url.query.get("days", "30"))
    except ValueError:
        days = 30
    days = max(1, min(days, 90))

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    by_day: dict[str, dict] = {}
    last_start: str | None = None

    def _slot(day_key: str) -> dict:
        return by_day.setdefault(
            day_key, {"day": day_key, "running_minutes": 0.0, "start_count": 0}
        )

    # --- Primary source: HA history of the switch ---
    sw_records: list[dict] = []
    if PUMP_SWITCH_ENTITY:
        sw_records = await _ha_history(PUMP_SWITCH_ENTITY, start, now)

    primary_used = False
    if sw_records:
        primary_used = True
        prev_state: str | None = None
        prev_ts: datetime | None = None
        for rec in sw_records:
            ts_str = rec.get("last_changed") or rec.get("last_updated")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            state_val = rec.get("state")
            # Detect off->on transition.
            if state_val == "on" and prev_state != "on":
                last_start = ts.isoformat()
                _slot(ts.astimezone().date().isoformat())["start_count"] += 1
            # Accumulate minutes while previous state was "on".
            if prev_state == "on" and prev_ts is not None:
                delta = (ts - prev_ts).total_seconds() / 60
                if delta > 0:
                    day_key = prev_ts.astimezone().date().isoformat()
                    _slot(day_key)["running_minutes"] += delta
            prev_state = state_val
            prev_ts = ts
        # If the last seen state was "on", count up to now.
        if prev_state == "on" and prev_ts is not None:
            delta = (now - prev_ts).total_seconds() / 60
            if delta > 0:
                day_key = prev_ts.astimezone().date().isoformat()
                _slot(day_key)["running_minutes"] += delta

    # --- Fallback source: jsonl pump_running flag ---
    if not primary_used:
        records = _read_jsonl_window(hours=days * 24)
        records.sort(key=lambda r: r.get("ts", ""))
        prev_running = False
        prev_ts2: datetime | None = None
        for rec in records:
            try:
                ts = datetime.fromisoformat(rec["ts"])
            except Exception:  # noqa: BLE001
                continue
            running = bool(rec.get("pump_running"))
            if running and not prev_running:
                last_start = rec["ts"]
                _slot(ts.astimezone().date().isoformat())["start_count"] += 1
            if prev_running and prev_ts2 is not None:
                delta = (ts - prev_ts2).total_seconds() / 60
                if 0 < delta <= 15:
                    day_key = prev_ts2.astimezone().date().isoformat()
                    _slot(day_key)["running_minutes"] += delta
            prev_running = running
            prev_ts2 = ts

    # Fill missing days with zero so the chart shows continuous bars.
    today = datetime.now().astimezone().date()
    filled: list[dict] = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        slot = by_day.get(d) or {"day": d, "running_minutes": 0, "start_count": 0}
        slot["running_minutes"] = round(slot["running_minutes"], 1)
        filled.append(slot)

    week = sum(s["running_minutes"] for s in filled[-7:]) / 60
    month = sum(s["running_minutes"] for s in filled) / 60

    # Shelly availability flag for the frontend.
    pump_power = await _ha_state(PUMP_ENTITY) if PUMP_ENTITY else None
    shelly_available = (
        pump_power is not None
        and pump_power.get("state") not in (None, "unknown", "unavailable")
    )

    return web.json_response({
        "days": filled,
        "last_start": last_start,
        "total_running_hours_week": round(week, 2),
        "total_running_hours_month": round(month, 2),
        "source": "ha_switch_history" if primary_used else "jsonl_fallback",
        "shelly_available": shelly_available,
    })


async def api_last_response(request: web.Request) -> web.Response:  # noqa: ARG001
    if not state.last_response:
        return web.json_response({"available": False})
    body_b64 = state.last_response["body_b64"]
    body = base64.b64decode(body_b64) if body_b64 else b""
    hex_dump = " ".join(f"{b:02x}" for b in body[:128])
    ascii_view = "".join((chr(b) if 32 <= b < 127 else ".") for b in body[:128])
    return web.json_response({
        "available": True,
        "ts": state.last_response["ts"],
        "size_bytes": state.last_response["size_bytes"],
        "body_b64": body_b64,
        "preview_hex": hex_dump,
        "preview_ascii": ascii_view,
    })


async def api_analyze(request: web.Request) -> web.Response:  # noqa: ARG001
    """Statistical breakdown of all captured B0 payloads — useful while
    we still don't know the codec."""
    history = list(state.history)
    if not history:
        return web.json_response({"items": 0})

    all_b0 = [r["b0"] for r in history if r.get("b0")]
    chars: Counter[str] = Counter()
    for b0 in all_b0:
        chars.update(b0)

    # Aggregate field-by-field
    by_endpoint: dict[str, dict[str, set[str]]] = {}
    for r in history:
        ep = r.get("endpoint") or "?"
        f = r.get("fields") or {}
        d = by_endpoint.setdefault(ep, {})
        for k, v in f.items():
            d.setdefault(k, set()).add(v)

    fields_summary: dict[str, dict] = {}
    for ep, fields in by_endpoint.items():
        ep_summary: dict[str, dict] = {}
        for k, vals in fields.items():
            ep_summary[k] = {
                "distinct_values": len(vals),
                "is_invariant": len(vals) == 1,
                "sample_values": sorted(vals)[:8],
            }
        fields_summary[ep] = ep_summary

    response_sizes = Counter(
        r["response_size_bytes"] for r in history if r.get("response_size_bytes")
    )

    return web.json_response({
        "items": len(history),
        "alphabet": "".join(sorted(chars.keys())),
        "alphabet_size": len(chars),
        "char_frequency": dict(chars.most_common()),
        "fields_by_endpoint": fields_summary,
        "response_size_distribution": dict(response_sizes),
    })


# ---------- App wiring -----------------------------------------------------


async def pump_poller(app: web.Application) -> None:
    """Background task: poll HA Core for the filter pump power and update
    the global state used to correlate every captured request."""
    if not PUMP_ENTITY:
        log.info("pump_power_entity not configured, skipping correlation poller")
        return
    if not SUPERVISOR_TOKEN:
        log.warning("SUPERVISOR_TOKEN missing — homeassistant_api must be true")
        return

    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{HASS_API}/states/{PUMP_ENTITY}"
    log.info("pump correlation: entity=%s threshold=%.1f W poll=%ds",
             PUMP_ENTITY, PUMP_THRESHOLD_W, PUMP_POLL_S)
    client: ClientSession = app["http_client"]
    while True:
        try:
            async with client.get(url, headers=headers) as r:
                if r.status != 200:
                    log.debug("HA poll %s -> %s", PUMP_ENTITY, r.status)
                else:
                    data = await r.json()
                    raw = data.get("state")
                    state.pump_entity_state = raw
                    try:
                        watts = float(raw)
                    except (TypeError, ValueError):
                        watts = None
                    if watts is not None:
                        state.pump_power_w = watts
                        was_running = state.pump_running
                        state.pump_running = watts >= PUMP_THRESHOLD_W
                        if state.pump_running and not was_running:
                            state.pump_running_since = datetime.now(timezone.utc)
                            log.info("PUMP RUNNING detected (%.1f W >= %.1f W)",
                                     watts, PUMP_THRESHOLD_W)
                        elif not state.pump_running and was_running:
                            state.pump_running_since = None
                            log.info("pump stopped (%.1f W < %.1f W) — closing session",
                                     watts, PUMP_THRESHOLD_W)
                            # Pump just went off — close the current
                            # session whatever its idle status.
                            state.force_close_session()
                    state.pump_last_check = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001
            log.debug("pump poll error: %s", exc)
        await asyncio.sleep(PUMP_POLL_S)


async def session_closer(app: web.Application) -> None:
    """Periodically check whether the current session has gone idle."""
    while True:
        try:
            state.close_session_if_idle(datetime.now(timezone.utc))
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(30)


async def on_startup(app: web.Application) -> None:
    timeout = ClientTimeout(total=30, connect=5)
    connector = TCPConnector(limit=8, force_close=False, enable_cleanup_closed=True)
    app["http_client"] = ClientSession(timeout=timeout, connector=connector)
    warm_from_jsonl()
    app["pump_task"] = asyncio.create_task(pump_poller(app))
    app["session_task"] = asyncio.create_task(session_closer(app))
    log.info(
        "capturer ready: upstream=%s host=%s online_timeout=%ds",
        UPSTREAM_HOST, UPSTREAM_HOST_HEADER, ONLINE_TIMEOUT_S,
    )


async def on_cleanup(app: web.Application) -> None:
    for k in ("pump_task", "session_task"):
        t = app.get(k)
        if t:
            t.cancel()
    client: ClientSession = app["http_client"]
    await client.close()


def build_proxy_app() -> web.Application:
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.router.add_route("*", "/{tail:.*}", proxy_handler)
    return app


ADDON_VERSION = "0.6.4"


async def ingress_index(request: web.Request) -> web.Response:  # noqa: ARG001
    """Serve the dashboard SPA from static/index.html.

    Injects {{VERSION}} as cache-buster on the css/js asset links so
    bumping the addon forces the browser to reload them. Falls back to
    the legacy inline page if the static dir is missing."""
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        html = idx.read_text().replace("{{VERSION}}", ADDON_VERSION)
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return await _legacy_ingress_index(request)


async def _legacy_ingress_index(request: web.Request) -> web.Response:  # noqa: ARG001
    """Fallback in case the static/ directory is missing from the image."""
    now = datetime.now(timezone.utc)
    online = bool(
        state.last_seen
        and (now - state.last_seen).total_seconds() < ONLINE_TIMEOUT_S
    )
    seconds_since = (
        (now - state.last_seen).total_seconds() if state.last_seen else None
    )
    measurements = summarise_measurements(decode_fields(state.sticky_fields)) or {}
    captured = len(state.history)
    last_session_snapshot = State._snapshot_session(
        state.last_session_closed or State._empty_session()
    )

    def _row(label: str, value: object) -> str:
        v = "—" if value in (None, "") else value
        return (
            f'<tr><td style="padding:6px 10px;border:2px solid #1f1d1a;'
            f'background:#fff5d6;width:45%;">{label}</td>'
            f'<td style="padding:6px 10px;border:2px solid #1f1d1a;font-weight:bold;">{v}</td></tr>'
        )

    def _live(name: str) -> str:
        m = measurements.get(name)
        if isinstance(m, dict):
            v = m.get("value")
            unit = m.get("unit", "")
            return f"{v} {unit}".strip() if v is not None else "—"
        return "—"

    last_session_aggs = last_session_snapshot.get("aggregates") or {}

    def _agg(metric: str, key: str = "avg") -> str:
        a = last_session_aggs.get(metric)
        if isinstance(a, dict) and a.get(key) is not None:
            return str(a[key])
        return "—"

    rows = [
        _row("Online", "✅ sí" if online else "❌ no"),
        _row("Requests capturadas", captured),
        _row("Read.php calls", state.read_count),
        _row("Write.php calls", state.write_count),
        _row(
            "Seconds since last request",
            round(seconds_since, 1) if isinstance(seconds_since, (int, float)) else "—",
        ),
        _row("pH (live)", _live("ph")),
        _row("Salinity (live)", _live("salinity")),
        _row("Water temperature (live)", _live("temperature")),
        _row("Last session pH avg", _agg("SG")),
        _row("Last session salt avg", _agg("IT")),
        _row("Last session duration (s)", last_session_snapshot.get("duration_seconds")),
    ]

    html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><title>Idegis cloud capturer</title>
<style>
  body {{margin:0;font-family:Verdana,sans-serif;background:#f4ecd8;color:#1f1d1a;padding:20px;}}
  .wrap {{max-width:720px;margin:0 auto;}}
  h1 {{font-weight:900;background:#fff5d6;border:3px solid #1f1d1a;padding:8px 16px;display:inline-block;box-shadow:5px 5px 0 #1f1d1a;letter-spacing:-1px;}}
  table {{width:100%;border-collapse:collapse;margin-top:16px;background:#fff;box-shadow:5px 5px 0 #1f1d1a;border:3px solid #1f1d1a;}}
  a {{color:#1f1d1a;}}
  .links {{margin-top:24px;font-size:13px;color:#555;}}
  .links a {{display:inline-block;background:#fff5d6;border:2px solid #1f1d1a;padding:4px 10px;text-decoration:none;margin-right:8px;border-radius:4px;box-shadow:2px 2px 0 #1f1d1a;}}
</style></head>
<body><div class="wrap">
  <h1>🌊 IDEGIS CAPTURER</h1>
  <p>Estado en vivo del capturer. Auto-refresh cada 30 s.</p>
  <table>{''.join(rows)}</table>
  <div class="links">
    <a href="api/idegis/state">📄 /api/idegis/state</a>
    <a href="api/idegis/history">🕒 /api/idegis/history</a>
    <a href="api/idegis/analyze">🔬 /api/idegis/analyze</a>
    <a href="api/idegis/last_response">📥 /api/idegis/last_response</a>
  </div>
</div>
<script>setTimeout(() => location.reload(), 30000);</script>
</body></html>"""
    return web.Response(text=html, content_type="text/html")


STATIC_DIR = Path(__file__).parent / "static"


def build_api_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", ingress_index)
    app.router.add_get("/api/idegis/health", api_health)
    app.router.add_get("/api/idegis/state", api_state)
    app.router.add_get("/api/idegis/history", api_history)
    app.router.add_get("/api/idegis/last_response", api_last_response)
    app.router.add_get("/api/idegis/analyze", api_analyze)
    app.router.add_get("/api/idegis/timeseries", api_timeseries)
    app.router.add_get("/api/idegis/activity", api_activity)
    app.router.add_get("/api/idegis/pumps", api_pumps)
    app.router.add_get("/api/idegis/recommendation", api_recommendation)
    if STATIC_DIR.exists():
        app.router.add_static("/static/", path=str(STATIC_DIR), show_index=False)
    return app


async def main() -> None:
    # Shared client session lives in the proxy app (it does the outbound HTTP).
    proxy_app = build_proxy_app()
    api_app = build_api_app()

    proxy_app.on_startup.append(on_startup)
    proxy_app.on_cleanup.append(on_cleanup)

    proxy_runner = web.AppRunner(proxy_app)
    api_runner = web.AppRunner(api_app)
    await proxy_runner.setup()
    await api_runner.setup()

    # Forward the shared http client into the api app so it can also do
    # outbound calls if needed in the future.
    api_app["http_client"] = proxy_app["http_client"] if "http_client" in proxy_app else None

    proxy_site = web.TCPSite(proxy_runner, host="0.0.0.0", port=80)
    api_site = web.TCPSite(api_runner, host="0.0.0.0", port=8765)
    await proxy_site.start()
    await api_site.start()
    log.info("proxy on :80, api on :8765")

    # Sleep forever.
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
