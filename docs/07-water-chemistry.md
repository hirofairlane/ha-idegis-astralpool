# 07 · Water chemistry — references and target ranges

Summary of the parameters monitored in Home Assistant and the recommended
target ranges, based on the **Trouble Free Pool (TFP)** community — the
de-facto English-language reference for residential pools with a salt water
generator (SWG).

## Why TFP as a reference

- Method validated by decades of open technical discussion.
- Focused on the **FC/CYA relationship** (free chlorine vs cyanuric acid),
  which most manufacturer manuals oversimplify.
- Specific recommendations for SWG pools — exactly our use case.

## Target ranges for SWG + UV pools

| Parameter | Recommended range | Notes |
|---|---|---|
| **pH** | 7.2 – 7.8 (aim for 7.4-7.6) | Controlled automatically by the Idegis (default setpoint 7.20). TFP advises aiming slightly higher to reduce corrosion. |
| **Free chlorine (FC)** | 5 – 10 ppm | For SWG with CYA 70-80. Never below 5 ppm. |
| **Combined chlorine (CC)** | < 0.5 ppm | Above 0.5 the "chlorine smell" appears (chloramines). |
| **CYA (cyanuric acid)** | 60 – 90 ppm | SWG wants high CYA so chlorine lasts longer. **UV degrades CYA and FC** — watch it. |
| **TA (total alkalinity)** | 60 – 80 ppm | TFP recommends lower than most manuals (80-120) to reduce pH-rise tendency. |
| **CH (calcium hardness)** | 350 – 550 ppm | For vinyl liner pools it's flexible; for plaster/concrete aim for 350+. |
| **Salt (NaCl)** | per the cell — usually 3000-4500 ppm | This unit is **low-salinity**: range per manual (likely 1500-3000 ppm). |
| **Water temperature** | — | Indoor pool stays around 37 °C. Not controlled, just recorded. |

## The FC ↔ CYA relationship (the most important one)

"Free" chlorine (FC) without CYA lasts hours in the sun. With high CYA it
lasts days. The trade-off:

- **Low CYA (<30)**: chlorine burns off fast → SWG works hard → cell wears
  out sooner.
- **High CYA (60-90)**: stable chlorine → SWG works less → longer cell life.
  But you must keep **FC ≥ CYA/40** so chlorine remains effective as a
  disinfectant (CYA "sequesters" most of it).

TFP "Chlorine/CYA chart": https://www.troublefreepool.com/threads/chlorine-cya-chart.2177/

Practical rule with CYA 70-80 and a SWG:

- **FC target**: 5–10 ppm (we live in 7–8).
- **FC hard minimum**: 5 ppm.
- **FC "shock level"** (algae or contamination): 31 ppm at CYA 80.

## Implications for the reference installation

1. **Indoor pool at 37 °C**: warm water accelerates chlorine consumption
   and favours bacterial growth if FC drops. Stay in the upper end of the
   range (FC 8–10).
2. **Active UV**: degrades CYA continuously. Check CYA monthly with a
   strip and top up when it drops below 60.
3. **Low salinity**: the optimal salt range depends on the cell. When
   reading the Modbus, validate against `threshold_low_salt` and
   `threshold_high_salt` programmed in holdings `0xC2/0xC3` (defaults
   300/800 with ÷100 → 3.00–8.00 g/L; **likely reprogrammed for the
   low-salt range** in this unit — read at first pairing).
4. **The Idegis does NOT measure CYA, TA or CH**. These remain manual via
   strips / DPD test weekly-monthly. **No real electronic sensor exists
   under 500 €** for those parameters (already discounted in
   [05-sensors-extra.md](05-sensors-extra.md)).
5. **The Idegis DOES measure pH, ORP, salt, temperature**. These are what
   we surface in HA over Modbus.

## Recommended TFP reading

| Topic | Link |
|---|---|
| FC/CYA relationship explained | https://www.troublefreepool.com/blog/2019/01/18/free-chlorine-and-cyanuric-acid-relationship-explained/ |
| Water balance for SWGs | https://www.troublefreepool.com/blog/2019/01/18/water-balance-for-swgs/ |
| ABCs of pool chemistry | https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/ |
| CYA wiki | https://www.troublefreepool.com/wiki/index.php?title=CYA |
| Chlorine/CYA chart (forum) | https://www.troublefreepool.com/threads/chlorine-cya-chart.2177/ |
| TFP method overview | https://www.troublefreepool.com/blog/pool-school/ |

## Translating to Home Assistant

In the pool dashboard (Phase 4 of
[04-esphome-config.md](04-esphome-config.md)):

- Gauges with TFP ranges as bands (green 5–10 ppm equivalent for FC via
  ORP, etc.).
- Alarms: pH < 6.8 or > 7.8, ORP < 600 or > 850 mV (proxy for FC out of
  band), Temp > 40 °C (enclosure anomaly).
- Monthly reminder: "test CYA and TA manually".
- Grafana long-term history of pH, ORP, salt, temperature to spot trends.
