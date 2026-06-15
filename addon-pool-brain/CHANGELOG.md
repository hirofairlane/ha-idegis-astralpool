# Changelog

## 0.3.0 — 2026-06-15

- **24 h sparklines** on the comic dashboard. Each vital signs panel
  (pH, salt, temperature) plus the health score gauge gets an SVG
  sparkline showing the last 24 h of decimated samples — pure vanilla
  JS, no external libs.
- **New endpoint** `GET /api/brain/history` exposes the ring-buffer
  snapshot as JSON so other dashboards / scripts can reuse it.
- **`history.py`** module: in-memory ring buffer with built-in
  decimation. Default capacity 48 samples × decimation 60 ticks =
  24 h at 30 s aggregator cadence. Easily testable.

## 0.2.0 — 2026-06-15

- **Auto-learned pump nominal W**. New `nominal_learner.py` module
  applies an exponential moving average (alpha 0.02, ~8 min half-life)
  over the live wattage while the pump switch is on and the reading is
  above the noise floor (50 W). The learned value persists in
  `/data/state.json` and survives restarts.
- **Pump anomaly logic extracted** into a side-effect-free
  `anomaly.decide(sample, latched, now)` function. The previous
  `pump_watch.py` became a thin orchestrator: it samples HA, calls
  `nominal_learner.update`, calls `anomaly.decide`, reacts (Telegram +
  optional auto-stop), and publishes MQTT. The whole decision is now
  unit-testable without HA or MQTT.
- **Bug fix**: latched timers used 0.0 as the "not active" sentinel,
  which collided with a legitimate `now=0` on the first tick. Replaced
  with `None`.
- **New MQTT diagnostic entities**:
  `sensor.idegis_brain_pump_nominal_w_learned` and
  `sensor.idegis_brain_cleaner_nominal_w_learned` so the user can watch
  the EMA converge.
- **Test coverage** jumped from 66 to 90 cases: every transition of
  the anomaly state machine is now covered, plus the full lifecycle of
  the learner (rejection of off-state samples, EMA convergence, hard
  floor enforcement, alpha override).

## 0.1.0 — 2026-06-13

First public release.

- Subscribes to the companion `idegis_capturer` `/api/idegis/state` and
  surfaces ~20 synthetic entities via MQTT discovery
  (`device = "Idegis Pool Brain"`).
- TFP-based pH / salt / temperature / production bands.
- Weighted health score (0-100).
- Recommended pump minutes computed from TFP heat-load table +
  turnover requirement + chemistry correction.
- Per-day runtime counter (resets at 00:00) and rolling 7-day runtime.
- Filter and cleaner kWh integration from Shelly Pro 4PM channels.
- Pump / cleaner anomaly watchdog (overcurrent / dry-running / stuck
  contactor) with optional auto emergency stop.
- Emergency stop buttons (`button.idegis_brain_emergency_stop_*`).
- Comic-styled ingress dashboard (vanilla HTML/CSS/JS).
- Weekly HTML email report scheduled via APScheduler. Falls back to a
  compressed Telegram summary if no email service is configured.
- First-minutes window flag (default 5 min) marks measurements taken
  right after pump start as unreliable — the brain ignores them and
  surfaces this state in `binary_sensor.idegis_brain_first_minutes_window`.
