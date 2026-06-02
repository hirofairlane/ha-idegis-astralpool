# Idegis / AstralPool cloud capturer

Home Assistant add-on that intercepts and decodes the cloud telemetry of
**Idegis** and **AstralPool** pool chlorinators (Fluidra group, Multi-Tec
platform). Works without any extra hardware — just a DNS override on your
router.

## How it works

```
┌───────────────┐     ┌────────────────────┐    ┌─────────────────────┐
│ Chlorinator   │     │ HA OS              │    │ Real cloud (Imperva)│
│ Idegis /      │ DNS │  ┌──────────────┐  │ HTTP│ api.idegis.net      │
│ AstralPool    │ ───>│  │ nginx :80    │──┼───>│ 45.60.153.189       │
│ (api.idegis.  │ HTTP│  │ reverse proxy│  │    │                     │
│ net poll)     │ :80 │  └──────┬───────┘  │    └─────────────────────┘
└───────────────┘     │         │ log      │
                      │  ┌──────▼───────┐  │
                      │  │ capturer.py  │  │
                      │  │ FastAPI :8765│──┼───> HA integration polls
                      │  └──────────────┘  │     /api/idegis/state
                      └────────────────────┘
```

The chlorinator polls `api.idegis.net/interface/{read,write}.php` every
3-4 seconds while the filter pump is running. When you point that domain
to your Home Assistant host via a DNS override on your router, nginx
inside this add-on takes the request, logs it, forwards it transparently
to the real cloud (so the device keeps working) and the Python capturer
parses each line of the log to expose decoded state on a local JSON API
that the companion HA integration consumes.

## Prerequisites

1. The companion integration `idegis_astralpool` installed in Home
   Assistant (custom repository on HACS).
2. A DNS override on your LAN router that points `api.idegis.net` to
   the IP of your Home Assistant host.

   Example for OpenWrt:

   ```sh
   uci add_list dhcp.@dnsmasq[0].address='/api.idegis.net/<HA_IP>'
   uci commit dhcp && /etc/init.d/dnsmasq restart
   ```

   Example for Pi-hole: Local DNS Records → Add → `api.idegis.net` → HA IP.

3. The chlorinator needs to be running (pump on) for the capturer to see
   traffic.

## Configuration options

| Option | Default | Description |
|---|---|---|
| `upstream_host` | `45.60.153.189` | Literal IP of the Idegis/Imperva cloud backend. Hard-coded by IP so we do not loop through our own DNS override. |
| `upstream_host_header` | `api.idegis.net` | Host header sent to the cloud. Must match what the cloud expects. |
| `log_level` | `info` | uvicorn log level for the capturer service. |
| `max_history` | `1000` | How many parsed requests to keep in memory. |
| `online_timeout_s` | `90` | Seconds of silence after which the device is reported as offline. |

## Endpoints exposed by the add-on

| Port | URL | Purpose |
|---|---|---|
| `80/tcp` | `http://<HA>/interface/{read,write}.php` | Receives chlorinator polls (DNS-overridden traffic) |
| `8765/tcp` | `http://<HA>:8765/api/idegis/health` | Health probe used by the HA integration |
| `8765/tcp` | `http://<HA>:8765/api/idegis/state` | Decoded current state (latest values, online flag, polling rate) |
| `8765/tcp` | `http://<HA>:8765/api/idegis/history?n=50` | Last N parsed requests with field-level breakdown |

## What you get in Home Assistant

Once the companion integration is configured, you will see:

- `binary_sensor.idegis_chlorinator_online`
- `sensor.idegis_chlorinator_last_seen`
- `sensor.idegis_chlorinator_polling_rate`
- `sensor.idegis_chlorinator_captured_requests`
- `sensor.idegis_chlorinator_read_php_calls`
- `sensor.idegis_chlorinator_write_php_calls`
- `sensor.idegis_chlorinator_last_endpoint`
- `sensor.idegis_chlorinator_last_cloud_upstream_time`
- `sensor.idegis_chlorinator_li_field_raw`
- `sensor.idegis_chlorinator_cd_field_raw`
- `sensor.idegis_chlorinator_sg_field_raw`
- `sensor.idegis_chlorinator_cy_field_raw`

The raw `LI`/`CD`/`SG`/`CY` fields will be replaced by decoded values
(pH, ORP, salt, etc.) as the B0 payload codec is reverse-engineered.

## Privacy

This add-on **does not phone home**. It only talks to:

- The chlorinator on your LAN.
- The official Idegis/AstralPool cloud (`api.idegis.net` resolved to the
  literal IP `45.60.153.189`) so your equipment keeps working.

No logs leave your network.

## Troubleshooting

- **No traffic reaches the add-on.** Verify the DNS override:
  `nslookup api.idegis.net` from a client should return your HA IP, not
  `45.60.153.189`.
- **The integration shows "offline".** Check the pump is actually running
  — the chlorinator only powers on with the filter pump.
- **Traffic logs but nothing in HA.** Verify the integration is pointing
  to the add-on host. Default is `<HA_HOST>:8765`.

## Source

Code, documentation and roadmap:
<https://github.com/hirofairlane/ha-idegis-astralpool>
