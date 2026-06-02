"""Idegis capturer service — addon edition.

Same logic as the previous stand-alone CT104 service, adapted to read its
configuration from /data/options.json (Home Assistant add-on options) and
tail the nginx log under /data/captures/.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

# --- Config ----------------------------------------------------------------

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

LOG_PATH = Path(os.environ.get(
    "IDEGIS_LOG", "/data/captures/idegis_proxy_access.log"
))
MAX_HISTORY = int(OPTS["max_history"])
ONLINE_TIMEOUT_S = int(OPTS["online_timeout_s"])

FIELD_SEP = "4fU0W430"
KV_SEP = "4fUX2d24"

REQ_RE = re.compile(
    r'^(?P<ts>\S+)\s+'
    r'client=(?P<client>\S+)\s+'
    r'"GET (?P<path>/interface/\w+\.php)\?B0=(?P<b0>[^& ]+)&H=(?P<h>[A-F0-9]+) '
    r'HTTP/[\d.]+"\s+'
    r'status=(?P<status>\d+)\s+'
    r'sent=(?P<sent>\d+)\s+'
    r'upstream_status=(?P<upstream>\S+)\s+'
    r'upstream_time=(?P<utime>\S+)\s+'
    r'req_len=(?P<reqlen>\d+)'
)

# --- Decoder helpers --------------------------------------------------------


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


# --- In-memory state --------------------------------------------------------


class State:
    def __init__(self) -> None:
        self.history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self.read_count = 0
        self.write_count = 0
        self.last_seen: datetime | None = None
        self.last_fields: dict[str, str] = {}
        self.device_id: str | None = None
        self.session_token: str | None = None

    def ingest(self, line: str) -> bool:
        m = REQ_RE.search(line)
        if not m:
            return False
        ts_str = m.group("ts")
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            return False
        path = m.group("path")
        b0 = m.group("b0")
        h = m.group("h")
        fields = split_b0(b0)
        record = {
            "ts": ts.astimezone(timezone.utc).isoformat(),
            "path": path,
            "fields": fields,
            "h": h,
            "status": int(m.group("status")),
            "upstream_status": m.group("upstream"),
            "upstream_time_s": (
                float(m.group("utime")) if m.group("utime") != "-" else None
            ),
            "client": m.group("client"),
            "sent_bytes": int(m.group("sent")),
        }
        self.history.append(record)
        self.last_seen = ts.astimezone(timezone.utc)
        self.last_fields = fields
        if path.endswith("read.php"):
            self.read_count += 1
        elif path.endswith("write.php"):
            self.write_count += 1
        if not self.device_id:
            self.device_id = fields.get("__prefix__")
        if not self.session_token:
            self.session_token = fields.get("TD")
        return True


state = State()


# --- Log tailer -------------------------------------------------------------


async def tail_log() -> None:
    while True:
        try:
            if not LOG_PATH.exists():
                await asyncio.sleep(2)
                continue
            with LOG_PATH.open("r") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        try:
                            if f.tell() > LOG_PATH.stat().st_size:
                                break
                        except FileNotFoundError:
                            break
                        continue
                    state.ingest(line.rstrip("\n"))
        except Exception:  # noqa: BLE001
            await asyncio.sleep(2)


async def warm_from_log() -> None:
    if not LOG_PATH.exists():
        return
    try:
        with LOG_PATH.open("r") as f:
            lines = f.readlines()
        for line in lines[-MAX_HISTORY:]:
            state.ingest(line.rstrip("\n"))
    except Exception:  # noqa: BLE001
        pass


# --- FastAPI ----------------------------------------------------------------


app = FastAPI(title="Idegis capturer", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    await warm_from_log()
    asyncio.create_task(tail_log())


@app.get("/api/idegis/health")
async def health() -> dict:
    return {
        "ok": True,
        "history_size": len(state.history),
        "options": {
            "upstream_host": OPTS["upstream_host"],
            "upstream_host_header": OPTS["upstream_host_header"],
            "max_history": MAX_HISTORY,
            "online_timeout_s": ONLINE_TIMEOUT_S,
        },
    }


@app.get("/api/idegis/state")
async def get_state() -> dict:
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
        rec_ts = datetime.fromisoformat(r["ts"]).timestamp()
        if rec_ts < cutoff:
            break
        recent += 1
    rate_per_min = (recent / (window_s / 60)) if recent else 0.0

    last = state.history[-1] if state.history else None

    return {
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
    }


@app.get("/api/idegis/history")
async def history(n: int = 50) -> dict:
    n = max(1, min(n, MAX_HISTORY))
    return {"items": list(state.history)[-n:]}
