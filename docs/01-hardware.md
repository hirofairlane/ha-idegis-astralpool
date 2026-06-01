# 01 · Hardware

## Equipo de referencia

**Idegis Neolysis Neo2-24PH/S**

| Parámetro | Valor |
|---|---|
| Familia | Neolysis (electrólisis salina + UV opcional, plataforma Multi-Tec) |
| Producción | 24 g/h de cloro |
| Control pH | Integrado (bomba peristáltica + sonda) |
| Sufijo `/S` | Variante con sonda pH montada de fábrica |
| Cloración | Sí (salida g/h variable) |
| ORP / Redox | No de fábrica en este SKU (slot disponible para futuro) |
| Temperatura | Sí (medida desde la celda) |
| Sal | Sí (calculada por corriente y tensión de electrodos) |
| Caudal | Detección sí/no (no caudalímetro m³/h) |
| Modbus | Slave RTU, configurable a 9600/19200 bps, 8E1/8N2/8N1, dirección 1-5 (default 2) |
| Modbus secundario | Sí — la placa expone un segundo bus Modbus slave (`secondary_modbus_slave` en el bitmap de capacidades) |
| Slot relés | Sí — se puede ampliar con módulo de salidas |
| App cloud | PoolStation (si se acopla el módulo wifi opcional) |

Capacidades reportadas por el registro holding `0x06`
(`ID_Technologies_implemented`) — el bitmap real lo confirmaremos al primer
pairing por Modbus, pero según el SKU `Neo2-24PH/S`:

- `electrolysis` (bit 0) ✅
- `ph` (bit 1) ✅
- `cl-orp` (bit 2) ⚠️ slot disponible, **no montado de fábrica** en este SKU
- `cl-ppm` (bit 3) ⚠️ slot disponible, no montado
- `temperature` (bit 4) ✅
- `salt` (bit 5) ✅
- `uv` (bit 6) ⚠️ depende del SKU (la línea Neolysis lo soporta; `/S` típicamente no lleva UV)
- `caudal` (bit 7) ❌
- `pressure` (bit 8) ❌
- `biopool` (bit 9) ✅
- `secondary_modbus_slave` (bit 11) ✅
- `slot_relay` (bit 13) ✅
- `electrolysis_low_salt` (bit 15) ✅

## Equivalencia OEM con AstralPool (Fluidra)

| Idegis | AstralPool | Notas |
|---|---|---|
| **Domotic 2** | **Elite Connect** | Mismo equipo, mismo firmware Multi-Tec, misma tabla Modbus, mismo módulo wifi (PoolStation). El distribuidor oficial Fluidra/SIBO publica documentación marcada como Idegis describiendo el Elite Connect. |
| **Neolysis** | **Neolysis** | Mismo nombre comercial en ambas marcas. Algunos retailers lo venden bajo doble marca (`Neolysis Zero Salt x UV AstralPool` con SKU Idegis). |
| Tecno Connect | (línea industrial) | Multi-Tec industrial. |

Esta documentación, por tanto, es **directamente aplicable a los AstralPool
Elite Connect y AstralPool Neolysis equivalentes**.

> ⚠️ **NO confundir** con **Sugar Valley NeoPool** (Hidrolife/Aquascenic/Bayrol/Brilix).
> Es **otro fabricante diferente**, con su propia tabla Modbus y su propia
> integración HA. El nombre se parece pero no son compatibles.

## Adaptador RS485 (pendiente confirmar modelo)

Opciones habituales:

- **C-MOD de Idegis** (kit oficial) — convertidor Modbus pensado para
  acoplarse al conector interno del equipo. Caro pero plug-and-play.
- **Conversor RS485 genérico** (MAX485, MAX3485, SP3485, módulo TTL↔RS485 con
  control de flujo automático tipo "auto direction") + ESP32 — opción típica
  DIY a coste despreciable (<5 €).

**TODO** Sergio: confirmar cuál tiene comprado para ajustar [docs/03-wiring-esp32.md](03-wiring-esp32.md).

## ESP32

Cualquier ESP32 sirve (DevKit-C v4, S3, WROOM-32, etc.). Recomendado con
conector USB-C, WiFi estable y al menos 2 UART hardware libres (UART0 reservada
para flasheo/logs; usaremos UART1 o UART2 para el RS485). Si Sergio quiere
añadir más sensores I²C (ADS1115 para presión, etc.), reservar GPIO21/22 (I²C).
