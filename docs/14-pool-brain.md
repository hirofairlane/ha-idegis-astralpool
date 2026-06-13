# 14 · Pool Brain — the closed-loop add-on

`idegis_pool_brain` is the second add-on shipped in this repo. It is the
**brain** that sits on top of the raw `idegis_capturer` telemetry and
turns it into:

- a one-number **health score**,
- TFP-aware **bands** on every measurement,
- a **smart filtration schedule**,
- **pump anomaly detection** with optional emergency stop,
- a **weekly HTML email report**,
- and a **comic-styled ingress dashboard**.

All synthetic entities are published into Home Assistant through MQTT
discovery — there is no custom integration to install. The add-on owns
its own MQTT device card (`Idegis Pool Brain`) so the entities aggregate
visually in HA.

## Where it sits in the stack

```
┌─────────────────────────────┐    ┌─────────────────────────────┐
│ Chlorinator (Idegis)        │    │ Shelly Pro 4PM              │
│ - cloud HTTP polling        │    │ - filter pump power         │
└────────────┬────────────────┘    │ - cleaner pump power        │
             │                     └───────────┬─────────────────┘
             ▼                                 │
┌─────────────────────────────┐                │
│ idegis_capturer add-on      │                │
│ - reverse proxy on :80      │                │
│ - JSON state on :8765       │                │
└────────────┬────────────────┘                │
             │                                 │
             │  GET /api/idegis/state          │
             ▼                                 ▼
       ┌─────────────────────────────────────────────────┐
       │ idegis_pool_brain add-on                        │
       │ - aggregator (30 s tick)                        │
       │ - pump_watch (10 s tick, anomaly + emergency)   │
       │ - MQTT publisher with HA auto-discovery         │
       │ - APScheduler weekly report                     │
       │ - Comic dashboard on /ingress                   │
       └────────────┬────────────────────────────────────┘
                    │ MQTT discovery + commands
                    ▼
              Home Assistant Core
              (entities, automations,
               dashboards, voice)
```

The brain reads from the capturer and from HA states, never directly
from the chlorinator. This makes it easy to mock for unit tests.

## Anatomy of one tick

Every 30 s the aggregator:

1. Fetches `/api/idegis/state` from the capturer.
2. Reads the live HA states for the pump switch + power and the cleaner
   switch + power (if configured).
3. Updates the persistent per-day counters
   (`runtime_minutes`, `filter_kwh`, `cleaner_kwh`).
4. Picks the trusted measurements from the snapshot — prefers
   `last_session_*_avg` over puntual readings. If a session is younger
   than `first_minutes_window_s`, puntual readings are flagged as
   unreliable via `binary_sensor.idegis_brain_first_minutes_window`.
5. Computes the bands and the weighted health score.
6. Computes the recommended minutes (TFP heat-load + turnover +
   chemistry multiplier).
7. Publishes everything through MQTT.
8. Caches a JSON snapshot under `AGG.snapshot` for the ingress
   dashboard to render.

The pump anomaly watchdog runs in parallel every 10 s. See
[`SPEC.md`](../addon-pool-brain/SPEC.md) for the exact thresholds.

## Filtration time algorithm

The user's empirical rule was *"1 h/day in summer, 1 h/week the rest
of the year"*. Pool Brain replaces it with a transparent formula:

```
base = base_minutes_from_temperature(water_temp)
       # 30 m at <18 °C → 480 m at >36 °C
turn = (volume_m3 × target_turnovers_per_day / nominal_flow_m3_h) × 60
       # 37 m³ × 1.0 / 12 = 185 min/day
multiplier =
   1.5 if any band danger
   1.3 if production saturated
   1.2 if any band warning
   1.0 otherwise

recommended_minutes_today = max(base, turn) × multiplier
```

For the reference installation (37 m³, Neolysis Neo2-24 ~12 m³/h)
this gives 185 min/day in summer (32 °C), 60 min/day at 24 °C, scaled
up if chemistry drifts.

Historical learning is documented as a v2 enhancement in
[`SPEC.md`](../addon-pool-brain/SPEC.md).

## Pump anomaly detection

For each watched Shelly channel:

- **Overcurrent**: `power > nominal × 1.2` for > 30 s. Indicates blocked
  impeller or closed valve.
- **Dry running**: `switch == on` AND `power < nominal × 0.2` for > 60 s.
  Indicates the motor is spinning without water. With
  `auto_emergency_stop = true`, the brain automatically calls
  `switch.turn_off` to prevent the seal from burning.
- **Stuck contactor**: `switch == off` AND `power > 5 W` for > 60 s.
  Welded relay. User must flip the breaker — the brain only alerts.

Telegram alerts deduplicate by anomaly kind, so a long-running
overcurrent only sends one message until the state recovers.

## Weekly email report

Default schedule: every Sunday at 20:00 local. The report is rendered
from `templates/weekly_email.html.j2`, inline CSS only so it survives
gmail / outlook stripping. Sections:

1. Health score header.
2. Vital signs (pH / salt / temp / production).
3. Filtration runtime vs recommended.
4. Cleaner usage.
5. Production saturated days (if any).
6. Suggestions (v2).

If `notify_email_service` is not configured, the brain falls back to a
compressed Telegram summary so users without SMTP still receive a
weekly digest.

## Emergency stop entry points

Three independent entry points so the user can react fast:

1. **Comic dashboard buttons** — three red comic-styled buttons (PUMP,
   CLEANER, ALL).
2. **MQTT button entities** — `button.idegis_brain_emergency_stop_*`
   appear in HA automatically; can be wired to physical buttons, voice
   commands or alerts.
3. **HTTP POST** — `/api/brain/emergency-stop/{all|pump|cleaner}` for
   third-party integrations.

In all three cases the brain calls `switch.turn_off` against the
configured entity and sends a Telegram confirmation.

## Why MQTT discovery instead of a custom_component

- Add-ons cannot register custom HA entities directly. They have to
  publish them via the supervisor REST API (limited) or via MQTT
  (well supported by HA core).
- MQTT discovery requires zero glue code on the HA side once the
  Mosquitto broker is set up.
- Users keep ownership of their entities and can rename / disable them
  without forking the add-on.
- Future iterations can add a custom_component that *consumes* the same
  add-on for users who prefer a config_flow UI.

## See also

- [`SPEC.md`](../addon-pool-brain/SPEC.md) — internal architecture
  notes, kept in repo for context preservation.
- [`ha-packages/pool_brain.yaml`](../ha-packages/pool_brain.yaml) —
  drop-in package with helpers, scripts and automations that bridge
  the brain with the rest of your HA configuration.
- [docs/07-water-chemistry.md](07-water-chemistry.md) — Trouble Free
  Pool target ranges, source of the bands.
- [docs/13-alerts-and-jarvis.md](13-alerts-and-jarvis.md) — division of
  responsibilities between the brain (deterministic alerts) and Jarvis
  (qualitative suggestions).
