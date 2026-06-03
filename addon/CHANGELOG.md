# Changelog

## 0.5.4 — 2026-06-03

- Field `GY` declared as **chlorine production %** based on its
  observed range (0..99 in increments of 1, pure-base10 alphabet,
  same shape as the production_pct_now register on the Modbus side).
- Companion integration v0.0.7 adds
  `sensor.idegis_chlorinator_chlorine_production` (%, precision 0).

## 0.5.3 — 2026-06-03

- Real fix: not every `write.php` carries every field. The first batch
  may include SG/IT/CY, the next one just counters, the next one a
  different subset. We now maintain a **sticky per-field state**: each
  Bn key keeps its last-known value indefinitely, regardless of which
  request carried it.
  - `/api/idegis/state` -> `measurements` is now computed from the
    sticky state. pH, salinity and temperature stay valid across the
    quiet intervals where the chlorinator only ships a counter-only
    write.
  - `/api/idegis/state` -> `sticky_fields_decoded` exposes the full
    sticky view, with per-field last-update timestamps available
    indirectly via the per-record history.

## 0.5.2 — 2026-06-03

- Bug fix: the `measurements` block went blank every time a `read.php`
  arrived, because measurements only ride on `write.php` requests. We
  now keep a separate `last_write_fields` snapshot that is only
  updated on writes, and the API surface uses that to compute
  measurements. The `last_fields` snapshot still reflects the very
  last request of any kind (used by raw and counter sensors).

## 0.5.1 — 2026-06-03

- `CY` field decoded as **water temperature in °C** (decimal, trailing
  unit marker 'I'). Verified by:
  - Range 24.6 .. 34.2°C across 79 samples, with 0.2°C step.
  - Clear day/night cycle in the captured corpus (32-34°C around
    23:00 UTC, dropping to 24-25°C by 07:00 UTC).
  - Plausible for a probe in the equipment-room bypass loop where
    the water cools off compared to the 37°C indoor pool basin.
- One side observation while correlating with SG (pH): the pH dropped
  to 5.76 around 23:00-01:00 UTC while the pump wasn't running. Likely
  an overdose by the pH-minus pump with no flow. Worth checking the
  pumpstop logic.

## 0.5.0 — 2026-06-03

Second decoding milestone — actual water measurements out.

After capturing 1000+ samples (318 writes) and running a per-field
range analysis, three more characters of the codec fell out:

- **`g` is the decimal point**.
- Trailing uppercase letters that are NOT in the digit set are
  **unit markers** (M, I, N, R, ...).

That immediately unlocks two real measurements:

- **`SG` = water pH** (values 5.72 – 7.51 across the corpus). Sample:
  `aVgef` -> `07.45` -> pH 7.45.
- **`IT` = salinity in g/L** (0.0 – 3.8, trailing 'M' is the unit
  marker — matches the Neolysis low-salinity range). Sample:
  `abgfM` -> `01.5M` -> 1.5 g/L.

These two are now first-class fields in `codec.py` with a `measure`
type and a unit, and `/api/idegis/state` exposes a new top-level
`measurements` block summarising them:

    {
      "measurements": {
        "ph": {"value": 7.45, "unit": "pH"},
        "salinity": {"value": 1.5, "unit": "g/L"}
      }
    }

This is the corpus before the filter motor was confirmed to be
running, so the values may not match the operational regime. More
captures with `pump_running=true` should let us pin down ORP,
temperature, production% and the remaining unknown fields (CY, 9G,
GY, MG, PG, CJ, CK, CC, C7, AJ).

## 0.4.0 — 2026-06-02

First decoding! The B0 codec uses a base-10 positional integer
representation with a custom digit alphabet:

    a=0  b=1  c=2  d=3  e=4
    f=5  U=6  V=7  W=8  X=9

This was inferred from the `CD` field by correlating its values with
wall-clock timestamps captured at the proxy. The decode is now
verified against many samples and is exact to the second.

Knowing the alphabet immediately unlocks several fields:

- `CD` = Unix timestamp in seconds, UTC. ('bVWaedfcbc' = 1780435212 =
  2026-06-02 23:20:12)
- `LI` = monotonic per-request counter (~1110-1132 in our sample)
- `CI` = constant 0 (channel index)
- `TD` = device serial number (13 base-10 digits, e.g. 2101812099010)
- `9C`, `Jb`, `SI`, `YI`, `Y9`, `DL`, `RB` = single-digit booleans
- `AJ`, `OI`, `OB`, `TB` = small integers (likely event counters or
  embedded timestamps)

Several fields (`CY`, `SG`, `9G`, `IT`, `GY`) contain characters that
are NOT in our base-10 set (`g`, `I`, `O`, `M`, etc.). They use a
wider alphabet that we have not pinned down yet — almost certainly
the actual measurement fields (pH, ORP, salt, temperature). They
need more samples captured with the filter motor actually running
(`pump_running=true`).

New addon endpoint output:

- `/api/idegis/state` now also returns `last_fields_decoded` and
  `last_response_fields_decoded`, each field annotated with its
  human-readable type, description and decoded value.

The codec lives in its own module (`rootfs/opt/idegis/codec.py`) so
the decoding logic is testable in isolation.

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
