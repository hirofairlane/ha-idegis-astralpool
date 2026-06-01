# 08 · Idegis cloud API discovery (HTTP, no TLS)

Result of the active diagnostic window **2026-06-02 00:08–00:13** with the
pump running and the chlorinator electronics powered.

## Critical findings

### 1. The chlorinator does NOT expose any inbound LAN port

Confirmed with two independent nmap scans during the active window
(top-1000 in 101 s and the full 65535 ports in 131 s):

- ICMP replies (host UP)
- **0 TCP ports open**
- Modbus TCP (502): closed/timeout
- HTTP (80, 8080, 443, 8443): closed
- Any port: closed

**Consequence**: Modbus TCP is **off the table**. The device is purely a
**client**, not a server.

### 2. The chlorinator polls `api.idegis.net` over plain HTTP

Captured via the **conntrack table of the main OpenWrt router** and
confirmed by the **dnsmasq query log**:

- **Domain**: `api.idegis.net`
- **Port**: 80 (HTTP, **no TLS**)
- **Backend**: Imperva/Incapsula (anycast IP 45.60.153.189, AS19551)
- **DNS resolver**: 9.9.9.9 (Quad9) — the device ignores the LAN DNS and
  uses a fixed public upstream
- **Polling rate**: 1 request every 3-4 seconds (write.php interleaved
  with read.php)

### 3. Protocol shape

Endpoints observed:

| Endpoint | Inferred role |
|---|---|
| `GET /interface/write.php` | The device **pushes** telemetry/state to the cloud |
| `GET /interface/read.php` | The device **polls** for pending commands |

Both carry two query-string parameters:

```
?B0=<alphanumeric encoded payload>&H=<MD5 hash, 32 hex>
```

#### Example

```
GET /interface/write.php?B0=JS4fUX2d24UWcVbXJYfYfd4fU0W430TD4fUX2d24cbabWbcaXXaba4fU0W430CI4fUX2d24a4fU0W430LI4fUX2d24aacad4fU0W430CD4fUX2d24bVWadfbWaa4fU0W430SG4fUX2d24aVgfW&H=C651B84CA98BD763E88A7CFD6DE86EC6 HTTP/1.1
```

User-Agent is empty (`"-"`).

#### Preliminary analysis of `B0`

- Character set: alphanumeric (`0-9 A-Z a-z`).
- **Field separator candidate**: the string `4fU0W430` repeats multiple
  times and acts as a delimiter between fields.
- Tokens between separators look like **field identifiers**:
  - `TD` → temperature data?
  - `CI` → current?
  - `LI` → limit?
  - `CD` → counter/timestamp (varies request-to-request, monotonic)
  - `SG` → setpoint generic?
- A second-level structure `4fU0W430<FIELD>4fUX2d24<VALUE>` separates key
  from value.
- The leading `JS4fUX2d24UWcVbXJYfYfd` is invariant across requests —
  likely device identity + session token.

Hypotheses to validate:

1. The payload uses a reversible encoding (not strong encryption),
   probably letter substitution or modified base32 on top of a key-value
   structure.
2. `H = MD5(B0 + shared_secret)` or `MD5(B0 + device_serial + timestamp_trunc)`.
3. If validated, we can both decode incoming telemetry and forge valid
   responses to `read.php` to inject local commands.

### 4. MITM capability verified

For 60 s a DNS override was applied on the main router
(`api.idegis.net → 192.168.1.70` = CT104). The Idegis correctly sent its
requests to CT104:80, where the existing nginx logged 5 connections (all
`TIME_WAIT` confirmed via `ss`). The device kept running even though the
answers were 404s — it is **resilient to transient failures** and retries.

This proves that we can:

- Run a **permanent reverse proxy** in CT104 that intercepts, decodes and
  forwards to the original cloud.
- Expose every metric of the payload as a HA sensor.
- Inject modified replies into `read.php` to send commands to the device
  without going through the Idegis cloud (cloud-emulated bidirectional
  control).

## New architecture — three complementary paths

| Path | Purpose | Status | Cost |
|---|---|---|---|
| **A) Cloud-MITM proxy** (new) | Pushed telemetry every 3–4 s, no contact with the chlorinator | To implement | ~0 € (software in CT104) |
| **B) Modbus RTU + ESP32** (original plan) | Full local control, deterministic, internet-independent | To implement | ~30 € hardware |
| **C) Poolstation cloud** (`cibernox/...`) | Drop-in fallback / cross-check | Done | 0 € |

**Revised recommendation**: start with path **A**. Fastest to a result,
no physical intervention, immediate telemetry. Path B (RTU) remains
desirable for offline control and to fully disconnect from the cloud, but
is no longer urgent.

## Next technical phase (path A)

1. **Decode `B0`** from multiple samples captured in nginx logs. Look for
   invariants (identity prefix) and an increment pattern (timestamps /
   counters).
2. **Validate the formula of `H`**: try `MD5(B0)`, `MD5(B0+serial)`,
   `MD5(B0+secret)`, etc.
