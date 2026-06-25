# Changelog

## 0.6.11 — 2026-06-25

- **New: electricity cost with solar attribution.** The pumps panel now shows,
  per channel, the real grid cost (priced by time-of-use period — valle/llano/
  punta), the energy that ran on free solar surplus (kWh + %), and the live
  power source (☀️ solar / 🔌 red). The header shows the current tariff period
  and price.
  - Splits each running interval into grid vs solar using a configurable signed
    grid-power sensor (`grid_power_entity`); solar (PV surplus) is counted as
    0 € with its forgone export value tracked separately. No grid sensor → all
    grid (safe fallback), still period-split.
  - Time-of-use tariff is configurable (`tariff_*` options), defaulting to the
    Spain 2.0TD geometry/prices used by the Energy Optimizer add-on, evaluated
    DST-aware in the configured timezone.
  - `GET /api/idegis/pumps` now returns a `cost` breakdown (24h/7d/30d:
    grid_kwh, solar_kwh, grid_eur, by-period €, solar_pct), `source_now`, and a
    `tariff` block.
- **Docs:** `docs/16-energy-cost-integration.md` documents the model and the
  cross-project contract with `ha-energy-optimizer` (what the capturer exposes
  for it to consume, and the canonical price sensors the Optimizer should
  publish so the tariff config isn't duplicated).


## 0.6.10 — 2026-06-25

- **Fixed: "Sal avg" and "Producción Cl avg" were blank in the Última sesión
  panel.** The chlorinator emits salinity and production only every few hours,
  so a filtration session often captures zero samples for them and the snapshot
  dropped the metric entirely. Now the session snapshot falls back to the
  last-known (carry-forward) value, flagged `carried`, and the UI shows it with
  a "último valor conocido" hint instead of `—`.
- **Fixed: those last-known values were lost across restarts.** Salinity/
  production reported more than `max_history` (1000) records ago fell outside
  the warm-up replay window, so sticky never held them. Startup now backfills
  sticky with the last-known value of each measurement field from the full
  persistent store.


## 0.6.9 — 2026-06-24

- **Fixed: the vitals charts (pH / salinity / temperature / production) were
  blank.** The chart autoscale folded the reference bands' open-ended
  `±Infinity` bounds into the Y-range, so `yRange` became `Infinity` and every
  plotted coordinate and axis label came out `NaN` — an invisible line over
  `—` labels. The autoscale now ignores non-finite band bounds and clamps
  open-ended bands to the plotted range.
- **Fixed: `/api/idegis/state` could 500 and blank every summary tile.** It
  read `last["path"]` (plus `upstream_status` / `upstream_time_s`) with a hard
  subscript; any history record without those optional proxy fields raised
  `KeyError` and took down the whole endpoint. Now read defensively.
- **New: end-to-end visualization tests** (`tests/test_dashboard_e2e.py`).
  These render the real dashboard in headless Chromium against the real
  aiohttp app seeded with fixtures and assert the SVG charts actually draw a
  finite line, the tiles show numbers, and no API endpoint errors. Wired into
  CI as a dedicated `e2e` job. This is the regression net for front-end render
  bugs the Python suites cannot see — it reproduces both fixes above.


## 0.6.8 — 2026-06-22

- **Capture store moved to `/share` so it survives add-on lifecycle events.**
  The JSON-Lines history used to live in the add-on's private `/data`
  volume, which the Supervisor **wipes on an uninstall or a
  repository/slug migration**. That is exactly what happened when the
  add-on moved from the `local` repository to a git repository
  (`local_idegis_capturer` → `37fb99c1_idegis_capturer`): the Supervisor
  ran `Removing app data folder …/local_idegis_capturer` and the entire
  capture corpus was lost.
  - The store now defaults to `/share/idegis_capturer/captures/idegis_full.jsonl`.
    `/share` persists across uninstall / slug changes **and** is included in
    Home Assistant backups.
  - `config.yaml` now maps `share:rw`.
  - On first start after the upgrade, the old `/data/captures/idegis_full.jsonl`
    (if present) is copied forward once, so no captures are lost in the move.
  - `/data/options.json` is unchanged — it stays Supervisor-managed in `/data`.

## 0.6.7 — 2026-06-22

- **Fix: "Última sesión" rendered blank / stuck on "ninguna sesión cerrada
  todavía".** The d4f4ba3 codec-key rename made the closed-session snapshot
  emit a `measurements` map keyed by semantic names
  (`ph` / `salinity` / `temperature` / `production_percent`) plus
  `duration_s` / `last_ts`, but both consumers were never updated and still
  read the old `aggregates` map keyed by raw codec codes (`SG`/`IT`/`CY`/`GY`)
  and `duration_seconds` / `end_ts`:
  - The ingress dashboard (`app.js`) read `ls.aggregates`, which is always
    `undefined`, so it permanently fell through to the empty state — even
    after a session had actually closed.
  - The desktop HTML status page (`show_status`) had the same mismatch.
  Both now read the live snapshot schema. Added a regression test
  (`test_closed_session_snapshot_schema`) that pins the snapshot contract so
  the renderers and `_snapshot_session` can't drift apart again.

## 0.6.6 — 2026-06-17

- **Trusted measurements: motor-on, time-averaged.** With the filter
  pump off, the chlorinator keeps reporting its probes but they read a
  stuck floor — pH was observed pegged at ~4.8 for hours overnight,
  then jumping to a real 7.4 the instant the motor (≈1.1 kW) started.
  The dashboard now only believes a pH / salinity / temperature /
  production reading captured while the motor was actually pushing
  water, and reports the **mean over a rolling ≥10 min window** of
  those valid samples instead of the raw last value:
  - New `measurement_flow_threshold_w` (default 50 W) — a sample counts
    only when the recorded pump power is at or above this, comfortably
    above the ~1.5 W contactor-coil baseline and below the running
    motor. Falls back to the boolean `pump_running` flag when the
    Shelly power isn't available.
  - New `measurement_window_s` (default 600) — the averaging window.
  - `GET /api/idegis/state` gains a `trusted_measurements` block
    (`value`, `n`, `window_s`, `from`, `to`, `stale_seconds`). The raw
    `measurements` block is kept for debugging.
  - `GET /api/idegis/timeseries` now drops motor-off samples by default
    (no more fake cliff on the charts); `?raw=1` restores the old
    behaviour.
  - The filtration recommendation reads the trusted temperature.
  - Dashboard tiles show the trusted average, dim when the value is
    stale (pump currently off → last good average carried over), and
    tooltip the sample count / age.
- **Version string fixed.** `ADDON_VERSION` in the code had lagged at
  0.6.4 (the asset cache-buster and footer were stale); now tracks the
  add-on version.

## 0.6.5 — 2026-06-17

- **Filtration recommendation tuned for indoor + UV pools.** New
  defaults that better fit a covered pool with a Neo2-24 UV chlorinator:
  - `target_production_pct: 40` — running longer at low % is gentler
    on the electrode than short pulses at 100 %.
  - `chlorine_demand_ppm_per_day: 0.6` — realistic for indoor water
    with no sun-driven UV decay.
  - `min_turnovers_per_day: 0.75` — covers UV-cell cycling for
    cloramines.
  - `apply_temp_multiplier: false` — kinetics multiplier is off by
    default for covered pools (no sun, no evaporation).
- **Net'N Clean awareness.** New `net_n_clean_installed` option:
  when the pool has an AstralPool Net'N Clean (or equivalent
  secondary booster pump driving in-floor returns), dead-zone
  prevention is mechanical, so the turnover floor is reduced to
  `min_turnovers × 0.6`. The remaining floor is justified solely
  by UV-cell cycling.
