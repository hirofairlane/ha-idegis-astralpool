# 04 · Configuración ESPHome y entidades HA

## Por qué ESPHome y no `modbus:` YAML nativo de HA

- **Aislamiento eléctrico**: el ESP32 está físicamente junto al equipo, HA en
  otro sitio. Si HA reinicia, el ESP sigue muestreando.
- **Reconexión y healing**: ESPHome reintenta y reconcilia el bus solo.
- **Latencia local**: las automatizaciones críticas (parar bomba si no hay
  flujo) pueden vivir en el propio ESP, sin pasar por HA.
- **Despliegue OTA**: cambios sin tocar config de HA.
- **Reutilización**: el YAML resultante es directamente publicable como
  proyecto público (objetivo del repo).

## Estrategia de mapeo

Cada zona del Excel (input/holding) → un bloque `modbus_controller` con
`sensor`/`binary_sensor`/`number`/`switch`/`select`/`text_sensor` de ESPHome,
agrupados por zona.

Para minimizar tráfico Modbus se usa:
- `update_interval: 10s` para medidas instantáneas (pH, ORP, temp, sal).
- `update_interval: 60s` para acumulados (g_today, horas, alarmas).
- `update_interval: 600s` o `never` con `lambda` para campos estáticos (HW/FW
  version, serie).
- `force_new_range: true` cuando un registro debe ir en su propia trama
  (cambio de zona, evitar leer huecos).

## Entidades HA derivadas (primera entrega)

### Sensores numéricos (lectura)

| Entidad HA | Source | Unidad | Notas |
|---|---|---|---|
| `sensor.piscina_ph` | input 0x51 /10 | pH | precisión 0.01 |
| `sensor.piscina_orp` | input 0x81 | mV | |
| `sensor.piscina_temperatura` | input 0xB1 /10 | °C | |
| `sensor.piscina_salinidad` | input 0xC1 /100 | g/L | |
| `sensor.piscina_produccion_pct` | input 0x42 | % | actual |
| `sensor.piscina_produccion_pct_target` | input 0x41 | % | setpoint en curso |
| `sensor.piscina_corriente_electrodos` | input 0x43 /100 | A | |
| `sensor.piscina_tension_electrodos` | input 0x44 /100 | V | |
| `sensor.piscina_produccion_g_h` | input 0x45 | g/h | |
| `sensor.piscina_produccion_g_today` | input 0x46 | g | acumulado día |
| `sensor.piscina_minutos_electrolisis_today` | input 0x47 | min | |
| `sensor.piscina_horas_totales_electrolisis` | input 0x48+0x49 uint32 | h | |
| `sensor.piscina_horas_totales_bomba_ph` | input 0x5A | h | |
| `sensor.piscina_bomba_ph_pct` | input 0x58 | % | |
| `sensor.piscina_bomba_ph_dosis_sec_hoy` | input 0x59 | s | |

### Binary sensors (alarmas)

| Entidad HA | Source bit |
|---|---|
| `binary_sensor.piscina_alarma_global` | 0x200 |
| `binary_sensor.piscina_tratamiento_parado` | 0x202 |
| `binary_sensor.piscina_flow_alarm` | 0x240 |
| `binary_sensor.piscina_burbuja_celda` | 0x241 |
| `binary_sensor.piscina_flow_switch` | 0x242 |
| `binary_sensor.piscina_ph_bajo` | 0x260 |
| `binary_sensor.piscina_ph_alto` | 0x261 |
| `binary_sensor.piscina_garrafa_ph_vacia` | 0x265 |
| `binary_sensor.piscina_pumpstop_ph` | 0x266 |
| `binary_sensor.piscina_fusible_ph` | 0x267 |
| `binary_sensor.piscina_orp_bajo` | 0x270 |
| `binary_sensor.piscina_orp_alto` | 0x271 |
| `binary_sensor.piscina_temp_baja` | 0x280 |
| `binary_sensor.piscina_temp_alta` | 0x281 |
| `binary_sensor.piscina_sal_baja` | 0x290 |
| `binary_sensor.piscina_sal_alta` | 0x291 |
| `binary_sensor.piscina_electrolisis_running` | 0x400 |
| `binary_sensor.piscina_polaridad` | 0x401 |
| `binary_sensor.piscina_cubierta_puesta` | 0x402 |
| `binary_sensor.piscina_aplicando_setpoint_cover` | 0x403 |
| `binary_sensor.piscina_dosificando_ph` | 0x560 |

