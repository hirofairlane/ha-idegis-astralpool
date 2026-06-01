# Integración Idegis / AstralPool en Home Assistant vía Modbus RTU + ESP32

> Documentación, configuraciones y notas para integrar electrolizadores salinos
> **Idegis Domotic 2 / Neolysis** y sus **gemelos AstralPool** (Elite Connect /
> Neolysis del grupo Fluidra) en Home Assistant a través del puerto Modbus RTU
> oficial, usando un ESP32 con adaptador RS485 y ESPHome.

Equipo de referencia del autor: **Idegis Neolysis Neo2-24PH/S** (24 g/h, control
pH integrado).

## Estado del arte (junio 2026)

A día de hoy **no existe integración pública Modbus** para Idegis/AstralPool
Neolysis en Home Assistant. Lo que hay:

| Solución | Tipo | Cobertura | Limitación |
|---|---|---|---|
| [`cibernox/homeassistant-poolstation`](https://github.com/cibernox/homeassistant-poolstation) | Cloud (PoolStation app) | Lecturas y setpoints básicos | Depende del cloud Fluidra |
| [`foXaCe/Fluidra-pool`](https://github.com/foXaCe/Fluidra-pool) | Cloud (Fluidra Connect / iAquaLink) | Equipos "NN" modernos | No prueba explícita en Neolysis |
| [Hilo openHAB de C. Schreiner](https://community.openhab.org/t/integrating-idegis-domotic-2-ls-pool-controller-with-openhab-via-modbus/163549) | Modbus RTU | Prueba de concepto parcial | openHAB, sin mapa de registros completo |
| [`ocorro/esp-modbus-mqtt-astralpool-chlorinator`](https://github.com/ocorro/esp-modbus-mqtt-astralpool-chlorinator) | ESP32 + MQTT | Solo AstralPool Smart Next | No cubre Neolysis |

**Confusión habitual**: *NeoPool* (Sugar Valley / Hidrolife / Bayrol / Brilix) es
**otro fabricante distinto**, con su propia tabla Modbus y su propia integración
HA madura ([alexdelprete/ha-sugar-valley-neopool](https://github.com/alexdelprete/ha-sugar-valley-neopool),
[driver Tasmota NeoPool](https://tasmota.github.io/docs/NeoPool/)).
**No es compatible** con Idegis/AstralPool Neolysis.

## Compatibilidad cruzada Idegis ↔ AstralPool

Idegis pertenece al grupo **Fluidra** desde 2007 (vía Aquaria), opera como OEM y
comparte plataforma **Multi-Tec** con AstralPool. Equivalencias confirmadas:

| Idegis | AstralPool | Plataforma |
|---|---|---|
| Domotic 2 | Elite Connect | Multi-Tec |
| Neolysis (línea residencial) | Neolysis | Multi-Tec |
| Tecno Connect | (línea industrial) | Multi-Tec |

→ **misma tabla Modbus, mismo firmware, mismo módulo wifi PoolStation/Fluidra Connect**.

La tabla Modbus de referencia (no publicada por el fabricante) es
[`20200515 Tabla modbus 1.62 - Elite & control connect.xlsm`](20200515%20Tabla%20modbus%201.62%20-%20Elite%20%26%20control%20connect.xlsm),
incluida en este repo.

## Objetivos del proyecto

1. **Documentar** la tabla Modbus 1.62 en formato legible (markdown), traduciendo
   direcciones, escalas y unidades de cada registro útil. → [docs/02-modbus-reference.md](docs/02-modbus-reference.md)
2. **Publicar** la primera configuración ESPHome funcional para Idegis/AstralPool
   Neolysis. → [esphome/idegis-neolysis.yaml](esphome/idegis-neolysis.yaml)
3. **Cobertura completa**: lectura de todas las medidas (pH, ORP, sal,
   temperatura, producción g/h, alarmas, horas de uso, estado bombas pH/Cl…) +
   escritura de setpoints clave (pH, ORP, % producción, modo manual/auto, reset
   alarmas, programación horaria).
4. **Hardware sugerido**: BOM concreta del ESP32 + adaptador RS485 + sensores
   externos complementarios. → [docs/03-wiring-esp32.md](docs/03-wiring-esp32.md) y [docs/05-sensors-extra.md](docs/05-sensors-extra.md)
5. **Integración HA limpia**: entidades, dashboard ejemplo, automatizaciones
   básicas (winterización, dosis acelerada tras fiesta, modo cubierta, etc.).

## Mapa de la documentación

- [docs/01-hardware.md](docs/01-hardware.md) — Hardware Idegis Neolysis Neo2-24PH/S, capacidades reales y equivalencia AstralPool.
- [docs/02-modbus-reference.md](docs/02-modbus-reference.md) — Mapa de registros Modbus traducido a markdown.
- [docs/03-wiring-esp32.md](docs/03-wiring-esp32.md) — Cableado RS485, adaptador, terminación, alimentación.
- [docs/04-esphome-config.md](docs/04-esphome-config.md) — Diseño de la config ESPHome y entidades HA derivadas.
- [docs/05-sensors-extra.md](docs/05-sensors-extra.md) — Sensores externos AliExpress complementarios (<100 €).

## Estado actual

🚧 **Fase 0 — Documentación previa al cableado.** El hardware existe pero no se
ha conectado todavía al ESP32.

## Aviso legal

Proyecto independiente, sin afiliación con Idegis, AstralPool ni Fluidra. La
tabla Modbus 1.62 incluida proviene de documentación técnica del fabricante;
si Idegis solicita su retirada, será retirada. El uso de funciones de escritura
Modbus en un electrolizador en servicio puede dañar el equipo si se usan valores
fuera de rango — usar bajo tu propia responsabilidad.

## Licencia

A definir (probablemente MIT para código, CC-BY-SA para documentación).
