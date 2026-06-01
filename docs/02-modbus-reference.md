# 02 · Modbus map — Idegis / AstralPool (table v1.62)

Distilled from the official factory table
`20200515 Tabla modbus 1.62 - Elite & control connect.xlsm` (not redistributed
here — see [legal notice](../README.md#legal)).

## Conventions

- **Supported functions**: `0x03` (read holding), `0x04` (read input),
  `0x06` (write single holding), `0x10` (write multiple holding).
- **FORBIDDEN** (cause undefined behaviour on the device): `0x01` read coils,
  `0x05` write single coil, `0x15` write multiple coils.
- **Valid slave addresses**: 1–5. Factory default `2`.
- **Default serial config**: 9600 bps, 8 data bits, even parity, 1 stop bit
  (8E1). The `COM_Setup` holding at `0x01` selects the mode:

  | Value | Mode |
  |---|---|
  | 0 | 9600 8E1 *(default)* |
  | 1 | 19200 8E1 |
  | 2 | 9600 8N2 |
  | 3 | 19200 8N2 |
  | 4 | 9600 8N1 |
  | 5 | 19200 8N1 |

- **Scale convention**: most measurements are unsigned 16-bit integers with
  a fixed factor of 10 or 100. Documented per register below.
- **32-bit convention**: 32-bit values are split across two consecutive
  registers `_lsb` + `_msb`, with the LSB at the lower address.

## Zone map

| Zone | Input (0x04) | Holding (0x03) | Content |
|---|---|---|---|
| Identify | — | `0x00` | Manufacturer ID, model, capabilities, FW/HW |
| Update | `0x00` | `0x14` | Reserved for firmware update |
| System | `0x1A` | — | System status |
| Common | `0x20` | `0x20` | Global status, alarm reset, calibration |
| Flow | `0x30` | `0x30` | Flow detection |
| Electrolysis | `0x40` | `0x40` | Chlorine production, electrode current/voltage |
| pH | `0x50` | `0x50` | pH reading + setpoint + dosing |
| Cl (ORP/PPM) | `0x80` | `0x80` | Redox/PPM + setpoints |
| Temperature | `0xB0` | `0xB0` | Temperature + alarm thresholds |
| Salt / conductivity | `0xC0` | `0xC0` | Salinity + thresholds |
| UV | `0xD0` | `0xD0` | UV lamp (if present) |
| Pressure | `0xE0` | `0xE0` | Pressure switch (if present) |
| Time | `0xF0` | `0xF0` | Sunrise/sunset, RTC |
| Inputs | `0x100` | — | Digital inputs 1-4 |
| Outputs | `0x110` | `0x110` | Relay outputs 1-4 + interlocks |
| Time programs | — | `0x170` | 4 daily periods × 10 timeprograms |
| Slots/probes | `0x120` | `0x1E0` | Probe slots (calibration) |
| Internet | `0x130` | `0x220` | wifi/ethernet status, IP, MAC |
| TFT | — | `0x230` | Screen brightness and language |
| VS pump | `0x140` | `0x240` | Variable-speed pump |
| Valve | `0x150` | `0x250` | Automatic backwash valve |

---

## Identification and configuration (holdings `0x00`–`0x11`)

| Reg | Name | Editable | Default | Notes |
|---|---|---|---|---|
| `0x00` | `ID_Address` | yes | 2 | Modbus slave address |
| `0x01` | `COM_Setup` | yes | 0 | See COM_Setup table |
| `0x02–0x03` | `ID_Manufacturer_hi/lo` | password | 0/178 | Idegis constant |
| `0x04–0x05` | `ID_Product_code_hi/lo` | password | 0x2016 | `0x2016` = g/h electrolyser |
| `0x06` | `ID_Technologies_implemented` | bitmap RO | — | Hardware capabilities |
| `0x07` | `HW Version` | RO | — | |
| `0x08` | `FW Version` | RO | — | |
| `0x09–0x0B` | `MODEL_Serie_hi/mi/lo` | RO | — | 48-bit serial number |
| `0x0C` | `CUSTOMER_code` | password | — | OEM customer code |
| `0x0D` | `ID_Technologies_enabled` | bitmap | — | Which features are active |
| `0x10` | `Watchdog_time` | yes | 0 | Modbus watchdog (s) |
| `0x11` | `Watchdog_config` | yes | 0 | Watchdog behaviour |

---

## Measurements (input registers, function `0x04`, read-only)

| Reg | Name | Unit | Scale | Example |
|---|---|---|---|---|
| `0x51` | `ph_measure` | pH | /100 | 712 → 7.12 |
| `0x81` | `orp_measure` | mV | /1 | 750 → 750 mV |
| `0x83` | `ppm_measure` | ppm | /100 | 159 → 1.59 ppm |
| `0x84` | `ppm_probe_current` | mA | /10 | 159 → 15.9 mA |
| `0xB1` | `temperature_measure` | °C | /10 | 256 → 25.6 °C |
| `0xC1` | `salt_measure` | g/L (ppt) | /100 | 365 → 3.65 g/L (= 3650 ppm) |

## Electrolysis (inputs `0x40`–`0x4D`)

| Reg | Name | Unit | Notes |
|---|---|---|---|
| `0x40` | `electrolysis_status` (bitmap) | — | bit 0 running, bit 1 polarity, bit 2 cover input, bit 3 cover setpoint in use, bit 7 daily g limit reached |
| `0x41` | `production_pct_target` | % | Active setpoint (normal or cover) |
| `0x42` | `production_pct_now` | % | Instantaneous production |
| `0x43` | `current_electrodes` | A | /100 (1741 → 17.41 A) |
| `0x44` | `voltage_electrodes` | V | /100 (1741 → 17.41 V) |
| `0x45` | `g_hour_production_now` | g/h | integer |
| `0x46` | `g_production_today` | g | accumulated from 00:00 |
| `0x47` | `time_electrolysis_today` | min | accumulated from 00:00 |
| `0x48–0x49` | `hours_running_elect_total` | h | uint32 (lsb,msb) |
| `0x4A–0x4B` | `hours_running_elect_partial` | h | uint32 (lsb,msb) |
| `0x4C` | `total_reset_elect` | — | partial hours reset count |
| `0x4D` | `g_production_this_hour` | g | from the start of the current hour |

## pH and Cl dosing pumps — telemetry (inputs)

| Reg | Name | Unit |
|---|---|---|
| `0x57` | `ph_dosage_time_output_1` | min |
| `0x58` | `ph_pct_pump_output_1` | % |
| `0x59` | `ph_dosis_seconds_run_output_1` | s |
| `0x5A–0x5B` | `ph_time_pump_running_total/partial_1` | h |
| `0x87` | `cl_dosage_time_output_1` | min |
| `0x88` | `cl_pct_pump_output_1` | % |
| `0x89` | `cl_dosis_seconds_run_output_1` | s |
| `0x8A–0x8B` | `cl_time_pump_running_total/partial_1` | h |

---

## Setpoints and thresholds (holding registers, function `0x06`)

### Electrolysis (`0x41`–`0x43`)

| Reg | Name | Unit | Default | Notes |
|---|---|---|---|---|
| `0x41` | `setpoint_production_normal` | % | 0 | 0–100 |
| `0x42` | `setpoint_production_cover` | % | 10 | Applied when pool cover is on |
| `0x43` | `g_per_day_limit` | g | 0 | 0 = no limit |

### pH (`0x50`–`0x5E`)

| Reg | Name | Unit | Default |
|---|---|---|---|
| `0x51` | `ph_low_alarm_limit` | pH ×100 | 650 (6.50) |
| `0x52` | `ph_high_alarm_limit` | pH ×100 | 850 (8.50) |
| `0x55` | `ph_seconds_initialization` | s | 0 |
| `0x57` | `setpoint_ph_output_1` | pH ×100 | 720 (7.20) |
| `0x58` | `dosage_time_limit_ph_output_1` | min | 60 |
| `0x59` | `max_pct_pump_ph_output_1` | % | 100 |
| `0x5A` | `intelligent_dosing_rank_ph_output_1` | pH ×100 | 20 |
| `0x5B` | `hysteresis_ph_output_1_on2off` | pH ×100 | 2 |
| `0x5C` | `hysteresis_ph_output_1_off2on` | pH ×100 | 1 |
| `0x5D` | `minutes_dosis_ph_output_1` | min | 15 |
| `0x5E` | `limit_hours_pump_ph_output_1` | h | 100 |

### Chlorine / ORP / PPM (`0x80`–`0x8F`)

| Reg | Name | Unit | Default |
|---|---|---|---|
| `0x81` | `mV_low_alarm_limit` | mV | 650 |
| `0x82` | `mV_high_alarm_limit` | mV | 855 |
| `0x83` | `ppm_low_alarm_limit` | ppm ×100 | 30 (0.30) |
| `0x84` | `ppm_high_alarm_limit` | ppm ×100 | 350 (3.50) |
| `0x87` | `setpoint_orp_output_1` | mV | 750 |
| `0x88` | `setpoint_ppm_output_1` | ppm ×100 | 750 (7.50) |
| `0x89` | `dosage_time_limit_cl_output_1` | min | 0 |
| `0x8A` | `max_pct_pump_cl_output_1` | % | 100 |
| `0x8B` | `intelligent_dosing_range_cl_output_1` | — | 0 |
| `0x8C–0x8D` | `hysteresis_cl_output_1_*` | — | 2 |
| `0x8F` | `limit_hours_pump_output_cl_1` | h | 100 |

### Temperature (`0xB2`–`0xB3`)

| Reg | Name | Unit | Default |
|---|---|---|---|
| `0xB2` | `threshold_low_temperature` | °C ×10 | 150 (15.0) |
| `0xB3` | `threshold_high_temperature` | °C ×10 | 380 (38.0) |

### Salt (`0xC2`–`0xC3`)

| Reg | Name | Unit | Default |
|---|---|---|---|
| `0xC2` | `threshold_low_salt` | g/L ×100 | 300 (3.00) |
| `0xC3` | `threshold_high_salt` | g/L ×100 | 800 (8.00) |

---

## Alarms (input bits — write `1` to the equivalent holding to reset)

| Input addr | Holding reset | Meaning |
|---|---|---|
| `0x200` | `0x200` | Any active alarm |
| `0x202` | — | Treatment halted (e.g. calibration mode) |
| `0x240` | `0x240` | Flow alarm OR (any source) |
| `0x241` | `0x241` | Internal cell bubble |
| `0x242` | `0x242` | Inductive flow switch open |
| `0x250`–`0x252` | `0x25x` | Check cell / low cond / high cond |
| `0x260` | `0x260` | pH low |
| `0x261` | `0x261` | pH high |
| `0x265` | `0x265` | pH tank empty |
| `0x266` | `0x266` | pH pumpstop |
| `0x267` | `0x267` | pH pump fuse |
| `0x268` | `0x268` | pH pump maintenance (hours) |
| `0x270`–`0x271` | `0x27x` | ORP low/high |
| `0x272`–`0x273` | `0x27x` | PPM low/high |
| `0x278` | `0x278` | Cl pump fuse |
| `0x280`–`0x281` | `0x28x` | Temperature low/high |
| `0x290`–`0x291` | `0x29x` | Salt low/high |
| `0x2A0`–`0x2A1` | `0x2Ax` | UV ballast / UV fuse |

---

## Time programs (holdings `0x170`–`0x186`, 10 timeprogs)

Each timeprog has 4 periods (start/stop) + 3 config bits + crepuscular
offsets (sunrise/sunset).

| Reg | Name |
|---|---|
| `0x170–0x171` | period_0 start/stop |
| `0x172–0x173` | period_1 start/stop |
| `0x174–0x175` | period_2 start/stop |
| `0x176–0x177` | period_3 start/stop |
| `0x178` | crepuscular_conf_bits |
| `0x179` | crepuscular_sunRiseOffset |
| `0x17A` | crepuscular_sunSetOffset |
| `0x17C–0x186` | next timeprog (same pattern) |

Time format is `HHMM` (e.g. 1430 = 14:30).

---

## Relay outputs (holdings `0x110`–`0x12E`)

Four configurable outputs (`Output 1`–`Output 4`), each with:

- `output_x_1` / `output_x_2` — base configuration (mode, source)
- `enclavamiento_input` — interlock digital input
- `enclavamiento_time_hysteresis` — time hysteresis
- `enclavamiento_modo` — `'0' / '1' / 'A' / 'N'` (off / on / auto / no)
- `enclavamiento_setpoint`, `enclavamiento_value_hysteresis`

Status telemetry is in input registers `0x1100` / `0x1120` etc. (bit 0 = on/off,
bit 8 = interlock mode).

---

## TODO at first pairing

1. Confirm real slave address (default 2 or changed in this SKU?).
2. Confirm UART configuration (9600 8E1?).
3. Read holding `0x06` to validate the actual capability bitmap.
4. Read `0x09–0x0B` to record this unit's serial number.
5. Identify which outputs (1-4) are wired and to what loads (filter pump,
   auto-fill, lights, etc.).
