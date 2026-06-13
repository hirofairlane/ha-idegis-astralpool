# Pool Brain — internal spec (working document)

Living design notes for the second add-on of `ha-idegis-astralpool`. Not
shipped to users. Kept in repo so the architecture decisions survive
context resets.

## Goal

Build a **native Home Assistant Add-on** that turns the raw Idegis cloud
telemetry (already captured by the `idegis_capturer` add-on) into a
**closed-loop pool brain**:

- Synthesises high-level "is the pool healthy?" signals on top of the raw
  sensors via MQTT discovery (new HA entities, owned by this add-on).
- Recommends and enforces a smart filtration schedule based on TFP
  guidelines, pool volume, real motor consumption history.
- Watches the pump/cleaner Shelly channels for anomalies and can
  emergency-stop them via HA service calls.
- Sends a weekly HTML report by email (SMTP/Gmail).
- Surfaces a comic-styled ingress dashboard.

## Hardware/data baseline (reference install)

| Element | Value | Source |
|---|---|---|
| Chlorinator | Idegis Neolysis Neo2-24PH/S | Sergio |
| Pool volume | 37 m³ | Sergio (option) |
| Nominal flow @ Neo2-24 | ~12 m³/h | manual page 23 |
| Cl production | 24 g Cl₂/h (max) | model spec |
| Filter pump kWh meter | `sensor.shellypro4pm_30c6f7836a6c_power_3` | Shelly Pro 4PM channel 3 |
| Cleaner pump kWh meter | `sensor.shellypro4pm_30c6f7836a6c_power_1` | Shelly Pro 4PM channel 1 |
| Electrolysis + UV + pH | **always powered, no metering** | Sergio's decision |
| Notification channel | `notify.telegram_bot_1353549989_1458801761` | input_text helper |
| Email channel | TBD `notify.smtp` (Gmail) | option |

## Synthetic entities published by the add-on

All published via MQTT discovery. Topic prefix: `homeassistant/<domain>/idegis_brain_<key>/config`.

### Sensors (numeric / text)

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.idegis_brain_health_score` | 0-100 | Weighted score (pH band 30 %, salt 20 %, FC proxy/production 25 %, temp 10 %, pump anomaly 15 %). |
| `sensor.idegis_brain_ph_band` | text | `ok` / `warning_low` / `warning_high` / `danger_low` / `danger_high`. Computed from `last_session_ph_avg`. |
| `sensor.idegis_brain_salt_band` | text | Same shape, against Neolysis low-salt thresholds (1.5–3.0 g/L). |
| `sensor.idegis_brain_temperature_band` | text | `ok` / `warm` / `hot` (>36 °C). |
| `sensor.idegis_brain_production_band` | text | `ok` / `saturated` (>95 % for 2+ sessions). |
| `sensor.idegis_brain_recommended_minutes_today` | min | TFP-table by temp + adjust by chemistry + adjust by historical effectiveness. |
| `sensor.idegis_brain_recommended_minutes_week` | min | Sum of today + remaining 6 days. |
| `sensor.idegis_brain_runtime_minutes_today` | min | Accumulated pump-running minutes today. Resets at 00:00. |
| `sensor.idegis_brain_runtime_minutes_week` | min | Rolling 7-day sum. |
| `sensor.idegis_brain_filter_kwh_today` | kWh | From Shelly. Resets at 00:00. |
| `sensor.idegis_brain_filter_kwh_week` | kWh | Rolling 7-day. |
| `sensor.idegis_brain_cleaner_kwh_today` | kWh | From Shelly. |
| `sensor.idegis_brain_cleaner_kwh_week` | kWh | Rolling 7-day. |
| `sensor.idegis_brain_pump_avg_power` | W | Average power during last full session. |
| `sensor.idegis_brain_turnovers_today` | # | Volume turnovers achieved today (runtime × flow / volume). |

### Binary sensors

| Entity ID | Description |
|---|---|
| `binary_sensor.idegis_brain_water_healthy` | All bands `ok` AND no active anomaly. |
| `binary_sensor.idegis_brain_pump_anomaly` | Overcurrent, undercurrent (dry running), or stuck contactor. |
| `binary_sensor.idegis_brain_cleaner_anomaly` | Same logic on cleaner channel. |
| `binary_sensor.idegis_brain_first_minutes_window` | True while a session is < 5 min old (filter unreliable data). |

### Buttons (actionable via HA UI)

| Entity ID | Action |
|---|---|
| `button.idegis_brain_emergency_stop_all` | Calls `switch.turn_off` on pump + cleaner + (optional cover line). |
| `button.idegis_brain_emergency_stop_pump` | Pump off only. |
| `button.idegis_brain_emergency_stop_cleaner` | Cleaner off only. |
| `button.idegis_brain_run_weekly_report_now` | Force-fire the weekly email. |
| `button.idegis_brain_recalibrate_runtime` | Reset today's runtime counter (user error correction). |

### Numbers (user-tunable)

| Entity ID | Range | Description |
|---|---|---|
| `number.idegis_brain_target_turnovers_per_day` | 0.5 – 3 | Default 1.0 (TFP minimum for residential). |
| `number.idegis_brain_pump_nominal_w` | 0 – 5000 | Auto-learned from history, override for diagnostics. |
| `number.idegis_brain_overcurrent_margin_pct` | 5 – 50 | Default 20 %. |

## First-minutes filter

Reason: measured pH/salt during the first minutes after pump start are
unreliable — sensor is still equilibrating with bulk water, valves
opening, etc.

Rule v1: while `session_age_seconds < FIRST_MINUTES_WINDOW_S` (default
300), `binary_sensor.idegis_brain_first_minutes_window = on` and the
synthetic bands ignore the in-session puntual values; they keep the
`last_session_*_avg` as the trusted source.

## Optimal pump time algorithm

```
recommended_minutes_today = max(
    base_from_temperature_table(water_temp),
    turnover_minutes(volume, nominal_flow, target_turnovers_per_day)
) * chemistry_correction(ph_band, salt_band, production_band)
```

### `base_from_temperature_table`

Derived from TFP heat-load curves. Indoor pool simplification:

| Water temp | Base minutes/day |
|---|---|
| < 18 °C | 30 |
| 18 – 24 °C | 60 |
| 24 – 28 °C | 120 |
| 28 – 32 °C | 240 |
| 32 – 36 °C | 360 |
| > 36 °C | 480 |

### `turnover_minutes`

```
turnover_minutes = (volume * target_turnovers_per_day / nominal_flow) * 60
                 = (37 * 1.0 / 12) * 60 ≈ 185 min/day
