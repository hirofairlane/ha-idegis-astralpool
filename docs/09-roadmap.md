# 09 · Roadmap toward the HACS integration

The end goal is a polished `custom_components/idegis_astralpool/` that
HACS users install in one click and Home Assistant configures via a UI
wizard.

## Target layout

```
custom_components/idegis_astralpool/
├── __init__.py            integration setup / unload
├── manifest.json          domain, version, requirements, dependencies
├── config_flow.py         UI wizard: choose mode (A / B / C) and pair
├── coordinator.py         single DataUpdateCoordinator
├── const.py
├── cloud_proxy.py         mode A: HTTP receiver + B0 decoder
├── modbus_rtu.py          mode B: Modbus RTU client (over ESP32 / direct USB)
├── poolstation_client.py  mode C: Poolstation cloud (fallback)
├── codec.py               B0 payload codec + H hash
├── sensor.py
├── binary_sensor.py
├── number.py
├── switch.py
├── button.py
└── translations/
    ├── en.json
    └── es.json
```

## Operating modes (config_flow options)

| Mode | When to pick it |
|---|---|
| **A · Cloud-MITM local** | You can override DNS on your router for `api.idegis.net` and run a small HTTP listener on Home Assistant or a sidecar host. |
| **B · Modbus RTU via ESP32 / USB** | You have wired an RS485 transceiver into the Idegis Modbus connector. Full bidirectional control, no cloud. |
| **C · Poolstation cloud** | Quick start. You accept the Fluidra cloud dependency. |

## Phases

### Phase α — research (current)

- Decode the `B0` payload from a corpus of captured requests.
- Validate the `H` MD5 formula.
- Prove the reverse proxy approach in CT104 with a couple of decoded
  fields.

### Phase β — minimum viable integration

- Implement mode A with the decoded fields surfaced as `sensor` entities.
- Single-mode config_flow (mode A only).
- Manual install via "Custom repository" in HACS.

### Phase γ — feature parity with the Modbus map

- Implement mode B (Modbus RTU) using `pymodbus`.
- Add `number` entities for setpoints.
- Add `button` entities for alarm reset.
- Multi-mode config_flow with auto-detection.

### Phase δ — polish and HACS default

- Add mode C as fallback.
- Full translations (en, es).
- Unit tests + GitHub Actions CI.
- Submit to HACS default repositories.

## Out of scope

- Bombs of features unrelated to chlorinator control (e.g. pool cleaner
  control, water heater integration). Those belong in other integrations.
- Anything specific to industrial Multi-Tec units (Tecno Connect line).
- Anything specific to AstralPool Halo (different platform).