- The formula breakdown in the dashboard now explains which
  constraints are active (temp multiplier on/off, Net'N Clean
  on/off) so the recommendation is auditable end-to-end.

## 0.6.4 — 2026-06-16

- **Theme aligned with `ha-energy-optimizer`** — dark slate background
  (`#0f172a`), amber/sky/green accents, system-ui sans-serif, chunky
  3 px black outlines with solid drop-shadows. Visual coherence with
  the other home apps so the user gets the same comic vibe across
  the homelab.
- **Pumps energy panel** — live W draw plus kWh accumulated 24 h /
  7 d / 30 d for both the filter pump (Shelly Pro 4PM ch 3) and the
  cleaner (ch 1). Motor running hours computed by integrating only
  intervals above 5 W (filters out the contactor coil's 1.5 W
  baseline). Cost in € over 30 days at the configurable price.
- **Filtration recommendation panel** — recommends daily and weekly
  filtration minutes from the configured pool volume + nominal flow
  + the current water temperature (temperature-multiplier from a
  TFP-inspired curve). Compares against actual runtime taken from
  the persistent jsonl and renders coverage bars (under = amber,
  on-target = green).
- New backend endpoints:
  - `GET /api/idegis/pumps` — calls HA history for the two Shelly
    channels via the Supervisor-proxied Core API.
  - `GET /api/idegis/recommendation` — pure derivation, no I/O
    besides the in-memory state.
