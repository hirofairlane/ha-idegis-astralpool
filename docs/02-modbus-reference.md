# 02 · Mapa Modbus Idegis / AstralPool (tabla 1.62)

Resumen accionable de la tabla oficial
[`20200515 Tabla modbus 1.62 - Elite & control connect.xlsm`](../20200515%20Tabla%20modbus%201.62%20-%20Elite%20%26%20control%20connect.xlsm).

## Notas previas

- **Funciones soportadas**: `0x03` (read holding), `0x04` (read input), `0x06`
  (write single holding), `0x10` (write multiple holding).
- **PROHIBIDO** (causa comportamiento indefinido en el equipo): `0x01` read
  coils, `0x05` write single coil, `0x15` write multiple coils.
- **Direcciones de esclavo válidas**: 1 a 5. Default `2`.
- **Comunicación por defecto**: 9600 bps, 8 bits, paridad par (E), 1 stop (8E1).
  El holding `0x01` `COM_Setup` permite cambiarlo según la siguiente tabla:

  | Valor | Configuración |
  |---|---|
  | 0 | 9600 8E1 *(default)* |
  | 1 | 19200 8E1 |
  | 2 | 9600 8N2 |
  | 3 | 19200 8N2 |
  | 4 | 9600 8N1 |
  | 5 | 19200 8N1 |

- **Convención de escalas**: la mayoría de medidas vienen como enteros sin signo
  con factor 10 o 100. Indicado en cada registro.
- **Convención uint32**: cuando un valor necesita 32 bits se publica en dos
  registros consecutivos `_lsb` + `_msb` (orden de palabra: lsb-primero).

## Mapa de zonas

| Zona | Input (0x04) | Holding (0x03) | Contenido |
|---|---|---|---|
| Identify | — | `0x00` | ID fabricante, modelo, capacidades, FW/HW |
| Update | `0x00` | `0x14` | Reservado actualización |
| Sistema | `0x1A` | — | — |
| Común | `0x20` | `0x20` | Estado global, reset alarmas, calibración |
| Flow | `0x30` | `0x30` | Detección de flujo |
| Electrólisis | `0x40` | `0x40` | Producción cloro, corriente/tensión electrodos |
| pH | `0x50` | `0x50` | Medida pH + setpoint + dosificación |
| CL (ORP/PPM) | `0x80` | `0x80` | Redox, ppm cloro libre + setpoints |
| Temperatura | `0xB0` | `0xB0` | Temp + umbrales alarma |
| Sal/conductividad | `0xC0` | `0xC0` | Salinidad + umbrales |
| UV | `0xD0` | `0xD0` | Lámpara UV (si está) |
| Presión | `0xE0` | `0xE0` | Presostato (si está) |
| Hora | `0xF0` | `0xF0` | Sunrise/sunset, reloj |
| Inputs | `0x100` | — | Entradas digitales 1-4 |
| Outputs | `0x110` | `0x110` | Salidas relé 1-4 + enclavamientos |
| Time programs | — | `0x170` | 4 períodos horarios x 10 timeprogs |
| Slots/pbas | `0x120` | `0x1E0` | Slots de sondas (calibraciones) |
| Internet | `0x130` | `0x220` | Estado wifi/ethernet, IP, MAC |
| TFT | — | `0x230` | Brillo y idioma pantalla |
| VS pump | `0x140` | `0x240` | Bomba velocidad variable |
| Valve | `0x150` | `0x250` | Selectora backwash automático |

---

## Identificación y configuración (holding `0x00`–`0x11`)

