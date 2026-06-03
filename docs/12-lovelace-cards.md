# 12 · Lovelace card examples

Ready-to-paste Lovelace YAML for the entities the integration exposes.
The exact card composition used on the reference installation (under
`calor-frio` → `piscina`) is reproduced below.

## Header markdown

```yaml
type: markdown
content: >
  ## 🧪 Idegis Neolysis — Agua

  Lecturas en directo desde el cloud del Idegis (capturadas vía DNS
  override + addon `idegis_capturer`). Más info:
  [github.com/hirofairlane/ha-idegis-astralpool](https://github.com/hirofairlane/ha-idegis-astralpool)
```

## Four gauges, side by side

```yaml
type: horizontal-stack
cards:
  - type: gauge
    entity: sensor.idegis_chlorinator_ph
    name: pH
    min: 6.5
    max: 8.5
    needle: true
    severity:
      green: 7.2
      yellow: 7.6
      red: 7.8
  - type: gauge
    entity: sensor.idegis_chlorinator_water_temperature
    name: Temp agua
    min: 15
    max: 40
    needle: true
    unit: °C
    severity:
      green: 25
      yellow: 32
      red: 36
  - type: gauge
    entity: sensor.idegis_chlorinator_salinity
    name: Sal
    min: 0
    max: 5
    needle: true
    unit: g/L
    severity:
      green: 1.5
      yellow: 3
      red: 4
  - type: gauge
    entity: sensor.idegis_chlorinator_chlorine_production
    name: Producción Cl
    min: 0
    max: 100
    needle: true
    unit: "%"
    severity:
      green: 0
      yellow: 70
      red: 95
```

### Why those severity thresholds?

The thresholds come from [Trouble Free Pool](https://www.troublefreepool.com/)
guidance for residential pools with a salt water generator and a UV
lamp (your installation profile):

| Parameter | Green (safe) | Yellow (watch) | Red (act) |
|---|---|---|---|
| pH | 7.2 .. 7.6 | 7.6 .. 7.8 | < 7.2 or > 7.8 |
| Temperature | 25 .. 32 °C | 32 .. 36 °C | > 36 °C (algae risk) |
| Salinity | 1.5 .. 3 g/L (cell range, low-salt SKU) | 3 .. 4 g/L | > 4 g/L |
| Production % | up to 70 % | 70 .. 95 % | > 95 % (electrolyzer saturated) |

Adjust to your pool — see [docs/07-water-chemistry.md](07-water-chemistry.md)
for the TFP references and the full reasoning.

## Diagnostic card

```yaml
type: entities
title: Idegis — diagnóstico cloud
show_header_toggle: false
entities:
  - entity: binary_sensor.idegis_chlorinator_online
    name: Conexión cloud
  - entity: sensor.idegis_chlorinator_polling_rate
    name: Polling rate
  - entity: sensor.idegis_chlorinator_filter_pump_power
    name: Potencia bomba
  - entity: sensor.idegis_chlorinator_request_counter
    name: Contador peticiones
  - entity: sensor.idegis_chlorinator_captured_requests
    name: Peticiones capturadas
  - entity: sensor.idegis_chlorinator_last_seen
    name: Última conexión
  - entity: sensor.idegis_chlorinator_device_serial
    name: Serial equipo
  - entity: sensor.idegis_chlorinator_device_clock
    name: Reloj equipo
```

## Notes

- `sensor.idegis_chlorinator_filter_pump_power` reads from the
  Shelly Pro 4PM channel that the chlorinator is wired to. The
  addon polls Home Assistant for this value (configurable via the
  add-on options) so the `pump_running` flag in `/api/idegis/state`
  is derived from the real-world power draw, not from the logical
  switch state.
- `sensor.idegis_chlorinator_device_clock` is the Unix timestamp the
  chlorinator put in the last `CD` field — decoded back to ISO 8601
  UTC. It is a sanity check: if it drifts away from wall clock the
  device's RTC needs syncing.
