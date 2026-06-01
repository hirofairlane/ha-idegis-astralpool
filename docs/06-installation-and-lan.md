# 06 · Site-specific installation and LAN discovery

Specifics of the reference installation used during development.

## Physical installation

- **Indoor pool inside a glass enclosure**. Low evaporation, water
  temperature stabilised around **37 °C** (a greenhouse effect, not active
  heating).
- **Equipment room separated** from the pool by a few metres of pipe.
- Hardware in the equipment room:
  - Sand/glass filter with circulation pump.
  - **AstralPool pressure-jet pool cleaner** (water-driven, no electric
    robot).
  - **Idegis Neolysis Neo2-24PH/S** — low-salinity electrolysis + UV
    lamp + pH-minus peristaltic dosing pump.

> **Site implication**: with the water sitting at ~37 °C all year round,
> **any submerged sensor lives in an aggressive environment** — much
> shorter than nominal lifetime. The factory pH/ORP/Cl probes are in the
> equipment room bypass loop (where the water has cooled slightly through
> recirculation). Any extra sensor we add must live **in the bypass loop
> too, never in the pool basin itself**.

This rules out, from the catalog in [docs/05-sensors-extra.md](05-sensors-extra.md),
everything that is "submerged-in-pool". JSN-SR04T (sensor #3) is fine
because it measures from the lid without touching the water; the skimmer
water is also ~37 °C but the sensor never gets wet.

## Electrical wiring of the chlorinator

The Idegis is **wired in series with the filter pump** following the
manufacturer's recommended diagram: the electrolysis cabinet only receives
230 V **when the pump contactor is closed**. With the pump stopped, the
unit is fully off.

The pump contactor is driven from a Home Assistant entity (`switch.depuradora`).
Turning it on from HA forces a diagnostic window.

### Project implications

1. **No pump, no diagnostics**. The wifi/ethernet module is on the same
   power line, so without the pump there is no LAN presence at all.
2. **However**: we have observed the device replying to ping while the
   pump is reportedly off (2026-06-01 23:54). Hypotheses:
   - the pump was actually scheduled on at that time, or
   - the wifi/eth module has standby power (internal scheme not known), or
   - the TCP/IP stack lingers briefly after a recent power-off.
3. The CT104 sentinel (see *Sentinel* below) records actual activity
   windows over time to settle this.

## LAN identity

| Field | Value |
|---|---|
| DHCP hostname | `IDEGIS` |
| IP | **192.168.1.84** (static lease on OpenWrt main router, `dhcp.@host[42]`) |
| MAC | `68:27:19:DA:5A:53` |
| OUI | Microchip Technology |
| Connection | Ethernet via Caseta router (192.168.1.3) |

The Idegis sends telemetry to a cloud server (daily email report to the
user). Endpoint is [decoded in docs/08-cloud-api-discovery.md](08-cloud-api-discovery.md).

### Port state — pump running, ICMP UP

`nmap -p- -sS --min-rate 1000` from CT104 during an active window
(2026-06-02 00:08–00:12):

- Host UP (ICMP replies).
- **0 TCP ports open**, all 65535 scanned.
- Modbus TCP 502: closed.
- HTTP/HTTPS 80/443/8080/8443: closed.

Conclusion: the chlorinator is **client only**. It listens on nothing.

## Sentinel on CT104

To avoid manual discovery on every session, a passive process is deployed
on the LXC 104 (jarvis stack). It rounds every 30 minutes and records
state.

Full details in [`INFRA/piscina.md`](../../INFRA/piscina.md) and
`/opt/piscina/docs/README.md` inside CT104. Quick recap:

```bash
# One-shot diagnostic
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/probe-idegis.sh"

# 60 s passive capture (run after starting the pump)
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/tcpdump-idegis.sh 60"

# Modbus TCP probe attempt
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/modbus-read.py"

# Sentinel history
ssh zeratul "pct exec 104 -- tail -50 /opt/piscina/logs/sentinel.log"
```

Active cron in CT104:

```
*/30 * * * * /opt/piscina/scripts/sentinel.sh >> /opt/piscina/logs/cron.log 2>&1
```

If the sentinel ever detects port 502 open, it creates
`/opt/piscina/state/modbus-tcp-detected` with a timestamp — the architectural
pivot signal.

## Open TODOs for this installation

- [ ] Confirm exact RS485 adapter model purchased.
- [ ] During the next pump window, run port scan + tcpdump + modbus-read in
      parallel and capture more cloud HTTP samples.
- [ ] Decide whether the sentinel should be allowed to start the pump for a
      weekly deep round (probably not — electricity and chlorine cost).
- [ ] Consider rewiring the consumption meter so it measures the whole
      chlorinator instead of just the contactor coil.