| Reg | Nombre | Editable | Default | Notas |
|---|---|---|---|---|
| `0x00` | `ID_Address` | Sí | 2 | Dirección Modbus esclavo |
| `0x01` | `COM_Setup` | Sí | 0 | Ver tabla COM_Setup arriba |
| `0x02–0x03` | `ID_Manufacturer_hi/lo` | Con pass | 0/178 | Constante Idegis |
| `0x04–0x05` | `ID_Product_code_hi/lo` | Con pass | 0x2016 | `0x2016` = electrolizador g/h |
| `0x06` | `ID_Technologies_implemented` | Bitmap RO | — | Capacidades hardware (ver tabla bits) |
| `0x07` | `HW Version` | RO | — | |
| `0x08` | `FW Version` | RO | — | |
| `0x09–0x0B` | `MODEL_Serie_hi/mi/lo` | RO | — | Nº serie 48 bits |
| `0x0C` | `CUSTOMER_code` | Con pass | — | Customer code (OEM cliente) |
| `0x0D` | `ID_Technologies_enabled` | Bitmap | — | Cuáles activas |
| `0x10` | `Watchdog_time` | Sí | 0 | Watchdog Modbus (s) |
| `0x11` | `Watchdog_config` | Sí | 0 | Comportamiento al saltar watchdog |

### Bitmap `ID_Technologies_implemented` (holding `0x06`)

| Bit | Nombre | Significa |
|---|---|---|
| 0 | electrolysis | Hace electrólisis |
| 1 | ph | Lleva slot pH |
| 2 | cl-orp | Lleva slot ORP/redox |
| 3 | cl-ppm | Lleva slot PPM amperométrico |
| 4 | temperature | Mide temperatura |
| 5 | salt | Mide sal |
| 6 | uv | Soporta lámpara UV |
| 7 | caudal | Mide caudal m³/h |
| 8 | pressure | Mide presión |
| 9 | biopool | Soporta modo biopool |
| 11 | secondary_modbus_slave | Tiene segundo Modbus esclavo |
| 12 | ethernet | Tiene Ethernet |
| 13 | slot_relay | Acepta slot de relés |
| 15 | electrolysis_low_salt | Soporta electrólisis baja sal |

---

## Medidas (input registers, función `0x04`, solo lectura)

| Reg | Nombre | Unidad | Escala | Ejemplo |
|---|---|---|---|---|
| `0x51` | `ph_measure` | pH | /10 | 712 → 7,12 |
| `0x81` | `orp_measure` | mV | /1 | 750 → 750 mV |
| `0x83` | `ppm_measure` | ppm | /100 | 159 → 1,59 ppm |
| `0x84` | `ppm_probe_current` | mA | /10 | 159 → 15,9 mA |
| `0xB1` | `temperature_measure` | °C | /10 | 256 → 25,6 °C |
| `0xC1` | `salt_measure` | g/L (ppt) | /100 | 365 → 3,65 g/L (=3650 ppm) |

## Electrólisis (input `0x40`–`0x4D`)

| Reg | Nombre | Unidad | Notas |
|---|---|---|---|
| `0x40` | `electrolysis_status` (bitmap) | — | Bit 0 running, bit 1 polarity, bit 2 cover input, bit 3 cover setpoint en uso, bit 7 límite g/día alcanzado |
| `0x41` | `production_pct_target` | % | Setpoint actual aplicado (puede ser normal o cover) |
| `0x42` | `production_pct_now` | % | Producción instantánea |
| `0x43` | `current_electrodes` | A | /100 (1741 → 17,41 A) |
| `0x44` | `voltage_electrodes` | V | /100 (1741 → 17,41 V) |
| `0x45` | `g_hour_production_now` | g/h | enteros |
| `0x46` | `g_production_today` | g | acumulado desde 00:00 |
| `0x47` | `time_electrolysis_today` | min | acumulado desde 00:00 |
| `0x48–0x49` | `hours_running_elect_total` | h | uint32 (lsb,msb) |
| `0x4A–0x4B` | `hours_running_elect_partial` | h | uint32 (lsb,msb) |
| `0x4C` | `total_reset_elect` | — | Nº reset de horas parciales |
| `0x4D` | `g_production_this_hour` | g | Desde la hora en curso |

