# 15 · Pool Brain Lovelace dashboard

Drop-in Lovelace dashboard that surfaces every entity the Pool Brain
add-on publishes, plus the cloud-MITM sensors and the optional RS485
diagnostic line. Uses only **stock HA cards** — no HACS required.

## Install

1. Copy [`dashboards/pool_brain.yaml`](../dashboards/pool_brain.yaml)
   into your HA `/config/dashboards/` directory.
2. Add to `configuration.yaml`:

   ```yaml
   lovelace:
     dashboards:
       pool-brain:
         mode: yaml
         title: Pool Brain
         icon: mdi:brain
         show_in_sidebar: true
         filename: dashboards/pool_brain.yaml
   ```
3. **Configuration → Server controls → Reload Lovelace**.
4. The new entry appears in the HA sidebar.

## Layout

Single view, eight sections (HA renders them as a responsive masonry
grid that adapts to phone / tablet / desktop):

| Section | What |
|---|---|
| **Salud del agua** | Gauge with the 0-100 score + glance of TFP bands + binary diagnostic flags |
| **Constantes vitales** | Session-averaged pH / salt / temp / production + two 24 h history graphs |
| **Filtración** | Recommended-vs-actual minutes, turnovers, motor wattage, kWh week, 7-day runtime history |
| **Limpiafondos** | Switch, learned nominal, kWh today/week, 7-day history |
| **Acciones rápidas** | Toggle pump / cleaner / pool light, run-with-timer scripts, three red emergency-stop buttons |
| **Reporte semanal** | Email recipient helper, "send now" button, last alert |
| **Diagnóstico** | Cloud capturer counters (path A) + RS485 ESP diagnostics (path B) |

## Why not Mushroom / button-card / mini-graph-card

So users without HACS can paste this in. If you're already on the
Mushroom theme, you can layer it via `card_mod` without changing the
YAML — every entity has stable IDs.

## Dependencies

- **Idegis Pool Brain** add-on (this repo) installed and publishing
  via MQTT discovery.
- **Idegis / AstralPool cloud capturer** add-on running so the
  `sensor.idegis_chlorinator_*` entities exist.
- Companion package
  [`ha-packages/pool_brain.yaml`](../ha-packages/pool_brain.yaml)
  loaded (the auto-bootstrap of the add-on handles this on first
  boot).
- Optional: ESP `bus-idegis` for the path-B diagnostic section.
