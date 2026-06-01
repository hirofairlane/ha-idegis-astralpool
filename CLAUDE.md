# Piscina — contexto persistente para Claude

> Documento interno (castellano) para sesiones Claude. El **repo público va
> en inglés** (README, docs/, esphome/). Convención alineada con
> [`Energy optimizer`](../Energy%20optimizer/) y [`HA alarm`](../HA%20alarm/).

## Objetivo

Integrar el clorador salino **Idegis Neolysis Neo2-24PH/S** (y sus gemelos
**AstralPool**) en Home Assistant. El proyecto termina siendo un repo público
+ futuro custom_component HACS.

## Hardware en propiedad

- **Idegis Neolysis Neo2-24PH/S** (24 g/h, control pH integrado, UV, baja
  salinidad). MAC `68:27:19:DA:5A:53`, IP fija LAN `192.168.1.84`,
  conectado por Ethernet al router **Caseta** (`192.168.1.3`).
- Adaptador Modbus RTU comprado (modelo concreto pendiente confirmar).
- Piscina cubierta con cerramiento de cristal, agua estable ~37 °C. **Nada
  sumergible en el vaso es viable** (temperatura + agresividad).

## Decisiones técnicas tomadas

- **Modbus TCP descartado** (2026-06-02). El Idegis no expone NINGÚN puerto.
- **Vía A (prioritaria, descubierta el 2026-06-02)**: cloud-MITM HTTP en CT104.
  El equipo es cliente HTTP plano (sin TLS) a `api.idegis.net/interface/{read,write}.php?B0=...&H=...`.
  Decodificar `B0` (codificación reversible alfanumérica) + validar `H = MD5(...)`.
- **Vía B**: Modbus RTU + ESP32 + RS485. Aplaza control bidireccional offline.
- **Vía C (backup)**: cloud Poolstation via `cibernox/homeassistant-poolstation`.

## Equivalencia AstralPool ↔ Idegis

Confirmado: ambos son rebadging Multi-Tec (grupo Fluidra). El repo cubre las
dos marcas y debe nombrarlas en inglés en title/description para SEO.

| Idegis | AstralPool |
|---|---|
| Domotic 2 | Elite Connect |
| Neolysis | Neolysis |

**NO confundir** con Sugar Valley NeoPool (otro fabricante distinto).

## Herramientas centralizadas en CT104

Convención del usuario: todo diagnóstico/red en `/opt/piscina/` dentro de
LXC 104. Ver [`INFRA/piscina.md`](../INFRA/piscina.md) y
[`docs/06-installation-y-lan.md`](docs/06-installation-y-lan.md).

```bash
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/probe-idegis.sh"
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/sentinel.sh"
ssh zeratul "pct exec 104 -- tail -50 /opt/piscina/logs/sentinel.log"
```

Cron CT104 cada 30 min: `/opt/piscina/scripts/sentinel.sh`.

## Convenciones del repo público (objetivo)

- **GitHub user**: `hirofairlane` (alineado con `ha-energy-optimizer`).
- **Nombre repo**: `ha-idegis-astralpool`.
- **Licencia**: MIT para código, CC-BY-SA 4.0 para docs.
- **NO subir** `20200515 Tabla modbus 1.62 - Elite & control connect.xlsm`
  (documento técnico del fabricante). Solo la versión derivada
  `docs/02-modbus-reference.md`.
- **Idioma del repo público**: inglés.
- **Estructura objetivo**: similar a `ha-energy-optimizer` para que pueda
  servirse vía repositorio HACS (`repository.yaml`).

## Permisos en el proyecto

Skip-permissions total. Aplica:
- SSH a `zeratul`, `pct exec 104` y routers OpenWrt (Caseta vía RSA legacy,
  Principal/Sotano/Arriba vía ed25519).
- Activar `switch.depuradora` en HA cuando aporte valor para diagnóstico.
- Modificar `uci` en routers OpenWrt (DNS overrides, iptables/nft logging) —
  siempre **revirtiendo** al terminar para no dejar residuo.
- Modificar/expandir `/opt/piscina/` en CT104 sin pedir confirmación.

## Documentos clave

- [`README.md`](README.md) — inglés, cara pública del proyecto.
- [`docs/`](docs/) — inglés, documentación técnica pública.
- [`esphome/`](esphome/) — config ESPHome (vía B).
- [`work-log.md`](work-log.md) — castellano, diario cronológico inverso.
- [`INFRA/piscina.md`](../INFRA/piscina.md) — castellano, info para Jarvis.

## Sesiones Claude por este proyecto

Memoria viva en `~/.claude/projects/-mnt-18T-MIO-Proyectos-piscina/memory/`.
Leer `MEMORY.md` antes de empezar.