## Bombas pH / Cl — telemetría (input)

| Reg | Nombre | Unidad |
|---|---|---|
| `0x57` | `ph_dosage_time_output_1` | min |
| `0x58` | `ph_pct_pump_output_1` | % |
| `0x59` | `ph_dosis_seconds_run_output_1` | s |
| `0x5A–0x5B` | `ph_time_pump_running_total/partial_1` | h |
| `0x87` | `cl_dosage_time_output_1` | min |
| `0x88` | `cl_pct_pump_output_1` | % |
| `0x89` | `cl_dosis_seconds_run_output_1` | s |
| `0x8A–0x8B` | `cl_time_pump_running_total/partial_1` | h |

---

## Setpoints y umbrales (holding registers, función `0x06`)

### Electrólisis (`0x41`–`0x43`)

| Reg | Nombre | Unidad | Default | Notas |
|---|---|---|---|---|
| `0x41` | `setpoint_production_normal` | % | 0 | 0–100 |
| `0x42` | `setpoint_production_cover` | % | 10 | % cuando hay cubierta de piscina puesta |
| `0x43` | `g_per_day_limit` | g | 0 | 0 = sin límite |

### pH (`0x50`–`0x5E`)

| Reg | Nombre | Unidad | Default | Notas |
|---|---|---|---|---|
| `0x51` | `ph_low_alarm_limit` | pH ×100 | 650 (6,50) | |
| `0x52` | `ph_high_alarm_limit` | pH ×100 | 850 (8,50) | |
| `0x55` | `ph_seconds_initialization` | s | 0 | Tiempo de espera estabilización tras arranque |
| `0x57` | `setpoint_ph_output_1` | pH ×100 | 720 (7,20) | Setpoint pH |
| `0x58` | `dosage_time_limit_ph_output_1` | min | 60 | Pumpstop si dosifica más de N min seguidos |
| `0x59` | `max_pct_pump_ph_output_1` | % | 100 | Tope velocidad bomba |
| `0x5A` | `intelligent_dosing_rank_ph_output_1` | pH ×100 | 20 | Rango dosificación inteligente |
| `0x5B` | `hysteresis_ph_output_1_on2off` | pH ×100 | 2 | |
| `0x5C` | `hysteresis_ph_output_1_off2on` | pH ×100 | 1 | |
| `0x5D` | `minutes_dosis_ph_output_1` | min | 15 | |
| `0x5E` | `limit_hours_pump_ph_output_1` | h | 100 | Mantenimiento bomba |

### Cloro / ORP / PPM (`0x80`–`0x8F`)

| Reg | Nombre | Unidad | Default | Notas |
|---|---|---|---|---|
| `0x81` | `mV_low_alarm_limit` | mV | 650 | |
| `0x82` | `mV_high_alarm_limit` | mV | 855 | |
| `0x83` | `ppm_low_alarm_limit` | ppm ×100 | 30 (0,30) | |
| `0x84` | `ppm_high_alarm_limit` | ppm ×100 | 350 (3,50) | |
| `0x87` | `setpoint_orp_output_1` | mV | 750 | |
| `0x88` | `setpoint_ppm_output_1` | ppm ×100 | 750 (7,50) | |
| `0x89` | `dosage_time_limit_cl_output_1` | min | 0 | |
| `0x8A` | `max_pct_pump_cl_output_1` | % | 100 | |
| `0x8B` | `intelligent_dosing_range_cl_output_1` | — | 0 | |
| `0x8C` | `hysteresis_cl_output_1_on2off` | — | 2 | |
| `0x8D` | `hysteresis_cl_output_1_off2on` | — | 2 | |
| `0x8F` | `limit_hours_pump_output_cl_1` | h | 100 | |

### Temperatura (`0xB2`–`0xB3`)

