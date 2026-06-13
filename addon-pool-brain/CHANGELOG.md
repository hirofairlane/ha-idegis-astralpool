# Changelog

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
