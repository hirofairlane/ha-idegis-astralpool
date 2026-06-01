# 04 · ESPHome configuration and HA entities

## Why ESPHome, not Home Assistant's native `modbus:` YAML

- **Electrical isolation**: the ESP32 sits next to the chlorinator, HA lives
  elsewhere. If HA reboots, the ESP keeps sampling.
- **Reconnection and self-healing**: ESPHome retries and re-syncs the bus by
  itself.
- **Local latency**: critical safety automations (stop the dosing pump if no
  flow) can live on the ESP, no HA round-trip.
- **OTA**: deploy changes without touching HA config.
- **Reusable**: the resulting YAML is directly publishable as a community
  config (this repo's goal).

## Mapping strategy

Each zone of the Excel (input/holding) maps to one block of
`modbus_controller` entities (`sensor` / `binary_sensor` / `number` /
`switch` / `select` / `text_sensor`), grouped by zone.

Polling intervals:

- `update_interval: 10s` for instantaneous readings (pH, ORP, temp, salt).
- `update_interval: 60s` for accumulators (g_today, hours, alarms).
- `update_interval: 600s` or `never` (with `lambda`) for static fields
  (HW/FW versions, serial).
- `force_new_range: true` to put a register in its own frame when a zone
  changes or there are gaps.

## HA entities (first delivery)

### Numeric sensors (read-only)

| HA entity | Source | Unit | Notes |
|---|---|---|---|
| `sensor.pool_ph` | input 0x51 ÷100 | pH | precision 0.01 |
| `sensor.pool_orp` | input 0x81 | mV | |
| `sensor.pool_temperature` | input 0xB1 ÷10 | °C | |
| `sensor.pool_salinity` | input 0xC1 ÷100 | g/L | |
| `sensor.pool_production_pct` | input 0x42 | % | actual |
| `sensor.pool_production_pct_target` | input 0x41 | % | active setpoint |
| `sensor.pool_electrode_current` | input 0x43 ÷100 | A | |
| `sensor.pool_electrode_voltage` | input 0x44 ÷100 | V | |
| `sensor.pool_production_g_h` | input 0x45 | g/h | |
| `sensor.pool_production_g_today` | input 0x46 | g | daily accumulator |
| `sensor.pool_electrolysis_minutes_today` | input 0x47 | min | |
| `sensor.pool_electrolysis_total_hours` | input 0x48+0x49 uint32 | h | |
| `sensor.pool_ph_pump_total_hours` | input 0x5A | h | |
| `sensor.pool_ph_pump_pct` | input 0x58 | % | |
| `sensor.pool_ph_pump_dose_seconds_today` | input 0x59 | s | |

### Binary sensors (alarms)

| HA entity | Source bit |
|---|---|
| `binary_sensor.pool_alarm_global` | 0x200 |
| `binary_sensor.pool_treatment_halted` | 0x202 |
| `binary_sensor.pool_flow_alarm` | 0x240 |
| `binary_sensor.pool_cell_bubble` | 0x241 |
| `binary_sensor.pool_flow_switch` | 0x242 |
| `binary_sensor.pool_ph_low` | 0x260 |
| `binary_sensor.pool_ph_high` | 0x261 |
| `binary_sensor.pool_ph_tank_empty` | 0x265 |
| `binary_sensor.pool_ph_pumpstop` | 0x266 |
| `binary_sensor.pool_ph_pump_fuse` | 0x267 |
| `binary_sensor.pool_orp_low` | 0x270 |
| `binary_sensor.pool_orp_high` | 0x271 |
| `binary_sensor.pool_temp_low` | 0x280 |
| `binary_sensor.pool_temp_high` | 0x281 |
| `binary_sensor.pool_salt_low` | 0x290 |
| `binary_sensor.pool_salt_high` | 0x291 |
| `binary_sensor.pool_electrolysis_running` | 0x400 |
| `binary_sensor.pool_cell_polarity_reverse` | 0x401 |
| `binary_sensor.pool_cover_present` | 0x402 |
| `binary_sensor.pool_applying_cover_setpoint` | 0x403 |
| `binary_sensor.pool_dosing_ph` | 0x560 |

### Editable numbers (Modbus writes)

| HA entity | Holding | Range | Unit |
|---|---|---|---|
| `number.pool_setpoint_ph` | 0x57 | 6.50–8.00 | pH (×100 on wire) |
| `number.pool_setpoint_orp` | 0x87 | 600–900 | mV |
| `number.pool_setpoint_production_normal` | 0x41 | 0–100 | % |
| `number.pool_setpoint_production_cover` | 0x42 | 0–100 | % |
| `number.pool_daily_g_limit` | 0x43 | 0–500 | g (0 = no limit) |
| `number.pool_dosage_time_limit_ph` | 0x58 | 0–120 | min |
| `number.pool_max_pct_pump_ph` | 0x59 | 0–100 | % |
| `number.pool_threshold_temp_low` | 0xB2 | 0–25 | °C (×10) |
| `number.pool_threshold_temp_high` | 0xB3 | 25–45 | °C (×10) |
| `number.pool_threshold_salt_low` | 0xC2 | 1.0–4.0 | g/L (×100) |
| `number.pool_threshold_salt_high` | 0xC3 | 4.0–10.0 | g/L (×100) |

### Buttons (alarm resets)

| HA entity | Action |
|---|---|
| `button.pool_reset_global_alarm` | write 0x200 holding = 1 |
| `button.pool_reset_flow_alarms` | write 0x240 holding = 1 |
| `button.pool_reset_ph_alarms` | write 0x26x holdings |
| `button.pool_reset_partial_electrolysis_hours` | write reset 0x4C |

### Diagnostics

- `text_sensor.pool_serial` (read `0x09–0x0B`, hex formatted)
- `text_sensor.pool_fw_version` (`0x08`)
- `text_sensor.pool_hw_version` (`0x07`)
- Capabilities from holding `0x06` bitmap as `binary_sensor` diagnostic
  entities.

## Phased rollout

**Phase 1 — read only (no risk).**
Implement all `sensor` and `binary_sensor` blocks. Validate against the
physical front panel of the Idegis for 1–2 weeks. Only proceed if values
match.

**Phase 2 — safe setpoints.**
Enable `number` entities for pH setpoint, ORP setpoint, normal/cover
production %, alarm thresholds. Use Modbus password if required (some
holdings need a token — register `0x22` `calibration_value` acts as the
contextual token).

**Phase 3 — time programs and outputs.**
Time programs (`0x170+`), relay outputs (`0x110+`), VS pump and valve.
Requires more modelling and testing.

**Phase 4 — HA automations.**
- Push alert when pH is out of band for more than N minutes.
- Reduce production at night via timeprog driven from HA.
- Switch to cover mode when a Lovelace toggle is pressed.
- "Refill pH tank" notification when bit 0x265 triggers.
- Long-term InfluxDB / Grafana history of g/h vs water temperature.

## Known risks

- **Functions 0x01/0x05/0x15 are forbidden** — undefined behaviour. ESPHome
  uses 0x03/0x06/0x10 for holdings by default, so this is automatically
  avoided.
- **Some holdings need a password** (`With Pass` in the original Excel).
  The mechanism appears to be writing a specific value into `0x22` before
  writing the protected register. Pending validation.
- **Changing `ID_Address` or `COM_Setup` can mute the bus**. Treat these
  as diagnostic-only, never expose them as editable `number` entities.
- **Modbus watchdog**: if `0x10 Watchdog_time` is configured and the ESP32
  drops, the chlorinator may enter a safe mode. Decide whether to enable
  it and at what value.

## References

- ESPHome `modbus_controller`: https://esphome.io/components/modbus_controller.html
- ESPHome `uart` (hardware UART recommended): https://esphome.io/components/uart.html
