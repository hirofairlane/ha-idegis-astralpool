# 05 · Sensores externos complementarios (<100 € AliExpress)

El Idegis ya mide pH, ORP (si lleva slot), temperatura, salinidad y producción.
Estos sensores externos cubren lo que **no** mide.

## Ranking por relación coste/utilidad

| # | Sensor | Para qué | Precio | Prioridad |
|---|---|---|---|---|
| 1 | Transductor presión 0-5 bar G1/4" + ADS1115 | Filtro sucio, alarma backwash | 10-20 € | ⭐⭐⭐⭐⭐ |
| 2 | DS18B20 impermeable + sonda fuga LM393 | Temp cuadro + inundación | 5 € | ⭐⭐⭐⭐⭐ |
| 3 | JSN-SR04T ultrasónico estanco | Nivel agua vaso/skimmer | 8-10 € | ⭐⭐⭐⭐ |
| 4 | DFRobot Gravity ORP + sonda BNC platino | ORP redundante (cross-check) | 45-60 € | ⭐⭐⭐ |
| 5 | Sonda turbidez Modbus RS485 0-1000 NTU | Detectar problemas filtración | 60-95 € | ⭐⭐ |
| 6 | Sensor cloro libre amperométrico | Cloro real vs ORP | 60-90 € | ⭐ |

## Detalle por sensor

### 1. Presión del filtro (TOP PICK)

Transductor piezorresistivo G1/4", rango 0-5 bar, salida `0.5-4.5 V` ratio-
métrica (preferible) o `4-20 mA`.

- Marcas habituales AliExpress: **Eastsensor**, **Heyuan**, **Anpoiner**, sin marca.
- Conexión: a través de **ADS1115 I²C 16-bit** (~4 €) para leer la salida 0.5-
  4.5 V con buena resolución. El ADC interno del ESP32 es ruidoso y no llega
  bien a la zona alta.
- Si compras versión **4-20 mA**: necesitas un módulo conversor (~5 €) o una
  resistencia shunt de 250 Ω para tener 1-5 V.
- Instalación: T de bronce o PVC roscada G1/4" en la salida del filtro
  (después del manómetro analógico, para mantener el de respaldo).
- **Por qué prioritario**: detectar filtro sucio sin abrir la tapa, programar
  backwash automático cuando ΔP supere umbral, alarma de obstrucción.

### 2. Temperatura cuadro + sonda de fuga

- **DS18B20 impermeable** (one-wire, 2-3 €): pegar al disipador del Neolysis o
  al lateral del cuadro para vigilar sobrecalentamiento.
- **Sonda de fuga con comparador LM393** (2-3 €): cinta o varillas en el suelo
  del cuarto de máquinas. Salida digital a GPIO del ESP32.
- Total: 5 € por dos sensores muy útiles.

### 3. Nivel de agua (JSN-SR04T)

Ultrasónico estanco con sonda externa de 2-3 m de cable.

- Montaje: tapa del skimmer o vaso de compensación, apuntando hacia abajo.
- Pinout: VCC 5V (precaución de logic level — usar divisor en echo a 3.3V),
  GND, TRIG, ECHO.
- Aplicación: alarma de bajo nivel + autollenado con electroválvula latch.
- Alternativa más cara: sonda hidrostática sumergible 4-20 mA (25-45 €) si
  quieres precisión absoluta en cm.

### 4. ORP redundante (validar la sonda del Idegis)

Solo si el SKU lleva slot ORP montado.

- **DFRobot Gravity ORP** módulo analógico + sonda BNC platino: ~50 € total.
- Calibración con patrón 220 mV (40-50 €/200 ml) o 468 mV.
- Vida sonda 1-2 años, hay que cuidar la humedad de almacenamiento.
- Aplicación: detectar deriva de la sonda original (si ambas miden 100 mV
  diferentes durante días → calibrar).

### 5. Turbidez

- **Analógica DFRobot SEN0189** (8-15 €): solo cualitativa, sensible a burbujas
  y bioincrustación. Vale como "agua turbia: sí/no".
- **Sonda Modbus RS485 0-1000 NTU calibrada** (60-95 €): mucho más fiable.
  Comparte bus con el Idegis (otra slave address) o segundo UART del ESP32.

### 6. Cloro libre amperométrico

Existe pero **mantenimiento alto**: calibración mensual con DPD, vida útil
6-12 meses, deriva con cloraminas. Solo si te interesa la disciplina química.
**Mi recomendación: postergar.** Con pH+ORP+sal del Idegis tienes el control de
desinfección; un test DPD manual semanal cubre el resto.

## Descartar

- **TDS genérico Gravity** (10 €): satura con agua salada de piscina, inútil.
  El Idegis ya da salinidad.
- **Multiparámetro chino "6 en 1" 40 €**: refrito sin calibración real.
- **Ácido cianúrico digital**: no existe sensor electroquímico real <500 €. Usa
  tiras o test DPD.
- **Dureza cálcica / alcalinidad electrónica**: requieren titulación química,
  no hay equivalente electrónico viable.
- **Cloro colorimétrico DPD reutilizable barato**: no son sensores reales.

## BOM sugerida inicial (fase de arranque)

| Ítem | Coste estimado |
|---|---|
| ESP32 DevKit-C v4 | 7 € |
| Caja IP65 + prensaestopas | 8 € |
| Conversor RS485 auto-direction | 3 € |
| Transductor presión 0-5 bar | 12 € |
| ADS1115 I²C | 4 € |
| DS18B20 impermeable | 3 € |
| Sonda fuga LM393 | 2 € |
| JSN-SR04T | 8 € |
| Fuente 5V dedicada cuadro | 10 € |
| Cables, conectores, prensaestopas extra | 10 € |
| **Total** | **~67 €** |
