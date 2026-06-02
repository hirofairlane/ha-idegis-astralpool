# 10 · Add-on architecture (path A, self-contained)

Starting at v0.1.0 the **recommended deployment** is a single
Home Assistant add-on that bundles the nginx reverse proxy and the Python
capturer service. The previous setup (a standalone service on CT104) is
documented in [`docs/08-cloud-api-discovery.md`](08-cloud-api-discovery.md)
but is **superseded** by the add-on.

## Why an add-on, not just a custom_component

The capturer needs to **receive HTTP traffic on port 80** from the
chlorinator. A pure Home Assistant integration cannot do that — it lives
in the HA Core event loop and only outbound calls are practical from it.
A Home Assistant **add-on** runs as a separate container, can bind any
TCP port, can run nginx + Python + a custom UI, and is fully distributable
via the Add-on Store.

This mirrors the architecture of the user's own
[`ha-energy-optimizer`](https://github.com/hirofairlane/ha-energy-optimizer)
add-on.

## Layout

```
addon/
├── config.yaml                   add-on manifest (slug, ports, options, schema)
├── Dockerfile                    Alpine + nginx + python3 + uvicorn + fastapi
├── build.yaml                    multi-arch build config
├── apparmor.txt                  hardened AppArmor profile
├── DOCS.md                       what the user sees in the Add-on Store
├── README.md                     short pointer
├── CHANGELOG.md
└── rootfs/                       gets copied verbatim into the image
    ├── etc/
    │   ├── nginx/nginx.conf      reverse proxy + custom access log format
    │   ├── cont-init.d/
    │   │   └── 10-render-nginx.sh  templates upstream_host into nginx.conf
    │   └── services.d/
    │       ├── nginx/{run,finish}     s6-overlay v3 service
    │       └── capturer/{run,finish}  s6-overlay v3 service
    └── opt/idegis/
        └── capturer.py            FastAPI service tailing the nginx log
```

## Container stack

- **Base**: `ghcr.io/hassio-addons/base:17.2.0` (Alpine + s6-overlay v3 +
  bashio).
- **Services**:
  - `nginx`: listens on `:80`, vhost `api.idegis.net`, forwards every
    request to the literal cloud IP, logs request URL + upstream status
    in `idegis_full` format.
  - `capturer`: `uvicorn capturer:app --host 0.0.0.0 --port 8765`. Tails
    `/data/captures/idegis_proxy_access.log`, parses the B0 payload,
    keeps the last N requests in memory, exposes:
    - `GET /api/idegis/health`
    - `GET /api/idegis/state`
    - `GET /api/idegis/history?n=50`

## Persistent state

Everything that needs to survive add-on restarts lives under `/data`:

- `/data/captures/idegis_proxy_access.log` — nginx access log
- `/data/captures/idegis_proxy_error.log` — nginx error log
- `/data/state/` — placeholder for future codec state

`/data` is the standard HA add-on persistent volume.

## Options (config_flow surface inside HA)

| Option | Default | Description |
|---|---|---|
| `upstream_host` | `45.60.153.189` | Cloud IP. Literal IP to avoid DNS loop with the router override. |
| `upstream_host_header` | `api.idegis.net` | Host header forwarded to the cloud. |
| `log_level` | `info` | uvicorn / capturer log level. |
| `max_history` | `1000` | In-memory request history size. |
| `online_timeout_s` | `90` | After this many seconds without traffic the device is reported offline. |

## Security profile

`apparmor.txt` enforces a minimal capability set: only `dac_read_search`,
`net_bind_service`, `setgid`, `setuid`. No `NET_ADMIN`, no `SYS_ADMIN`,
no host networking. This makes the add-on safe enough for the public
Add-on Store and side-steps the concerns we had about turning HA OS into
a router (see [docs/06-installation-and-lan.md](06-installation-and-lan.md)).

## Relationship with the integration

```
+-------------------------------+        +-------------------------------+
| HA Core                       |        | Add-on container              |
|                               | poll   |                               |
|  custom_components/           | http   |  nginx :80  (chlorinator)     |
|  idegis_astralpool/  <--------|------->|  capturer :8765 (HA Core)     |
|    config_flow, sensors       |        |                               |
+-------------------------------+        +-------------------------------+
```

The integration is unchanged from `0.0.2` — it polls the capturer's
`/api/idegis/state` endpoint on `<host>:8765`. When the add-on is used,
the user simply configures the integration with `host = <HA host>` (or
`localhost` if the add-on is on the same HA instance) instead of an
external host like a Proxmox container.

## Migration from the CT104 deployment

If you used the previous standalone deployment described in
[docs/08-cloud-api-discovery.md](08-cloud-api-discovery.md), you migrate
in two steps:

1. Install and start this add-on. Update the DNS override in your router
   to point `api.idegis.net` at the HA host instead of CT104.
2. Stop and disable the `idegis-state.service` systemd unit on CT104.
   The nginx vhost on CT104 can be removed too. The history stored in
   `/var/log/nginx/idegis_proxy_access.log` can be preserved for offline
   analysis.

The HA integration entry is unchanged — only its `host` configuration
moves from CT104 to the HA host.

## What is not implemented yet

This is `0.1.0`. Open work:

- B0 payload codec — we have the schema and the alphabet, the value
  decoding is pending. Once decoded, the `*_field_raw` sensors will be
  joined by decoded `sensor.pool_ph`, `sensor.pool_orp`,
  `sensor.pool_temperature`, `sensor.pool_salinity`, etc.
- Cloud response decoding — `read.php` replies with a 176-byte body that
  likely carries setpoint/command information back to the device. Once
  decoded, the integration gains the ability to inject custom setpoints
  through the cloud channel.
- `H` hash formula — needed to forge valid requests (required for the
  setpoint injection above).
- Ingress UI — a small dashboard inside the add-on showing live
  capture, B0 hex dump, decoded values and a play/pause toggle.
- Modbus RTU mode — for users who wire an ESP32 + RS485 transceiver into
  the chlorinator's internal Modbus connector (path B).
- Poolstation cloud client — as a path C fallback for users who do not
  want to touch DNS at all.
