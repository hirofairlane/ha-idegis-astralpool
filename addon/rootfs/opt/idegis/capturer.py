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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, TCPConnector, web

# ---------- Configuration --------------------------------------------------

_OPTIONS_FILE = Path("/data/options.json")

DEFAULTS = {
    "upstream_host": "45.60.153.189",
    "upstream_host_header": "api.idegis.net",
    "log_level": "info",
    "max_history": 1000,
    "online_timeout_s": 90,
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


class State:
    def __init__(self) -> None:
        self.history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self.read_count = 0
        self.write_count = 0
        self.last_seen: datetime | None = None
        self.last_fields: dict[str, str] = {}
        self.last_response: dict | None = None  # body of latest cloud response
        self.last_response_fields: dict[str, str] = {}
        self.device_id: str | None = None
        self.session_token: str | None = None
        self.first_seen_session: datetime | None = None

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
        "session_age_seconds": session_age_s,
    })


async def api_history(request: web.Request) -> web.Response:
    try:
        n = int(request.rel_url.query.get("n", "50"))
    except ValueError:
        n = 50
    n = max(1, min(n, MAX_HISTORY))
    return web.json_response({"items": list(state.history)[-n:]})


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


async def on_startup(app: web.Application) -> None:
    timeout = ClientTimeout(total=30, connect=5)
    connector = TCPConnector(limit=8, force_close=False, enable_cleanup_closed=True)
    app["http_client"] = ClientSession(timeout=timeout, connector=connector)
    warm_from_jsonl()
    log.info(
        "capturer ready: upstream=%s host=%s online_timeout=%ds",
        UPSTREAM_HOST, UPSTREAM_HOST_HEADER, ONLINE_TIMEOUT_S,
    )


async def on_cleanup(app: web.Application) -> None:
    client: ClientSession = app["http_client"]
    await client.close()


def build_proxy_app() -> web.Application:
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.router.add_route("*", "/{tail:.*}", proxy_handler)
    return app


def build_api_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/idegis/health", api_health)
    app.router.add_get("/api/idegis/state", api_state)
    app.router.add_get("/api/idegis/history", api_history)
    app.router.add_get("/api/idegis/last_response", api_last_response)
    app.router.add_get("/api/idegis/analyze", api_analyze)
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