| Reg | Nombre | Unidad | Default |
|---|---|---|---|
| `0xB2` | `threshold_low_temperature` | °C ×10 | 150 (15,0) |
| `0xB3` | `threshold_high_temperature` | °C ×10 | 380 (38,0) |

### Sal (`0xC2`–`0xC3`)

| Reg | Nombre | Unidad | Default |
|---|---|---|---|
| `0xC2` | `threshold_low_salt` | g/L ×100 | 300 (3,00) |
| `0xC3` | `threshold_high_salt` | g/L ×100 | 800 (8,00) |

---

## Alarmas (input, bits — escribir `1` al holding equivalente las resetea)

| Input addr | Holding reset | Significado |
|---|---|---|
| `0x200` | `0x200` | Hay alguna alarma activa |
| `0x202` | — | Treatment_halted (parado por calibración) |
| `0x240` | `0x240` | Flow alarm OR (cualquier fuente) |
| `0x241` | `0x241` | Burbuja interna electrólisis |
| `0x242` | `0x242` | Flow switch inductivo abierto |
| `0x250`–`0x252` | `0x25x` | Check cell / low cond / high cond |
| `0x260` | `0x260` | pH bajo |
| `0x261` | `0x261` | pH alto |
| `0x265` | `0x265` | Garrafa pH vacía |
| `0x266` | `0x266` | Pumpstop pH |
| `0x267` | `0x267` | Fusible bomba pH |
| `0x268` | `0x268` | Mantenimiento bomba pH (horas) |
| `0x270`–`0x271` | `0x27x` | ORP bajo/alto |
| `0x272`–`0x273` | `0x27x` | PPM bajo/alto |
| `0x278` | `0x278` | Fusible bomba Cl |
| `0x280`–`0x281` | `0x28x` | Temp baja/alta |
| `0x290`–`0x291` | `0x29x` | Sal baja/alta |
| `0x2A0`–`0x2A1` | `0x2Ax` | Balasto UV / fusible UV |

---

## Programación horaria (holding `0x170`–`0x186`, 10 timeprogs idénticos)

Cada timeprog tiene 4 períodos (start/stop) + 3 bits de configuración +
offsets crepusculares (sunrise/sunset).

| Reg | Nombre |
|---|---|
| `0x170–0x171` | period_0 start/stop |
| `0x172–0x173` | period_1 start/stop |
| `0x174–0x175` | period_2 start/stop |
| `0x176–0x177` | period_3 start/stop |
| `0x178` | crepuscular_conf_bits |
| `0x179` | crepuscular_sunRiseOffset |
| `0x17A` | crepuscular_sunSetOffset |
| `0x17C–0x186` | siguiente timeprog (mismo patrón) |

Patrón se repite hasta 10 timeprogs. Formato horario: `HHMM` (p.ej. 1430 = 14:30).

---

## Salidas relé (holding `0x110`–`0x12E`)

4 salidas configurables (`Output 1`–`Output 4`), cada una con:

- `output_x_1` y `output_x_2` — config base (modo, fuente)
- `enclavamiento_input` — entrada digital de enclavamiento
- `enclavamiento_time_hysteresis` — histéresis tiempo
- `enclavamiento_modo` — `'0' / '1' / 'A' / 'N'` (off/on/auto/no)
- `enclavamiento_setpoint`, `enclavamiento_value_hysteresis`

Telemetría correspondiente en input registers `0x1100`/`0x1120` etc. (bit 0 =
estado on/off, bit 8 = modo enclavamiento).

---

## Notas pendientes de validar al primer pairing

1. Confirmar dirección esclavo real (¿default 2 o cambiada en este SKU?).
2. Confirmar config UART (¿9600 8E1 default?).
3. Leer holding `0x06` para validar bitmap real de capacidades vs lo asumido.
4. Leer `0x09–0x0B` para registrar nº serie del equipo en este repo.
5. Identificar qué outputs (1-4) están cableados y a qué cargas (bomba
   filtración, autollenado, luz, etc.).
