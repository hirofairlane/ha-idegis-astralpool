# 03 · ESP32 ↔ Idegis wiring (RS485)

## Topology

```
┌─────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│ Idegis      │      │ TTL ↔ RS485 module    │      │ ESP32                │
│ Neolysis    │ A,B  │ (MAX485 / SP3485 /    │ TX,RX│                      │
│ Modbus RTU  │◄────►│ auto-direction)       │◄────►│ UART2 GPIO16/17      │
│ slave=2     │      │ Vcc/GND 3.3 V or 5 V  │      │ 3.3 V                │
└─────────────┘      └──────────────────────┘      └──────────────────────┘
                                                            │ WiFi
                                                            ▼
                                                     ┌──────────────┐
                                                     │ Home Assistant│
                                                     │ ESPHome API   │
                                                     └──────────────┘
```

## RS485 adapter (TBC for this build)

### A) Official Idegis C-MOD

Plug-in module on the internal Modbus connector. Exposes A/B/GND on terminal
blocks. Plug-and-play, no internal wiring required, but expensive.

### B) Generic RS485 transceiver (≈ 3 €)

Common eBay/AliExpress modules:

- **MAX485 with manual DE/RE** — needs an extra ESP32 GPIO for direction
  control (DE and RE tied together). ESPHome handles it through
  `flow_control_pin`.
- **MAX3485 / SP3485 at 3.3 V** — preferred for ESP32 (no level shifter).
- **Auto-direction modules (XY-017 / XY-K485 etc.)** — no GPIO control,
  simplest first deployment. Some variants require 5 V Vcc.

Recommended starter combo: a **5 V auto-direction module** powered from the
ESP32 USB-C 5 V rail (VIN).

## ESP32 pinout (DevKit-C v4)

| Function | ESP32 GPIO | RS485 module pin |
|---|---|---|
| UART2 TX | GPIO17 | TXD / DI |
| UART2 RX | GPIO16 | RXD / RO |
| RS485 DE/RE (if manual) | GPIO4 | DE+RE |
| GND | GND | GND |
| 3.3 V or 5 V | 3V3 / VIN | VCC |

Modbus side:

| Adapter pin | Idegis pin |
|---|---|
| A (D+) | A (Modbus +) |
| B (D-) | B (Modbus -) |
| GND | GND (common) |

## Termination and biasing

- **Termination**: 120 Ω at **both ends** of the bus on cable runs longer
  than ~5 m. Short runs (ESP next to the cabinet) often work without it.
  Most Chinese modules already include a 120 Ω resistor or a jumper —
  check before adding another in parallel.
- **Fail-safe biasing**: if the bus floats when nobody transmits, garbage
  bytes can appear. Many modules include pull-up / pull-down resistors
  (≈ 680 Ω). If you see desyncs, this is usually the cause.

## ESP32 power

Three options in order of preference:

1. **Dedicated 5 V supply** inside the cabinet (industrial USB charger,
   1 A). Galvanically isolated from the chlorinator electronics.
2. **5 V tap from the Idegis PCB** if available and dimensioned for it —
   *check the manual before tapping*.
3. **PoE splitter** if the cabinet already has ethernet — more stable long
   term.

## Electrical safety

- The pool cabinet carries 230 VAC and high-current electronics (>10 A on
  the electrolysis side). Keep the ESP32 + RS485 module in an **IP65
  enclosure** physically separated from the power side. Avoid ground loops
  by wiring the Modbus GND in a star topology from the Idegis side.
- Do not power the ESP32 directly from a 230 V line with cheap modules
  without galvanic isolation. Hi-Link HLK-PM01 is acceptable but **not
  certified for pool environments**.
- Ideally place the ESP32 + module in an enclosure with cable glands and an
  external wifi antenna if the box is metallic.

## Reserved GPIO for future extras

Reserve these pins now so you do not have to rewire later if you add the
optional external sensors from
[docs/05-sensors-extra.md](05-sensors-extra.md):

- I²C (ADS1115 for filter pressure) → GPIO21 SDA, GPIO22 SCL
- DS18B20 ambient temperature → GPIO5 (1-Wire with 4.7 kΩ pull-up)
- Leak sensor digital input → GPIO13
- JSN-SR04T ultrasonic → GPIO18 trig, GPIO19 echo