- New configurable options:
  - `cleaner_power_entity`, `pump_switch_entity`,
    `cleaner_switch_entity` (Shelly + HA switches).
  - `pool_volume_m3` (default 37), `pump_nominal_flow_m3_h` (12),
    `energy_price_eur_kwh` (0.18).

## 0.6.3 — 2026-06-16

- **Real dashboard** — the ingress panel is now a single-file vanilla
  JS app with SVG charts (no CDN, no HACS, no Chart.js). Sections:
  - **Top tiles**: online pill, last pump start (relative + absolute),
    filtration hours week / month, polling rate, captures count,
    read/write split.
  - **Vital signs**: pH / salt / temperature / chlorine production,
    each with a line chart and **TFP reference bands shaded in the
    background** (green = ok, amber = warn, red = bad). A period
    selector switches between 24 h, 3 d, 7 d and 30 d windows.
  - **Filter activity**: 30-day bar chart of pump running minutes per
    day, with circles above each bar marking the number of starts.
  - **Last session**: avg pH / salt / temp / production, duration and
    close timestamp.
  - **No more JSON link buttons** at the bottom — the dashboard
    surfaces what the user actually needs.
- New backend endpoints used by the dashboard:
  - `GET /api/idegis/timeseries?hours=N&points=N` — decimated series
    pulled from the persistent jsonl, decoded through the codec.
  - `GET /api/idegis/activity?days=N` — per-day pump-running minutes
    plus last start, total hours week and total hours month.
- Static assets under `rootfs/opt/idegis/static/` served by aiohttp.

## 0.6.2 — 2026-06-15

- **Ingress + sidebar panel**. The add-on now exposes the panel
  through HA ingress (`ingress: true`, `ingress_port: 8765`,
  `panel_title: "Idegis capturer"`). The toggle "Show in sidebar"
  becomes available in the add-on UI. The previous JSON-link landing
  page lives as a fallback in case `static/` is missing from the
  image.

## 0.6.1 — 2026-06-03

- Reworked session boundaries. The chlorinator keeps emitting writes
  with measurements even when the filter pump is off (it has an
  internal standby), so the previous "5 minutes of measurement
  silence" rule never fired on the reference installation and the
  session never closed.
  - New rule: the session is delimited by **pump_running edges**.
    The pump_poller now triggers `force_close_session()` on the
    falling edge (pump goes from running to stopped).
  - Default `pump_running_threshold_w` lowered from 100 W to 1 W so
    the contactor coil draw is enough to flag the session active.
    Users who can read the real motor current can raise it back.
  - `SESSION_IDLE_TIMEOUT_S` bumped to 30 min as a hard fallback for
    setups where the pump poller is misconfigured or HA itself is
    down — it should never fire in normal operation.

## 0.6.0 — 2026-06-03

- Session tracking. A *session* is a contiguous stretch of write.php
  requests that carry measurements. The addon now keeps per-session
  aggregates for every metric (n_samples, avg, min, max, last,
  duration). Sessions auto-close after 5 minutes of measurement silence.
- `/api/idegis/state` now also exposes:
  - `current_session`: open session in progress
  - `last_session`: snapshot of the last closed session
- A background asyncio task ticks every 30 s to roll sessions over.

These are the building blocks behind the new "session" sensors in the
companion integration (pH avg / temp avg / salinity avg / production
avg / session duration, etc.) — much more useful than the instant
values because the chlorinator only reports while it is alimented.

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
