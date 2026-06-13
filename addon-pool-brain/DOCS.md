# Idegis Pool Brain — Add-on docs

Closed-loop pool brain for the Idegis / AstralPool stack. See the
[full README](README.md) for the entity catalogue and SPEC details.

## What it adds to your Home Assistant

This add-on publishes ~20 synthetic entities through MQTT discovery
that summarise the health of your pool, recommend a filtration time
budget, and watch for pump anomalies — all on top of the raw
telemetry that the companion **`idegis_capturer`** add-on already
captures from your chlorinator's cloud traffic.

## What you need before installing

1. A working **`idegis_capturer`** add-on (sibling add-on, same repo).
2. An **MQTT broker** reachable from Home Assistant — the official
   Mosquitto broker add-on works out of the box.
3. The HA `notify.<your_telegram_bot>` service if you want Telegram
   alerts (optional but recommended).
4. An HA `notify.<smtp_or_other>` service if you want the weekly email
   report. You can also just use the Telegram fallback.

## Options walk-through

The defaults are tuned for the reference installation (Idegis Neolysis
Neo2-24PH/S, 37 m³ indoor pool, Shelly Pro 4PM channel 3 = filter
pump, channel 1 = cleaner). Adjust:

- **`pool_volume_m3`** — drives the daily turnover calculation. Be
  honest: an undersized value makes the brain run the pump less than
  needed.
- **`pump_switch_entity`** / **`pump_power_entity`** — your filter pump
  switch and live wattage sensor. Required.
- **`cleaner_*_entity`** — optional. Leave empty to disable the cleaner
  watch.
- **`auto_emergency_stop`** — leave `false` until you trust the dry-run
  detection thresholds for your setup. Once enabled, the add-on will
  automatically turn off a pump that has been spinning dry for > 60 s.

## Sanity-check after first start

- Open the add-on web UI. You should see the comic dashboard with the
  current health score and bands.
- In HA → Settings → Devices, look for the device **"Idegis Pool Brain"**
  with all the entities listed.
- Press the **Send weekly report now** button to verify the email
  service works without waiting for Sunday.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Web UI shows `unknown` everywhere | Capturer down or wrong URL | Check `capturer_base_url` and that the capturer add-on is running. |
| No entities appear in HA | MQTT broker not configured | Install Mosquitto broker add-on and grant access. |
| Telegram alerts not sent | Wrong notify service name | Verify the `notify.*` entity exists under `Developer Tools → Services`. |
| Recommended minutes seems off | Volume / flow misconfigured | Adjust `pool_volume_m3`; flow is auto-detected from chlorinator model. |

## License

MIT. See LICENSE in the repo root.