```

### `chemistry_correction`

| Condition | Multiplier |
|---|---|
| All bands `ok` | 1.0 |
| Any band in `warning_*` | 1.2 |
| pH or salt in `danger_*` | 1.5 (cap) |
| Production saturated 2+ sessions | 1.3 |

### Historical learning (v2, after first month)

Compare 7-day rolling `runtime_minutes_week` against achieved
`health_score` average. If high runtime + low health → user is
overworking the pump (suggest dosing). If low runtime + high health →
user can reduce (suggest cutting). Surface as an opinion in the weekly
report, not enforced.

## Pump anomaly detection

For each Shelly channel (pump and cleaner):

| Signal | Condition | Result |
|---|---|---|
| Overcurrent | `power > nominal_w * (1 + margin)` for >30 s | `anomaly = on` + Telegram |
| Dry running | `switch.state == on` AND `power < nominal_w * 0.2` for >60 s | `anomaly = on` + Telegram + auto turn_off if `auto_emergency_stop = true` |
| Stuck contactor | `switch.state == off` AND `power > 5 W` for >60 s | `anomaly = on` + Telegram (user must reset breaker) |

`nominal_w` is learned: 30-day rolling mean of `power` while `switch == on`. Floor 100 W to avoid noise.

## Weekly email report (Sunday 20:00 local)

HTML, single column, mobile friendly. Sections:

1. **Health score** — large gauge, 7-day average + delta.
2. **Vital signs** — pH/salt/temp/production min-avg-max-band per day.
3. **Filtration** — runtime vs recommended per day, kWh, anomalies.
4. **Cleaner usage** — runtime, kWh, last anomaly if any.
5. **Cell production** — saturated days flag.
6. **Open issues** — any Telegram alert that fired during the week.
7. **Suggestions** — one or two text snippets from `historical_learning`.

Template rendered with Jinja2. Inline CSS only (no external links).
Inline base64 SVG for icons. PNG charts via matplotlib (optional v2).

## MQTT setup

The add-on requires the **Mosquitto broker** add-on (or any MQTT broker
HA can talk to). Auto-discovery topics:

```
homeassistant/sensor/idegis_brain_<key>/config        ← discovery message
homeassistant/sensor/idegis_brain_<key>/state         ← value updates
```

Discovery payload includes `device` block so all entities aggregate under
a single device card in HA called "Idegis Pool Brain".

## Service expose

The add-on calls HA Core via `http://supervisor/core/api/services/<domain>/<service>`
with `Authorization: Bearer $SUPERVISOR_TOKEN` (injected by Supervisor when
`homeassistant_api: true`).

Calls used:
- `switch.turn_on` / `switch.turn_off` for pump, cleaner.
- `notify.<entity>` for Telegram and email.
- `automation.trigger` for the weekly report manual button.

## Frontend (ingress)

`/api/brain/state` GET → JSON snapshot of all synthetic entities + last
24 h history.

`/api/brain/ack/<alert_id>` POST → acknowledge an alert.

`/api/brain/run-report` POST → fire the weekly report on demand.

`/` serves the comic dashboard SPA from `static/`. Plain vanilla JS,
fetches `/api/brain/state` on a 30 s interval. No build step.

## Persistence

`/data/state.sqlite` — runtime accumulator, anomaly history, sent email
log.

`/data/charts/` — generated PNGs for the weekly email (if used).

## Versioning

Starts at `0.1.0`. Lockstep with the `addon/` (capturer) addon? **No**.
They are independent. The capturer might bump version due to codec work,
the brain might bump due to dashboard tweaks — they don't need to track
each other.

## Open decisions to resolve while coding

- [ ] How to handle the case where the user has no Mosquitto broker
      installed — auto-detect and fail with a helpful message.
- [ ] Cleaner channel may be unused — option to disable cleaner watch.
- [ ] First v0.1.0 ships with the dashboard read-only + alerts. Emergency
      stop and weekly report follow in v0.2.0 / v0.3.0.
