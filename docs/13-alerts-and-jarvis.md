# 13 · Alerts & the Jarvis split

Two-layer alerting strategy designed to avoid notification fatigue.

## Layer 1 — Home Assistant native alerts

Reactive, deterministic, immediate. Fired by the HA automation engine
on hard thresholds. These live in
[`ha-packages/idegis_alerts.yaml`](../ha-packages/idegis_alerts.yaml)
and the user only needs to drop the file into `/config/packages/` (or
include it from `configuration.yaml`) and reload automations.

| Alert | Trigger |
|---|---|
| **Equipo offline** | `binary_sensor.idegis_chlorinator_online == off` for > 10 min |
| **pH medio fuera de banda** | last-session pH avg outside 7.2 .. 7.8 |
| **Producción saturada** | last-session production_pct avg > 95 % |
| **Temperatura agua > 36 °C** | instantaneous reading above 36 °C for > 30 min |

These are wired through `input_text.idegis_notify_service` which the
user can edit live without touching the pack — defaults to the
existing `notify.telegram_bot_<...>` service on the reference install.

### Why these specific thresholds?

They come from the Trouble Free Pool guidance for residential
SWG + UV pools (see [`docs/07-water-chemistry.md`](07-water-chemistry.md))
and from the empirical observation that the chlorinator only emits
measurements while it is alimented — hence "last session avg" is the
right unit, not the noisy instantaneous reading.

## Layer 2 — Jarvis (cualitative analysis)

What we explicitly **do not** put into the HA pack is anything that
needs interpretation:

- *"The pH is drifting downward by 0.1 per day — check the acid bottle"*
- *"The cell has been running > 90% for three days, salinity might be
  too low"*
- *"Temperature climbed 2 °C since yesterday — algae risk if pH also
  drifts"*
- *"The chlorinator was offline most of last weekend — was that
  intentional?"*

That kind of work belongs in a periodic agent that has the full
history, the cloud telemetry, the weather, the calendar and the
ability to write nuanced Spanish. The user already runs **Jarvis** as
the personal LLM agent on LXC 104; integrating with it is a matter of
giving it read access to:

- `/api/idegis/state` for the current snapshot.
- `/api/idegis/history?n=200` for the recent corpus.
- The HA REST API for cross-references (pump runtime via
  `sensor.shellypro4pm_30c6f7836a6c_energy_3`, weather, etc.).

A first sensible cron cadence:

- **Every 8 hours** (already used by Jarvis for other duties):
  read `last_session`, append a one-line summary to a persistent
  worklog, do not notify unless something is genuinely out of band.
- **Daily at 09:00**: produce a Spanish-language brief over Telegram
  summarising the previous 24 h (avg pH/temp/salt/prod, total
  electrolysis time, any incidents).
- **On-demand**: when the user asks "¿cómo está la piscina?" Jarvis
  pulls fresh state and answers conversationally.

The point is that the HA pack should never wake the user up with a
borderline reading, and Jarvis should never page the user when a
real failure is happening — the HA pack handles the latter.

## Installing the HA pack

1. Make sure `homeassistant.packages` is enabled in
   `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
2. Drop `ha-packages/idegis_alerts.yaml` into `/config/packages/`.
3. Settings → System → Restart Home Assistant.
4. Optionally edit `input_text.idegis_notify_service` from the UI to
   point at any notify service (telegram, mobile app, signal, etc.).
