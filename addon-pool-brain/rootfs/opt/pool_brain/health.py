"""TFP-based health bands and weighted score.

The bands turn raw measurements into traffic-light text states
(`ok` / `warning_*` / `danger_*`) using the targets documented in
`docs/07-water-chemistry.md`. The health score weights them.
"""
from __future__ import annotations

from dataclasses import dataclass

# ----- Bands ----------------------------------------------------------------

def ph_band(ph: float | None) -> str:
    if ph is None:
        return "unknown"
    if ph < 6.8:
        return "danger_low"
    if ph < 7.2:
        return "warning_low"
    if ph <= 7.8:
        return "ok"
    if ph <= 8.2:
        return "warning_high"
    return "danger_high"


def salt_band(salt_g_l: float | None) -> str:
    """Neolysis low-salt range. Cell calibrates around 1.5–3.0 g/L."""
    if salt_g_l is None:
        return "unknown"
    if salt_g_l < 1.0:
        return "danger_low"
    if salt_g_l < 1.5:
        return "warning_low"
    if salt_g_l <= 3.5:
        return "ok"
    if salt_g_l <= 5.0:
        return "warning_high"
    return "danger_high"


def temperature_band(temp_c: float | None) -> str:
    """Indoor pool — the cell shows degradation risk above 36 °C."""
    if temp_c is None:
        return "unknown"
    if temp_c < 20:
        return "warning_low"
    if temp_c <= 32:
        return "ok"
    if temp_c <= 36:
        return "warm"
    return "hot"


def production_band(production_pct: float | None) -> str:
    if production_pct is None:
        return "unknown"
    if production_pct <= 95:
        return "ok"
    return "saturated"


# ----- Weighted score -------------------------------------------------------

_BAND_POINTS = {
    "ok": 100,
    "warm": 80,
    "warning_low": 70,
    "warning_high": 70,
    "saturated": 60,
    "hot": 50,
    "danger_low": 25,
    "danger_high": 25,
    "unknown": 50,
}


@dataclass
class HealthInput:
    ph: float | None
    salt_g_l: float | None
    temperature_c: float | None
    production_pct: float | None
    pump_anomaly: bool
    cleaner_anomaly: bool


def health_score(snapshot: HealthInput) -> tuple[int, dict[str, str]]:
    """Return (score 0-100, dict of band labels)."""
    bands = {
        "ph": ph_band(snapshot.ph),
        "salt": salt_band(snapshot.salt_g_l),
        "temperature": temperature_band(snapshot.temperature_c),
        "production": production_band(snapshot.production_pct),
    }
    score = (
        _BAND_POINTS[bands["ph"]] * 0.30
        + _BAND_POINTS[bands["salt"]] * 0.20
        + _BAND_POINTS[bands["production"]] * 0.25
        + _BAND_POINTS[bands["temperature"]] * 0.10
        + (15 if not snapshot.pump_anomaly else 0)
        + (0 if snapshot.cleaner_anomaly else 0)  # cleaner is informative, no weight
    )
    return int(round(score)), bands


def all_ok(bands: dict[str, str]) -> bool:
    """True only if every band is `ok` (saturated and warm are not ok)."""
    return all(v == "ok" for v in bands.values())
