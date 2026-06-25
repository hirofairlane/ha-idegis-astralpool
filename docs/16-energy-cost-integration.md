# Energy cost & solar attribution — and Energy Optimizer integration

The capturer add-on estimates **how much the pool pumps cost to run**, splitting
consumption into **grid** energy (priced by a time-of-use tariff) and **solar**
energy (consumed from PV surplus, counted as free). This document describes the
model, the configuration, and the **contract** for sharing data with the
companion [`ha-energy-optimizer`](https://github.com/hirofairlane/ha-energy-optimizer)
add-on.

## Cost model

For every interval the pump's power sensor reports while running, the capturer:

1. Integrates energy: `kWh = power_W × dt / 3600 / 1000` (intervals clipped to
   10 min to absorb HA downtime gaps).
2. Looks up the **house grid-power sign** at that moment (from a configured
   signed grid sensor). If the house was **exporting** (PV surplus) the energy
   is attributed to **solar** → `0 €` paid (its forgone export value is tracked
   separately). Otherwise it is **grid**.
3. Prices grid energy at the **time-of-use period** in force at that timestamp
   (peak / mid / valley), evaluated in the tariff's local timezone (DST-aware).

With **no grid sensor** configured, everything is counted as grid — a safe,
pessimistic fallback — and the per-period split still applies.

> **Attribution caveat.** This is a *marginal* model: when there is any PV
> surplus, the pump's marginal draw is treated as solar. It does not apportion a
> shared load across multiple consumers. It is an estimate for awareness, not
> billing.

## Configuration (add-on options)

| Option | Default | Meaning |
|---|---|---|
| `grid_power_entity` | `""` | Signed grid-power sensor (W). Same one the Energy Optimizer reads. Empty → all energy counted as grid. |
| `grid_export_positive` | `true` | Sign convention: `+W = exporting`, `−W = importing`. Flip if your meter is inverted. |
| `tariff_timezone` | `Europe/Madrid` | Timezone for period boundaries. |
| `tariff_price_peak` / `_mid` / `_valley` | `0.2234 / 0.1483 / 0.1147` | Import price €/kWh per period (Spain 2.0TD defaults). |
| `tariff_price_export` | `0.04` | Feed-in price €/kWh (for the solar opportunity value). |
| `tariff_peak_hours` | `[10,11,12,13,18,19,20,21]` | Local hours that are *punta* on weekdays. |
| `tariff_valley_hours` | `[0..7]` | Local hours that are *valle* on weekdays. |
| `tariff_weekend_days` | `[5,6]` | Weekday indices (Sat,Sun) that are valley all day. |

Hours not in peak/valley on weekdays are **mid** (*llano*). These defaults match
the Energy Optimizer's `DEFAULT_TARIFF`, so the two stay consistent until a live
price source is wired (see below).

## What the capturer EXPOSES — `GET /api/idegis/pumps`

So the Energy Optimizer (or anything else) can incorporate pool-pump
consumption into its own accounting:

```jsonc
{
  "pump": {
    "now_w": 1100.0,
    "switch": "on",
    "kwh_24h": 2.2, "kwh_7d": 14.0, "kwh_30d": 60.0,
    "eur_30d": 8.42,                 // real grid € (solar excluded)
    "source_now": "grid",           // "solar" | "grid" | "idle" | null
    "cost": {
      "24h": { "grid_kwh": 1.8, "solar_kwh": 0.4, "grid_eur": 0.27,
               "solar_export_value_eur": 0.016, "solar_pct": 18.2,
               "by_period_eur": { "peak": 0.2, "mid": 0.07, "valley": 0.0 } },
      "7d":  { ... },
      "30d": { ... }
    }
  },
  "cleaner": { ... same shape ... },
  "grid_sensor_configured": true,
  "tariff": { "period_now": "mid", "price_now_eur_kwh": 0.1483,
              "peak": 0.2234, "mid": 0.1483, "valley": 0.1147, "export": 0.04 }
}
```

This endpoint is on the capturer's API port (`8765`) and via HA ingress.

## What the capturer would CONSUME (recommended Energy Optimizer additions)

The capturer currently **duplicates** the tariff geometry because it cannot read
the Energy Optimizer's private `/data/tariff.json` (the Optimizer is
ingress-only — no host port). To remove that duplication, the Energy Optimizer
should **publish canonical Home Assistant sensors** (via MQTT discovery or the
Supervisor API). The capturer can then read them with the same machinery it uses
for the pump power sensor and prefer them over its local tariff config:

| Proposed sensor | Unit | Notes |
|---|---|---|
| `sensor.energy_optimizer_import_price` | €/kWh | Current import price. Attribute `period: peak\|mid\|valley`. |
| `sensor.energy_optimizer_export_price` | €/kWh | Current feed-in price. |
| `sensor.energy_optimizer_grid_power` | W | Signed (or re-expose the user's grid sensor) so consumers needn't be told the entity id. |
| `sensor.energy_optimizer_power_source` | — | Convenience: `solar\|grid\|mixed`. |

This is the clean, decoupled path: the Optimizer owns pricing, the capturer (and
any other add-on) consumes it through HA, and there is a single source of truth.
Until those sensors exist, the capturer's own tariff options above are the
fallback.
