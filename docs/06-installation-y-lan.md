# 06 · Instalación específica y descubrimiento en LAN

Detalles de la instalación concreta de Sergio que condicionan el diseño.

## Instalación física

- **Piscina cubierta con cerramiento de cristal**. Evaporación baja,
  temperatura del agua estabilizada en torno a **37 °C** (consecuencia del
  efecto invernadero del cerramiento, no de calefacción activa).
- **Cuarto de máquinas separado**, a unos metros de la piscina, con
  cableado hacia el vaso.
- Hardware presente:
  - Bomba de filtración con depuradora (filtro de arena/vidrio).
  - **Limpiafondos por chorro AstralPool** (presión hidráulica desde la
    propia depuradora — no robot eléctrico).
  - **Idegis Neolysis Neo2-24PH/S** — electrólisis salina **de baja
    salinidad** + lámpara UV + bomba peristáltica minoradora de pH.

> **Implicación clave**: como el agua está siempre a ~37 °C, **cualquier sensor
> sumergido en el vaso vive en condiciones agresivas** (vida útil mucho más
> corta de lo nominal). Las sondas pH/ORP/Cl del Idegis están en el bypass del
> cuarto de máquinas (donde el agua llega ya más fría, recirculada). Cualquier
> sensor extra que añadamos debe ir **también en bypass**, nunca dentro del
> vaso.

→ Esto elimina del catálogo de sensores extras todo lo que sea "sumergido en
piscina" (ej. nivel hidrostático directo, sondas in-pool con flotador). En
[docs/05-sensors-extra.md](05-sensors-extra.md) el sensor #3 (JSN-SR04T
ultrasónico) sigue siendo válido porque mide desde la tapa, sin contacto, y el
agua del skimmer también es ~37 °C pero no toca al sensor.

## Cableado del equipo

El Idegis está **acoplado en serie a la depuradora** según el esquema
recomendado por el fabricante: la electrólisis recibe alimentación 230 V
**solo cuando el contactor de la bomba de filtración está cerrado**. Cuando la
depuradora está parada, el equipo está completamente apagado.

Sergio puede activar la depuradora desde Home Assistant (entidad concreta del
switch del contactor pendiente de documentar — TODO).

### Implicaciones para el proyecto

1. **Sin ventana de bomba, sin diagnóstico**. El módulo Ethernet del Idegis
   también está alimentado por la misma línea, así que en off no responde
   nada (ni siquiera ping).
2. **Pero**: lo hemos visto **respondiendo a ping** con la depuradora apagada
   (2026-06-01 23:54). Hipótesis a confirmar:
   - O bien la depuradora estaba realmente activa (timer programado),
   - O bien el módulo wifi/eth del Idegis lleva alimentación de respaldo (no
     se conoce esquema interno).
   - O bien la TCP/IP stack queda activa por inercia tras un apagado reciente.
3. El centinela en CT104 (ver §Centinela) registra las ventanas reales de
   actividad para responder estas preguntas con datos.

## Descubrimiento en LAN

| Campo | Valor |
|---|---|
| Hostname DHCP | `IDEGIS` |
| IP | **192.168.1.84** (lease static en OpenWrt `dhcp.@host[42]`) |
| MAC | `68:27:19:DA:5A:53` |
| OUI | Microchip Technology |
| Conexión | Ethernet cableado |

Tráfico saliente al cloud: el equipo envía telemetría a un servidor Idegis
(reporte diario por email al usuario). Pendiente capturar con tcpdump qué
endpoint exacto y protocolo. → ver §Centinela.

### Estado de puertos (standby — bomba off pero responde a ping)

Escaneo nmap completo TCP (todos los 65535 puertos) desde CT104, 2026-06-01:

- Host UP (ICMP responde).
- **0 puertos TCP abiertos**.

Esto significa que el módulo Ethernet/wifi del Idegis tiene su stack TCP/IP
activa pero **todos los servicios dormidos**. Habrá que repetir el escaneo
durante una ventana de depuradora activa para mapear qué servicios despiertan
(esperado al menos puerto 80 web embebida y/o **502 Modbus TCP** — si este
último aparece, no necesitamos cablear ESP32+RS485).

## Centinela en CT104

Para no depender de hacer el descubrimiento "a mano", se ha desplegado un
proceso pasivo en el LXC 104 (`jarvis stack`) que ronda cada 30 minutos y
registra estado.

Ver detalle completo en [`INFRA/piscina.md`](../../INFRA/piscina.md) y
[`/opt/piscina/docs/README.md`](file:///opt/piscina/docs/README.md) dentro de
CT104. Resumen:

```bash
# Diagnóstico instantáneo
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/probe-idegis.sh"

# Captura tráfico 60 s tras activar la bomba
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/tcpdump-idegis.sh 60"

# Intentar lectura Modbus TCP
ssh zeratul "pct exec 104 -- /opt/piscina/scripts/modbus-read.py"

# Ver log histórico
ssh zeratul "pct exec 104 -- tail -50 /opt/piscina/logs/sentinel.log"
```

Cron activo en CT104:
```
*/30 * * * * /opt/piscina/scripts/sentinel.sh >> /opt/piscina/logs/cron.log 2>&1
```

Si el centinela detecta el puerto 502 abierto alguna vez, crea
`/opt/piscina/state/modbus-tcp-detected` con timestamp — pivote definitivo de
arquitectura.

## TODOs pendientes con la instalación

- [ ] Identificar entidad HA del contactor de la bomba (`switch.depuradora_*`)
- [ ] Hacer una ventana de diagnóstico de 5-10 min con la bomba en marcha y:
  - port scan completo TCP+UDP
  - tcpdump 5 min para capturar tráfico cloud (DNS, TLS SNI, destinos)
  - probar Modbus TCP 502 con `modbus-read.py`
  - probar HTTP en puerto 80 (¿web embebida con login?)
- [ ] Decidir si el centinela debe poder activar él la bomba para una ronda
  semanal (probablemente no — coste eléctrico y de cloro).