3. **Build the transparent reverse proxy** in CT104:
   - Listen on port 80 on a different IP (the current nginx already binds
     :80) or extend nginx with a `location /interface/` reverse proxy.
   - Forward to the real `api.idegis.net` (DNS resolved out-of-band to
     avoid an override loop).
   - Log every request/response.
   - Publish decoded metrics via MQTT (mosquitto is already running in
     CT104).
4. **HA**: consume MQTT → sensor entities.

## Does Imperva notice the MITM?

The Idegis does not use TLS and does not pin certificates. A DNS override
MITM is **invisible to both the Idegis and Imperva** (the forwarded
request reaches the cloud through the same TCP path as always — only ~1-2
ms of extra latency).

## Capture log

```
/opt/piscina/captures/idegis-cloud-protocol-<TIMESTAMP>.log
```

Full nginx access log copy from the override window (12+ requests from
the device, all answered with default 404).

## Update — transparent reverse proxy live (2026-06-02)

A dedicated nginx vhost is now running in CT104:

```nginx
log_format idegis_full '$time_iso8601 client=$remote_addr "$request" '
                       'status=$status sent=$body_bytes_sent '
                       'upstream_status=$upstream_status upstream_time=$upstream_response_time '
                       'req_len=$request_length';

server {
    listen 80;
    server_name api.idegis.net;
    access_log /var/log/nginx/idegis_proxy_access.log idegis_full;
    error_log  /var/log/nginx/idegis_proxy_error.log warn;

    location / {
        proxy_pass http://45.60.153.189$request_uri;
        proxy_set_header Host api.idegis.net;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.0;
        proxy_buffering off;
        proxy_read_timeout 30s;
        proxy_connect_timeout 5s;
    }
}
```

DNS override applied permanently on the main router (`api.idegis.net →
192.168.1.70`). The chlorinator keeps polling normally and the cloud
keeps replying — the device is completely unaware of the MITM.

### Observed traffic shape (post-proxy)

- Polling rate while pump running: 1 request every ~25–30 s (interleaved
  `read.php` and `write.php`).
- `upstream_status=200` consistently, `upstream_time≈0.1s`.
- `read.php` → cloud responds with a **176-byte body** (likely the
  command/configuration block back to the device).
- `write.php` → cloud responds with a **16-byte body** (likely an ACK).

### Confirmed B0 schema (17 samples)

```
<prefix>
  4fU0W430 TD 4fUX2d24 <value>      ← INVARIANT: cbabWbcaXXaba (session/serial)
  4fU0W430 CI 4fUX2d24 <value>      ← INVARIANT: a
  4fU0W430 LI 4fUX2d24 <value>      ← slow counter
  4fU0W430 CD 4fUX2d24 <value>      ← fast counter (each request)
  4fU0W430 SG 4fUX2d24 <value>      ← (write.php only) state/setpoint flags
```

Prefix `JS4fUX2d24UWcVbXJYfYfd` is invariant across all 17 samples and is
almost certainly the device identity token.

### B0 alphabet

24 characters: `0234CDGIJLSTUVWXYabcdefg`. Not base62, not hex, not
base32 — it is a custom 24-character alphabet. The lexicographic order
does **not** match the codec order (deltas between consecutive `CD`
values do not match the time intervals when interpreted that way). The
true order has to be reconstructed empirically.

### Hash H — no obvious formula yet

Tested against the captured samples:

| Candidate | Matches |
|---|---|
| `MD5(B0)` | 0 |
| `MD5(path+B0)` | 0 |
| `MD5(B0+path)` | 0 |
| `MD5(B0+"idegis")` | 0 |
| `MD5(B0+"Idegis")` | 0 |
| `MD5(B0+"poolstation")` | 0 |
| `MD5("?B0="+B0)` | 0 |

`H` is almost certainly `MD5(B0 + <shared_secret>)`. The shared secret
needs to be brute-forced or extracted from the device firmware.

### Open work

- Decode `B0` alphabet by feeding ground-truth measurements (Poolstation
  app open in another window during a capture).
- Decode cloud responses (the 176-byte read.php body) to understand the
  command protocol.
- Brute-force the hash `H` shared secret (dictionary attack with common
  values: "idegis", "fluidra", "neolysis", "poolstation", device serial,
  domain, etc.).

## Derived TODOs

- [ ] Capture 100+ requests from the device (next window, this time with a
      custom listener that returns 200 OK with an empty body, so the
      polling does not perceive failure).
- [ ] Empirically decode `B0`.
- [ ] Validate the `H` formula.
- [ ] Decide whether to rewrite nginx as a reverse proxy or stand up a
      dedicated container/IP for the Idegis listener.
- [ ] Once stable, drop path C (Poolstation cloud) as redundant or keep
      it as a backup.
- [ ] Consider **blocking DNS for `api.idegis.net` at the router** once
      the proxy is operational, so the device never reaches the real
      cloud and the system lives 100% locally.