### Números editables (escritura por Modbus)

| Entidad HA | Holding | Rango | Unidad |
|---|---|---|---|
| `number.piscina_setpoint_ph` | 0x57 | 6.50–8.00 | pH (×100 en wire) |
| `number.piscina_setpoint_orp` | 0x87 | 600–900 | mV |
| `number.piscina_setpoint_produccion_normal` | 0x41 | 0–100 | % |
| `number.piscina_setpoint_produccion_cover` | 0x42 | 0–100 | % |
| `number.piscina_limite_g_dia` | 0x43 | 0–500 | g (0 = sin límite) |
| `number.piscina_dosage_time_limit_ph` | 0x58 | 0–120 | min |
| `number.piscina_max_pct_pump_ph` | 0x59 | 0–100 | % |
| `number.piscina_threshold_temp_baja` | 0xB2 | 0–25 | °C (×10) |
| `number.piscina_threshold_temp_alta` | 0xB3 | 25–45 | °C (×10) |
| `number.piscina_threshold_sal_baja` | 0xC2 | 1.0–4.0 | g/L (×100) |
| `number.piscina_threshold_sal_alta` | 0xC3 | 4.0–10.0 | g/L (×100) |

### Switches y botones (acciones)

| Entidad HA | Acción |
|---|---|
| `button.piscina_reset_alarma_global` | escribir 0x200 holding a 1 |
| `button.piscina_reset_alarmas_flow` | escribir 0x240 holding a 1 |
| `button.piscina_reset_alarmas_ph` | escribir 0x26x holding |
| `button.piscina_reset_horas_parciales_electrolisis` | escribir reset 0x4C |

### Diagnóstico (categoría diagnostic en HA)

- `text_sensor.piscina_serial` (lectura `0x09–0x0B` formateado hex)
- `text_sensor.piscina_fw_version` (`0x08`)
- `text_sensor.piscina_hw_version` (`0x07`)
- Capacidades como `binary_sensor` de categoría diagnostic con el bitmap `0x06`.

## Iteración por fases

**Fase 1 — solo lectura (sin riesgo).**
Implementar todos los `sensor` y `binary_sensor`. Validar contra el panel
físico del Idegis durante 1-2 semanas. Si los valores cuadran, pasar a Fase 2.

**Fase 2 — escritura de setpoints "seguros".**
Habilitar `number` para pH setpoint, ORP setpoint, % producción normal/cover,
umbrales de alarma. Usar contraseña Modbus si aplica (algunos holdings la
piden — registro `0x22` `calibration_value` actúa como token contextual).

**Fase 3 — control de programaciones y salidas.**
Time programs (`0x170+`), salidas relé (`0x110+`), VS pump y selectora.
Requiere más trabajo de modelado y testing.

**Fase 4 — automatizaciones HA.**
- Alerta push si pH fuera de banda más de N minutos.
- Reducción producción en horario nocturno (timeprog desde HA).
- Switch a modo cover cuando lovelace pulse "cubierta puesta".
- Notificación "rellenar garrafa pH" cuando bit 0x265 active.
- Histórico InfluxDB / Grafana de g/h vs temperatura.

## Riesgos conocidos

- **Funciones 0x01/0x05/0x15 prohibidas** — comportamiento indefinido. ESPHome
  por defecto usa 0x03/0x06/0x10 para holdings, OK.
- **Algunos holdings requieren contraseña** (`With Pass` en el Excel). Hay que
  averiguar el mecanismo de pass — probablemente escribir un valor concreto en
  `0x22` antes de escribir el registro protegido. Pendiente de validar.
- **Cambiar `ID_Address` o `COM_Setup` puede dejar el bus mudo**. Tratar estos
  registros como diagnóstico solo, no exponer como `number` editables.
- **Watchdog Modbus**: si `0x10` `Watchdog_time` está configurado y el ESP32 se
  cae, el equipo puede entrar en modo seguro. Decidir si activarlo y a qué
  valor.

## Referencias

- ESPHome `modbus_controller`: https://esphome.io/components/modbus_controller.html
- ESPHome `uart` (Hardware UART recomendado): https://esphome.io/components/uart.html
