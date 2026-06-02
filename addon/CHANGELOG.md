# Changelog

## 0.3.0 — 2026-06-02

- New: live correlation with Home Assistant. The add-on now polls a HA
  entity (default `sensor.shellypro4pm_30c6f7836a6c_power_3`) and tags
  every captured request with the current pump power and a derived
  `pump_running` boolean.
- Why it matters: the chlorinator only sends real telemetry
  (`write.php` with B0+B1+B2) while the filter motor is actually
  drawing power. With this flag we can filter the captured corpus
  offline to keep only the records where decoding is possible.
- New config options: `pump_power_entity` (the entity_id to watch),
  `pump_running_threshold_w` (W threshold above which we consider the
  motor running), `pump_poll_interval_s`.
- Uses the HA Supervisor token automatically — no manual auth setup,
  just enable the add-on and it talks to HA Core through the supervisor
  proxy. Enabled via `homeassistant_api: true` in config.yaml.
- `/api/idegis/state` now exposes `pump_power_w`, `pump_running`,
  `pump_entity_state` and `pump_running_seconds`.

## 0.2.1 — 2026-06-02

- Hot fix after first real-traffic capture: the chlorinator splits its
  payload across `B0`, `B1`, `B2` when it overflows the URL length.
  We now concatenate every `Bn` parameter (in numeric order) before
  decomposing into fields. This recovers ~24 fields per write request
  (`YI`, `SI`, `IT`, `MG`, `PG`, `GY`, `IJ`, `DL`, `CJ`, `Jb`, `Y9`,
  `CK`, `CC`, `C7`, `MK`, `AJ`, `OI`, `RB`, `OB`, `TB`, `NB`, `8B`,
  `YD`, `9C`, `9G`).
- The cloud response body, which we now know is ASCII text in the
  form `00#B0=<payload>&H=<hash>`, is parsed too. The decomposed
  cloud-side fields are surfaced in `/api/idegis/state` as
  `last_response_fields`.

## 0.2.0 — 2026-06-02

Rebuilt as a single-process aiohttp service. Drops nginx entirely.

- New: response bodies are captured too. The 176-byte body the cloud
  returns to `/read.php` (where the device's setpoints/commands live)
  is now persisted base64-encoded.
- New: `/api/idegis/last_response` endpoint exposes the latest cloud
  reply with hex and ASCII preview.
- New: `/api/idegis/analyze` endpoint runs alphabet / invariants /
  response-size statistics on the captured corpus.
- New: persistent JSON-lines log at `/data/captures/idegis_full.jsonl`.
  The state warms up from this file on every restart.
- Removed: nginx and its render script. The proxy is now pure Python
  (aiohttp), one supervised process. Simpler image, lighter footprint.
- Removed: the `idegis_proxy_access.log` plain text file (replaced by
  the structured JSON-lines file).
- The HA integration gets two extra sensors derived from the new
  fields: `last_response_size_bytes` and `session_age_seconds`.

## 0.1.0 — 2026-06-02

First public release.

- nginx reverse proxy for `api.idegis.net` on port `80`.
- FastAPI capturer service on port `8765` (health / state / history endpoints).
- Persistent log under `/data/captures/idegis_proxy_access.log`.
- Hard-coded upstream IP `45.60.153.189` to avoid DNS loop with the
  router-side override.
- B0 field decomposition (prefix + TD + CI + LI + CD + SG + CY) exposed
  raw. Codec decoding is pending — see project roadmap.
