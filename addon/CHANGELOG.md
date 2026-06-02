# Changelog

## 0.1.0 — 2026-06-02

First public release.

- nginx reverse proxy for `api.idegis.net` on port `80`.
- FastAPI capturer service on port `8765` (health / state / history endpoints).
- Persistent log under `/data/captures/idegis_proxy_access.log`.
- Hard-coded upstream IP `45.60.153.189` to avoid DNS loop with the
  router-side override.
- B0 field decomposition (prefix + TD + CI + LI + CD + SG + CY) exposed
  raw. Codec decoding is pending — see project roadmap.
