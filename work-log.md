# Work log — Piscina Idegis / AstralPool

Diario cronológico inverso. Entradas más recientes arriba. Castellano.

---

## 2026-06-02 — Convención inglés + estructura repo público

**Conclusión sesión 1.** Sergio recordó que las convenciones del NAS son:
repo público en inglés, memorias internas en castellano,
`CLAUDE.md` + `work-log.md` en cada proyecto activo, usuario GitHub
`hirofairlane`, naming `ha-<dominio>`.

Acciones:
- Quitado el `.xlsm` del fabricante del git tracking + añadido a `.gitignore`.
- Creados `CLAUDE.md` (castellano) y `work-log.md` (este fichero).
- Traducidos `README.md` y todos los docs públicos al inglés.
- Renombrado objetivo del repo a `ha-idegis-astralpool`.
- Creado esqueleto HACS (`hacs.json`, `repository.yaml`).
- Memoria actualizada con la convención.

Pendiente próxima sesión:
- `gh repo create hirofairlane/ha-idegis-astralpool --public` (autenticar
  primero si hace falta).
- Decidificar el payload `B0` con muestras múltiples capturadas.
- Probar listener en puerto distinto al :80 (nginx ya lo ocupa) para no
  romper el polling del Idegis.

---

## 2026-06-02 (00:08–00:14) — Ventana de diagnóstico activa

Sergio encendió `switch.depuradora` desde HA. Aproveché para escanear y
sniffear.

Hallazgos:
- nmap full TCP (65535 puertos) durante ventana activa → **0 puertos
  abiertos**. Modbus TCP, HTTP, HTTPS: todos cerrados.
- conntrack del router Principal mostró tráfico saliente HTTP plano a
  `45.60.153.189:80` (Incapsula/Imperva).
- DNS query log activado en Principal → resuelve `api.idegis.net` vía
  `9.9.9.9` (ignora DNS del router LAN).
- MITM verificado: DNS override en Principal apuntando `api.idegis.net` →
  CT104 (192.168.1.70). El Idegis envió 12+ requests a CT104:80 capturadas
  por nginx existente.
- Protocolo: `GET /interface/{write,read}.php?B0=<alfanumérico>&H=<MD5_32hex>`,
  polling cada 3-4 s. Sin User-Agent, sin TLS.

Cambios persistentes:
- Cron `/opt/piscina/scripts/sentinel.sh` cada 30 min en CT104 (ronda no
  invasiva).
- Logs capturados preservados en `/opt/piscina/captures/`.
- DNS override en Principal **revertido**.

Decisión arquitectónica:
- **Vía A nueva**: proxy reverso MITM en CT104 → telemetría sin hardware.
- Vía B (Modbus RTU + ESP32) pierde urgencia pero sigue siendo deseable.

---

## 2026-06-01 (23:50–00:00) — Identificación en LAN + sentinel

- Idegis identificado en inventario LAN: `192.168.1.84`, MAC
  `68:27:19:DA:5A:53`, OUI Microchip, hostname DHCP `IDEGIS`. Lease static
  en OpenWrt Principal (`dhcp.@host[42]`).
- Conectado por Ethernet al router **Caseta** (192.168.1.3).
- nmap pasivo (depuradora off): host UP, 0 puertos.
- Herramientas centralizadas en `/opt/piscina/` de CT104:
  `probe-idegis.sh`, `tcpdump-idegis.sh`, `modbus-read.py` (pymodbus 3.13),
  `sentinel.sh`. Cron cada 30 min.
- Doc para Jarvis creada: `INFRA/piscina.md`.

---

## 2026-06-01 (23:16–23:50) — Arranque del proyecto

Sergio inicia el proyecto. Aporta:
- Equipo: Idegis Neolysis Neo2-24PH/S.
- Excel oficial del fabricante con la tabla Modbus 1.62 (no pública).
- Confirmación de equivalencia OEM con AstralPool.

Investigación realizada:
- Estado del arte HA: `cibernox/homeassistant-poolstation` (cloud, activo)
  + hilo openHAB de Schreiner (Modbus RTU prueba de concepto). Nada
  específico Modbus para Idegis/AstralPool Neolysis.
- Confirmada relación Fluidra: Idegis = AstralPool en hardware Multi-Tec.
- Trouble Free Pool (TFP) integrado como referencia química — rangos FC/CYA
  para piscina con SWG + UV.

Estructura del repo creada:
- `README.md`, `docs/01..07.md`, `esphome/idegis-neolysis.yaml`,
  `.gitignore`. Git init, primer commit local.
- Memoria del proyecto creada en
  `~/.claude/projects/-mnt-18T-MIO-Proyectos-piscina/memory/`.
