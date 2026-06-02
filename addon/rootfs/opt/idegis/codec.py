"""codec.py — Idegis B0 payload codec.

What we currently know about the alphabet (derived empirically from
captured CD timestamps and verified against wall clock):

    Base-10 digits (used by counters, timestamps and small booleans):
        a=0, b=1, c=2, d=3, e=4, f=5, U=6, V=7, W=8, X=9

    Confirmed by:
        - CD positionally encodes a Unix timestamp in seconds. Sample
          'bVWaedfcbc' decodes to 1780435212 = 2026-06-02 23:20:12 UTC.
        - LI is a per-request session counter that increments by 1
          every time, ('abbba'=1110, 'abbbb'=1111, ...).
        - CI is constant 'a' = 0 (channel index).
        - TD is the device serial, 13 base-10 digits.

What we still don't know:

    Several fields (CY, SG, 9G, IT...) contain characters that are not
    in the base-10 set (g, I, O, M, S, T, Y, ...). They almost
    certainly use a wider custom alphabet to encode the actual
    measurements (pH, ORP, salt, temperature, production %). The full
    alphabet seen across all captures is 30 chars wide:

        0 2 3 4 9 A B C D G I J L M O R S T U V W X Y a b c d e f g

    A base-30 hypothesis is plausible but we need more samples taken
    while the filter motor is actually running (pump_running=true) to
    pin down the digit order for the measurement fields.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Confirmed base-10 alphabet (a-f then U,V,W,X).
BASE10_MAP: dict[str, int] = {
    "a": 0, "b": 1, "c": 2, "d": 3, "e": 4,
    "f": 5, "U": 6, "V": 7, "W": 8, "X": 9,
}

# Fields we have identified semantically.
FIELDS_INFO = {
    "CI": {"type": "constant", "description": "Channel index (always 0)"},
    "TD": {"type": "device_id", "description": "Device serial (13-digit base10)"},
    "LI": {"type": "counter", "description": "Per-request session counter"},
    "CD": {"type": "unix_timestamp", "description": "Unix seconds when the request was built"},
    # Booleans
    "9C": {"type": "bool", "description": "Unknown boolean flag"},
    "Jb": {"type": "bool", "description": "Unknown boolean flag"},
    "SI": {"type": "bool", "description": "Unknown boolean flag"},
    "YI": {"type": "bool", "description": "Unknown boolean flag"},
    "Y9": {"type": "bool", "description": "Unknown boolean flag"},
    "DL": {"type": "bool", "description": "Unknown boolean flag"},
    "RB": {"type": "bool", "description": "Unknown boolean flag"},
    # Counters / small integers
    "AJ": {"type": "counter", "description": "Small counter, increments slowly"},
    "OI": {"type": "counter", "description": "Small counter"},
    "OB": {"type": "counter", "description": "Counter or timestamp (~3500 range)"},
    "TB": {"type": "counter", "description": "Counter or timestamp (~3500 range)"},
    # Unknown — need wider alphabet
    "CY": {"type": "unknown", "description": "Wider-alphabet field, possibly measurement"},
    "SG": {"type": "unknown", "description": "Wider-alphabet field, possibly measurement"},
    "9G": {"type": "unknown", "description": "Wider-alphabet field"},
    "IT": {"type": "unknown", "description": "Wider-alphabet field"},
    "GY": {"type": "unknown", "description": "Wider-alphabet field"},
    # Reserved/unused as far as we know
}


def decode_base10(s: str) -> int | None:
    """Decode a base-10-custom-alphabet string into an integer.
    Returns None if the string contains any char outside our known map."""
    if not s:
        return None
    try:
        return int("".join(str(BASE10_MAP[c]) for c in s))
    except KeyError:
        return None


def decode_field(name: str, value: str) -> dict[str, Any]:
    """Decode a single field and annotate it with what we know."""
    if not value:
        return {"name": name, "raw": value, "decoded": None}

    info = FIELDS_INFO.get(name, {})
    raw_int = decode_base10(value)
    out: dict[str, Any] = {
        "name": name,
        "raw": value,
        "type": info.get("type", "unknown"),
        "description": info.get("description", ""),
        "decoded": raw_int,
    }

    # Specialised post-processing
    if name == "CD" and raw_int is not None:
        try:
            dt = datetime.fromtimestamp(raw_int, tz=timezone.utc)
            out["as_iso_utc"] = dt.isoformat()
        except (OSError, OverflowError, ValueError):
            pass
    elif name in {"9C", "Jb", "SI", "YI", "Y9", "DL", "RB"} and raw_int is not None:
        out["bool"] = bool(raw_int)

    return out


def decode_fields(fields: dict[str, str] | None) -> dict[str, dict[str, Any]]:
    """Decode every field in a request's `fields` dict."""
    if not fields:
        return {}
    out = {}
    for k, v in fields.items():
        if k.startswith("__"):
            continue
        out[k] = decode_field(k, v)
    return out
