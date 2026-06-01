# Idegis / AstralPool pool chlorinator

Home Assistant integration for **Idegis** and **AstralPool** salt water
chlorinators (Fluidra group, Multi-Tec platform). Covers both brands —
they are OEM rebadging of the same hardware.

> Pre-alpha. See [README](https://github.com/hirofairlane/ha-idegis-astralpool)
> and [work-log](https://github.com/hirofairlane/ha-idegis-astralpool/blob/main/work-log.md)
> for status.

## Reference device

Idegis Neolysis Neo2-24PH/S (≡ AstralPool Neolysis equivalent).

## Three operating modes (planned)

1. **Cloud-MITM local** — DNS override + reverse proxy. No hardware.
2. **Modbus RTU** — ESP32 + RS485 transceiver. Full local control.
3. **Poolstation cloud** — drop-in fallback.

## Not compatible with

Sugar Valley **NeoPool** (Hidrolife / Aquascenic / Bayrol / Brilix). That's
a different manufacturer — use the Sugar Valley integrations.
