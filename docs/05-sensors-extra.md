# 05 · Optional external sensors (<100 € each, AliExpress)

The Idegis already measures pH, ORP (if the slot is populated),
temperature, salinity and production telemetry. These extras cover
what the chlorinator does **not** measure.

> ⚠️ In a covered pool at ~37 °C **nothing submerged in the pool basin
> survives long enough to be useful**. All external sensors below must
> live in the equipment room or in the bypass loop, not in the pool.

## Ranked by value for money

| # | Sensor | Purpose | Price | Priority |
|---|---|---|---|---|
| 1 | 0–5 bar G1/4" pressure transducer + ADS1115 | Dirty filter, backwash alarm | 10–20 € | ⭐⭐⭐⭐⭐ |
| 2 | DS18B20 waterproof + LM393 leak sensor | Cabinet temp + flood detection | 5 € | ⭐⭐⭐⭐⭐ |
| 3 | JSN-SR04T ultrasonic | Pool water level (via skimmer cap) | 8–10 € | ⭐⭐⭐⭐ |
| 4 | DFRobot Gravity ORP + BNC platinum probe | Redundant ORP (cross-check) | 45–60 € | ⭐⭐⭐ |
| 5 | RS485 Modbus turbidity 0–1000 NTU | Filtration quality | 60–95 € | ⭐⭐ |
| 6 | Amperometric free-chlorine probe | Real Cl level (vs ORP proxy) | 60–90 € | ⭐ |

## Details

### 1. Filter pressure (top pick)

Piezoresistive G1/4" transducer, 0–5 bar, ratiometric `0.5–4.5 V` output
(preferred) or `4–20 mA`.

- Brands frequently found on AliExpress: **Eastsensor**, **Heyuan**,
  **Anpoiner**, generic.
- Read with an **ADS1115 16-bit I²C ADC** (~4 €) for clean resolution.
  The ESP32 built-in ADC is noisy at the top of the range.
- For `4–20 mA` variants: either a tiny converter module (~5 €) or a
  250 Ω shunt resistor to drop to 1–5 V.
- Mounting: a brass or PVC G1/4" tee on the filter outlet (after the
  analog gauge so the manual gauge stays as fallback).
- **Why it is the top pick**: detects a dirty filter without opening the
  lid, lets you schedule an automated backwash when ΔP crosses a threshold,
  raises an obstruction alarm.

### 2. Cabinet temperature + leak detection

- **DS18B20 waterproof 1-Wire** (2–3 €): stick to the Neolysis heatsink
  or cabinet side wall to monitor overheating.
- **LM393 comparator leak sensor** (2–3 €): tape or rod sensor on the
  equipment room floor. Digital output to an ESP32 GPIO.
- Two useful sensors for 5 € total.

### 3. Water level (JSN-SR04T)

Waterproof ultrasonic with 2–3 m external probe cable.

- Mount in the skimmer lid or compensation tank, pointing down.
- Pinout: VCC 5 V (watch the logic level — use a divider on the echo line
  down to 3.3 V), GND, TRIG, ECHO.
- Used for low-level alarm + automated refill via a latch solenoid.
- More expensive alternative: 4–20 mA submersible hydrostatic probe
  (25–45 €) if you want absolute cm precision.

### 4. Redundant ORP

Useful only if your SKU has the ORP slot populated.

- **DFRobot Gravity ORP** analog module + BNC platinum probe: ~50 €
  combined.
- Calibration with 220 mV (40–50 €/200 ml) or 468 mV reference solution.
- Probe lifetime 1–2 years; storage humidity matters.
- Use it to detect drift on the factory probe (if both read >100 mV apart
  for several days → recalibrate).

### 5. Turbidity

- **DFRobot SEN0189 analog** (8–15 €): qualitative only ("clear / turbid"),
  sensitive to bubbles and bio-fouling. Fine as a yes/no signal.
- **RS485 Modbus 0–1000 NTU calibrated probe** (60–95 €): much more
  reliable. Shares the bus with the Idegis (different slave address) or
  goes on a second UART of the ESP32.

### 6. Free chlorine

Possible but **high-maintenance**: monthly DPD calibration, 6–12 month
lifetime, drifts with chloramines. Only worth it if you enjoy water
chemistry. We recommend deferring — pH + ORP + salt from the Idegis already
control disinfection; a weekly manual DPD test covers the rest.

## Do not buy

- **Generic Gravity TDS** (10 €): saturates in salt water, useless. The
  Idegis already gives salinity.
- **Chinese "6-in-1" multiparameter probes** (40 €): rebadged cheap
  electrodes without real calibration.
- **Digital cyanuric acid sensors**: there is no real electrochemical sensor
  under 500 €. Use test strips or DPD.
- **Calcium hardness / alkalinity electronic sensors**: require chemical
  titration, no viable electronic equivalent.
- **Reusable colorimetric DPD chlorine "sensors"**: not real sensors.

## Starter BOM (≈ 67 €)

| Item | Estimated cost |
|---|---|
| ESP32 DevKit-C v4 | 7 € |
| IP65 enclosure + cable glands | 8 € |
| Auto-direction RS485 module | 3 € |
| 0–5 bar pressure transducer | 12 € |
| ADS1115 I²C ADC | 4 € |
| DS18B20 waterproof | 3 € |
| LM393 leak sensor | 2 € |
| JSN-SR04T ultrasonic | 8 € |
| Dedicated 5 V supply | 10 € |
| Wiring, connectors, extras | 10 € |
| **Total** | **~67 €** |
