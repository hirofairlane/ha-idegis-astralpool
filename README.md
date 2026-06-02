# ha-idegis-astralpool

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docs: CC BY-SA 4.0](https://img.shields.io/badge/docs-CC%20BY--SA%204.0-lightgrey.svg)](LICENSE-docs)
[![Project status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](work-log.md)

Reverse engineering, documentation and Home Assistant integration for
**Idegis** and **AstralPool** salt water chlorinators (group Fluidra,
Multi-Tec platform). Covers both brands because they are OEM rebadging of the
same hardware.

> 🔒 **Local-first.** The end goal is to remove the dependency on the
> `api.idegis.net` cloud and have all telemetry and control happen on your
> LAN, either via Modbus RTU (ESP32+RS485) or via a transparent
> cloud-MITM proxy that runs on your own infrastructure.

Reference device used during development: **Idegis Neolysis Neo2-24PH/S**
(24 g/h salt electrolysis, integrated UV lamp, integrated pH control).

## What this project is and is not

This project **is**:

- A **public translation of the official Idegis Modbus map (v1.62)** into
  readable markdown, with units, scales and editable flags.
- A **working ESPHome configuration** to talk Modbus RTU to the chlorinator
  over an ESP32 + RS485 adapter.
- A **DNS-override + reverse proxy** strategy to intercept the device's
  outbound HTTP cloud telemetry locally and expose it to Home Assistant
  **without any additional hardware**.
- A **water-chemistry reference** for pools with salt water generators
  (SWG) and UV lamps, distilled from the
  [Trouble Free Pool](https://www.troublefreepool.com/) community.

This project **is not** (yet):

- A polished HACS integration. It will become one — see
  [docs/09-roadmap.md](docs/09-roadmap.md) — but right now it is a
  documentation and prototyping repo.
- A reverse-engineered Poolstation cloud client. For that see
  [`cibernox/homeassistant-poolstation`](https://github.com/cibernox/homeassistant-poolstation),
  which is the recommended drop-in if you do not want to touch hardware or
  network.

## Compatibility — Idegis ↔ AstralPool

Idegis joined the Fluidra group in 2007 and produces under the
[Multi-Tec platform](https://www.idegis.es/), which is rebadged as AstralPool
worldwide. The following pairs share **the same firmware, the same Modbus
register map (v1.62) and the same wifi/ethernet module**:

| Idegis | AstralPool |
|---|---|
| Domotic 2 | Elite Connect |
| Neolysis | Neolysis |

> ⚠️ **Do not confuse with Sugar Valley *NeoPool*** (Hidrolife, Aquascenic,
> Bayrol, Brilix…). That is a different manufacturer with a different Modbus
> map. If you have a NeoPool device use
> [`alexdelprete/ha-sugar-valley-neopool`](https://github.com/alexdelprete/ha-sugar-valley-neopool)
> or the Tasmota [NeoPool](https://tasmota.github.io/docs/NeoPool/) driver.

## Quick start (path A — recommended)

1. In Home Assistant: **Settings → Add-ons → ⋮ → Repositories → Add**
   `https://github.com/hirofairlane/ha-idegis-astralpool`.
2. Install the **Idegis / AstralPool cloud capturer** add-on and start it.
3. In HACS: **Integrations → ⋮ → Custom repositories → Add** this same
   repository as an *Integration*.
4. Install the integration. Add a new integration via **Settings →
   Devices & services → + Add integration → Idegis / AstralPool** with
   host = your HA host and port = 8765.
5. Add a DNS override on your LAN router that points `api.idegis.net` to
   the IP of your Home Assistant host. Example for OpenWrt:
   ```sh
   uci add_list dhcp.@dnsmasq[0].address='/api.idegis.net/<HA_IP>'
   uci commit dhcp && /etc/init.d/dnsmasq restart
   ```

The integration starts surfacing entities as soon as the chlorinator
makes its next request to the cloud (the pump must be running).

## Three integration paths (pick what you need)

| Path | What it gives you | Hardware needed | Cloud dependency |
|---|---|---|---|
| **A · Cloud-MITM (recommended)** | Continuous telemetry via DNS override + reverse proxy on a host you already own | None | Optional (you can fully bypass `api.idegis.net`) |
| **B · Modbus RTU** | Full bidirectional local control (read + write setpoints, time programs, etc.) | ESP32 + RS485 transceiver (~5 €) | None |
| **C · Poolstation cloud client** | Quick start using the existing community integration | None | Yes (depends on the official Fluidra cloud) |

The paths are not mutually exclusive — running A and B at the same time is
the best of both worlds (push telemetry every 3–4 s from cloud-MITM,
deterministic control from Modbus RTU). C is a fallback when A and B are not
acceptable to the user.

## Repo layout

```
.
├── README.md                  ← you are here
├── docs/                      ← public technical documentation (English)
│   ├── 01-hardware.md         hardware and capability bitmap
│   ├── 02-modbus-reference.md Modbus register map (v1.62 distilled)
│   ├── 03-wiring-esp32.md     RS485 wiring, topology, safety
│   ├── 04-esphome-config.md   entity mapping and rollout phases
│   ├── 05-sensors-extra.md    optional external sensors (<100 € each)
│   ├── 06-installation-and-lan.md  installation specifics + LAN discovery
│   ├── 07-water-chemistry.md  Trouble Free Pool targets for SWG + UV
│   ├── 08-cloud-api-discovery.md   cloud HTTP protocol of api.idegis.net
│   ├── 09-roadmap.md          phased plan toward HACS default
│   └── 10-addon-architecture.md   the HA add-on stack (current recommendation)
├── addon/                     ← HA Add-on (nginx + capturer, self-contained)
│   ├── config.yaml            add-on manifest
│   ├── Dockerfile
│   ├── build.yaml
│   ├── apparmor.txt
│   ├── DOCS.md                store description
│   └── rootfs/                copied verbatim into the image
├── esphome/
│   └── idegis-neolysis.yaml   ESPHome config (read-only phase 1)
├── custom_components/         ← HACS integration (companion of the add-on)
│   └── idegis_astralpool/
├── hacs.json                  ← HACS metadata
├── repository.yaml            ← HA add-on repository metadata
├── CLAUDE.md                  ← internal context (Spanish)
└── work-log.md                ← chronological dev log (Spanish)
```

## Status — current snapshot

- ✅ Modbus v1.62 register map translated to markdown.
- ✅ Idegis/AstralPool equivalence confirmed and documented.
- ✅ Device identified on LAN (MAC `68:27:19:DA:5A:53`, OUI Microchip).
- ✅ Cloud protocol partially reverse-engineered: HTTP plain, no TLS,
      polling `api.idegis.net/interface/{read,write}.php?B0=...&H=...`.
- ✅ MITM via DNS override demonstrated end-to-end.
- 🚧 `B0` payload encoding and `H` hash formula being decoded.
- 🚧 ESPHome config skeleton, not yet flashed onto hardware.
- 🚧 HACS integration scaffold.

See [work-log.md](work-log.md) for the chronological breakdown.

## Prior art

- [`cibernox/homeassistant-poolstation`](https://github.com/cibernox/homeassistant-poolstation)
  — Poolstation (Fluidra cloud) client.
- [`foXaCe/Fluidra-pool`](https://github.com/foXaCe/Fluidra-pool) — Fluidra
  Connect / iAquaLink reverse engineering.
- [openHAB community thread by C. Schreiner](https://community.openhab.org/t/integrating-idegis-domotic-2-ls-pool-controller-with-openhab-via-modbus/163549)
  — first public attempt at Modbus RTU for Idegis Domotic 2 LS.

## Legal

The Modbus register map v1.62 distilled in
[`docs/02-modbus-reference.md`](docs/02-modbus-reference.md) is derivative
work based on technical documentation by Idegis (I.D. Electroquímica S.L.).
The original `.xlsm` file is **intentionally not included** in this repo.
This project is **independent of Idegis, AstralPool and Fluidra**.

## License

- **Code**: [MIT](LICENSE)
- **Documentation**: [CC BY-SA 4.0](LICENSE-docs)
