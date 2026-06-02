# 01 · Hardware

## Reference device

**Idegis Neolysis Neo2-24PH/S**

| Field | Value |
|---|---|
| Family | Neolysis (salt electrolysis + UV optional, Multi-Tec platform) |
| Output | 24 g/h chlorine |
| pH control | Built-in (peristaltic pump + pH probe) |
| Suffix `/S` | Variant with pH probe pre-mounted from factory |
| Chlorination | Yes (variable g/h output) |
| ORP / Redox | Not from factory on this SKU (free slot available) |
| Temperature | Yes (measured at the cell) |
| Salt | Yes (computed from electrode current and voltage) |
| Flow detection | Yes/no detection only (no m³/h flowmeter) |
| Modbus | RTU slave, 9600/19200 bps, 8E1/8N2/8N1, address 1-5 (default 2) |
| Secondary Modbus | Yes — the PCB exposes a second Modbus slave (`secondary_modbus_slave` bit in capability bitmap) |
| Relay slot | Yes — extension slot for additional outputs |
| Cloud app | Poolstation (optional wifi module) |

## Capability bitmap (holding register `0x06`)

The chlorinator publishes its supported features as a bitmap at holding
register `0x06` (`ID_Technologies_implemented`). This is the source of truth
for what the unit can actually do. Read it on the first pairing — the
following is the expected layout for the `Neo2-24PH/S` SKU:

| Bit | Name | Meaning | Expected |
|---|---|---|---|
| 0 | electrolysis | Salt electrolysis cell | ✅ |
| 1 | ph | pH probe slot present | ✅ |
| 2 | cl-orp | ORP probe slot present | ⚠ slot only, not populated |
| 3 | cl-ppm | Amperometric PPM probe slot present | ⚠ slot only, not populated |
| 4 | temperature | Temperature measurement | ✅ |
| 5 | salt | Salt level measurement | ✅ |
| 6 | uv | UV lamp can be attached | ✅ (UV lamp present in reference unit) |
| 7 | caudal | m³/h flow measurement | ✅ (flowmeter present in reference unit) |
| 8 | pressure | Filter pressure measurement | ❌ |
| 9 | biopool | Biopool mode | ✅ |
| 11 | secondary_modbus_slave | Second Modbus slave on PCB | ✅ |
| 13 | slot_relay | Relay extension slot | ✅ |
| 15 | electrolysis_low_salt | Low-salt electrolysis | ✅ |

## OEM equivalence with AstralPool (Fluidra)

| Idegis | AstralPool | Notes |
|---|---|---|
| **Domotic 2** | **Elite Connect** | Same device, same Multi-Tec firmware, same Modbus map, same wifi module (Poolstation). The Fluidra/SIBO distributor publishes documentation labelled as Idegis describing the Elite Connect. |
| **Neolysis** | **Neolysis** | Same commercial name in both brands. Some retailers sell it double-branded (e.g. "Neolysis Zero Salt × UV AstralPool" with an Idegis SKU). |
| Tecno Connect | (industrial line) | Multi-Tec industrial. |

This repository is therefore **directly applicable to AstralPool Elite
Connect and AstralPool Neolysis units**.

> ⚠️ **Not to be confused** with **Sugar Valley NeoPool**
> (Hidrolife/Aquascenic/Bayrol/Brilix). That is a different manufacturer
> with a different Modbus map and its own mature HA integration. Similar
> names, unrelated products.

## RS485 adapter (model TBC)

Two common options:

### A) Official Idegis C-MOD kit

Plug-in module designed for the internal Modbus connector on the
chlorinator. Exposes A/B/GND on terminal blocks. Expensive but
plug-and-play, no need to mess with the unit's internal wiring.

### B) Generic RS485 transceiver (~3 €)

The usual eBay/AliExpress modules:

- **MAX485 with manual DE/RE** — needs an extra ESP32 GPIO to toggle
  direction (DE and RE tied together, driven by the ESP). ESPHome
  supports this via `flow_control_pin`.
- **MAX3485 / SP3485 at 3.3 V** — preferred for ESP32 without a
  level shifter.
- **Auto-direction modules (XY-017 / XY-K485 and similar)** — no GPIO
  control needed. Recommended for a simple first deployment. Some
  variants need 5 V Vcc.

For a first deployment we recommend the **5 V auto-direction module** powered
from the ESP32's VIN through a USB-C 5 V supply.

## ESP32

Any modern ESP32 works (DevKit-C v4, S3, WROOM-32 etc.). Pick one with USB-C,
stable wifi and at least two free hardware UARTs (UART0 reserved for
flashing/logs — use UART1 or UART2 for RS485). If you plan to add I²C
sensors (e.g. ADS1115 for the filter pressure transducer), reserve GPIO21
and GPIO22 for the bus.
