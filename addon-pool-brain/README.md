# Idegis Pool Brain — Home Assistant add-on

[![pool-brain tests](https://github.com/hirofairlane/ha-idegis-astralpool/actions/workflows/pool-brain-tests.yml/badge.svg)](https://github.com/hirofairlane/ha-idegis-astralpool/actions/workflows/pool-brain-tests.yml)

Closed-loop pool brain that sits on top of the
[`idegis_capturer`](../addon/) cloud capturer. It turns the raw Idegis
telemetry into TFP-aware bands, a health score, a recommended
filtration schedule, pump anomaly detection with optional emergency
stop, and a weekly HTML email report.

All synthetic entities are published into Home Assistant via **MQTT
discovery** — no custom integration needed. The add-on also exposes a
comic-styled ingress dashboard.

## Highlights

- 🩺 **Pool health score** (0-100) computed from pH, salinity,
  temperature and chlorine production bands.
- 🕒 **Smart filtration schedule** combining TFP heat-load tables, pool
  volume × turnover requirement, and chemistry corrections.
- ⚡ **Pump anomaly watchdog**: overcurrent, dry-running, and stuck
  contactor. Telegram alert per kind. Optional auto emergency stop.
- 🛑 **Emergency stop buttons** exposed both on the add-on dashboard and
  as `button.idegis_brain_emergency_stop_*` MQTT entities.
- 📧 **Weekly HTML email report** (default Sunday 20:00) with vital
  signs, runtime vs recommended, energy, and open issues.
- 📊 **First-minutes filter**: stale-water lectures from the chlorinator
  sensor cavity are excluded from band computation, exposed as
  `binary_sensor.idegis_brain_first_minutes_window`.

See [`SPEC.md`](SPEC.md) for the full design notes.

## Requirements

- The companion **`idegis_capturer`** add-on installed and running on
  the same HA host.
- An **MQTT broker** available to HA (the official Mosquitto broker
  add-on is the easy choice).
- Optional: Telegram notify service for alerts; SMTP notify service for
  the weekly report.

## Quick start

1. Install the **Idegis / AstralPool cloud capturer** add-on and verify
   it's receiving telemetry at `http://localhost:8765/api/idegis/state`.
2. Install **Mosquitto broker** if you don't have one.
3. Install **Idegis Pool Brain** (this add-on).
4. Configure the options (see below), set your pool volume.
5. Open the add-on web UI to confirm bands and recommendations are
   coming in.
6. Drop [`ha-packages/pool_brain.yaml`](../ha-packages/pool_brain.yaml)
   into `/config/packages/` to get the helper input_numbers, scripts and
   complementary automations.

## Configuration

| Option | Default | Description |
|---|---|---|
| `capturer_base_url` | `http://localhost:8765` | Where the companion capturer addon is listening. |
| `pool_volume_m3` | `37` | Pool volume in m³. Drives the turnover requirement. |
| `pump_switch_entity` | `switch.depuradora` | HA switch that controls the filter pump. |
| `pump_power_entity` | `sensor.shellypro4pm_30c6f7836a6c_power_3` | Real-time power for the filter pump. |
| `cleaner_switch_entity` | *(empty)* | Optional cleaner pump switch. |
| `cleaner_power_entity` | *(empty)* | Optional cleaner pump power. |
| `notify_telegram_service` | `notify.telegram_bot_...` | Notify entity for alerts. |
| `notify_email_service` | *(empty)* | Notify entity for the weekly report. |
| `weekly_report_enabled` | `true` | Master toggle for the weekly email. |
| `weekly_report_day` | `sun` | Day of the week. |
| `weekly_report_hour` | `20` | Local hour. |
| `auto_emergency_stop` | `false` | If true, dry-running detection auto turns the affected switch off. |
| `target_turnovers_per_day` | `1.0` | TFP recommends 1.0–2.0. |
| `first_minutes_window_s` | `300` | Seconds at the start of each pump session whose measurements are flagged as unreliable. |

## Entity catalogue published over MQTT

| Domain | Entity | What it tells you |
|---|---|---|
| `sensor` | `idegis_brain_health_score` | 0-100 weighted score. |
| `sensor` | `idegis_brain_ph_band` | `ok` / `warning_*` / `danger_*`. |
| `sensor` | `idegis_brain_salt_band` | Idem against Neolysis low-salt range. |
| `sensor` | `idegis_brain_temperature_band` | `ok` / `warm` / `hot`. |
| `sensor` | `idegis_brain_production_band` | `ok` / `saturated`. |
| `sensor` | `idegis_brain_recommended_minutes_today` | TFP + turnover + chemistry correction. |
| `sensor` | `idegis_brain_recommended_minutes_week` | Rolling weekly target. |
| `sensor` | `idegis_brain_runtime_minutes_today` | Accumulated pump-on time today. |
| `sensor` | `idegis_brain_runtime_minutes_week` | Rolling 7-day. |
| `sensor` | `idegis_brain_filter_kwh_today` | Integrated from the Shelly. |
| `sensor` | `idegis_brain_filter_kwh_week` | Rolling 7-day. |
| `sensor` | `idegis_brain_cleaner_kwh_today` | Optional. |
| `sensor` | `idegis_brain_cleaner_kwh_week` | Optional. |
| `sensor` | `idegis_brain_pump_avg_power` | Last reading from the Shelly. |
| `sensor` | `idegis_brain_turnovers_today` | Achieved turnovers. |
| `binary_sensor` | `idegis_brain_water_healthy` | All bands ok + no anomaly. |
| `binary_sensor` | `idegis_brain_pump_anomaly` | Overcurrent / dry / stuck. |
| `binary_sensor` | `idegis_brain_cleaner_anomaly` | Same logic on the cleaner. |
| `binary_sensor` | `idegis_brain_first_minutes_window` | True while data unreliable. |
| `button` | `idegis_brain_emergency_stop_all` | Press to stop pump + cleaner. |
| `button` | `idegis_brain_emergency_stop_pump` | Press to stop pump. |
| `button` | `idegis_brain_emergency_stop_cleaner` | Press to stop cleaner. |
| `button` | `idegis_brain_run_weekly_report_now` | Fire report on demand. |

## Running the tests

The add-on ships with a pytest suite covering the pure logic (TFP bands,
weighted score, recommended-minutes engine). Tests don't need MQTT or
Home Assistant — they import the modules directly from `rootfs/`.

```bash
cd addon-pool-brain
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Current state: **103 tests passing**.

## License

MIT for code, CC-BY-SA 4.0 for docs.
