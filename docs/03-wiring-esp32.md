# 03 · Cableado ESP32 ↔ Idegis (RS485)

## Topología

```
┌─────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│ Idegis      │      │ Conversor TTL ↔ RS485 │      │ ESP32                │
│ Neolysis    │ A,B  │ (MAX485 / SP3485 /   │ TX,RX│                      │
│ Modbus RTU  │◄────►│ auto-direction)      │◄────►│ UART2 GPIO16/17      │
│ slave addr=2│      │ Vcc/GND 3.3 V o 5 V  │      │ 3.3 V                │
└─────────────┘      └──────────────────────┘      └──────────────────────┘
                                                            │ WiFi
                                                            ▼
                                                     ┌──────────────┐
                                                     │ Home Assistant│
                                                     │ ESPHome API  │
                                                     └──────────────┘
```

## Adaptador RS485

**Pendiente confirmar el modelo concreto comprado por Sergio.** Opciones:

### A) Kit oficial Idegis C-MOD

Módulo enchufable directamente en el conector Modbus interno del equipo, expone
A/B/GND por bornes. Caro pero plug-and-play, no requiere intervención en el
cableado interno del Neolysis.

### B) Conversor RS485 genérico (3 €)

Los típicos módulos de eBay/AliExpress:

- **MAX485 con DE/RE manual** — requiere un GPIO extra del ESP32 para
  conmutar dirección (DE=RE conectados juntos, salida del ESP). ESPHome lo
  soporta vía `flow_control_pin`.
- **MAX3485 / SP3485 a 3.3 V** — mejor para ESP32 sin level-shifter.
- **Módulos "auto-direction" tipo XY-017 / XY-K485** — no requieren GPIO de
  control; recomendado para empezar simple. Algunos modelos requieren 5 V Vcc.

Para Sergio que arranca, **mi recomendación: módulo auto-direction 5V** con
USB-C powered ESP32 que dé 5 V por el VIN.

## Pinout ESP32 (DevKit-C v4)

| Función | GPIO ESP32 | Pin del conversor RS485 |
|---|---|---|
| UART2 TX | GPIO17 | TXD / DI |
| UART2 RX | GPIO16 | RXD / RO |
| RS485 DE/RE (si manual) | GPIO4 | DE+RE |
| GND | GND | GND |
| 3.3 V o 5 V | 3V3 / VIN | VCC |

Lado Modbus del conversor:

| Pin conversor | Pin Idegis |
|---|---|
| A (D+) | A (Modbus +) |
| B (D-) | B (Modbus -) |
| GND | GND Modbus (común) |

## Terminación y polarización

- **Terminación** 120 Ω en los **dos extremos** del bus si el cable es largo
  (>5 m). En instalaciones cortas (ESP junto al cuadro de máquinas) muchas veces
  se omite y funciona. La mayoría de módulos chinos llevan un jumper o
  resistencia ya soldada — comprobar antes de añadir otra.
- **Polarización (fail-safe)**: si el bus queda en alta impedancia al no
  transmitir nadie, pueden aparecer datos basura. Algunos módulos llevan
  resistencias de pull-up/pull-down (típicamente 680 Ω). Si Sergio ve
  desincronizaciones, esto suele ser la causa.

## Alimentación del ESP32

Tres opciones por orden de preferencia:

1. **Fuente 5 V dedicada en el cuadro de piscina** (cargador USB de 1 A
   industrial). Aislado de la electrónica del Neolysis.
2. **Toma 5 V del propio Idegis** si la placa lo proporciona y está dimensionada
   — *consultar manual antes de tirar de aquí*.
3. **PoE splitter** si el cuadro tiene cable de red — más estable a largo plazo.

## Consideraciones de seguridad eléctrica

- El cuadro de piscina lleva 230 VAC y electrónica de potencia (electrólisis con
  corrientes >10 A). Mantener el ESP32 + conversor en **caja IP65** separada
  físicamente de las líneas de potencia. Evitar bucles de masa cableando el GND
  Modbus en estrella desde el Idegis.
- No alimentar el ESP32 desde la línea de 230 V con módulos baratos sin
  aislamiento galvánico (los Hi-Link HLK-PM01 son aceptables pero no
  certificados para piscina).
- Idealmente, ESP32 + conversor en una caja con prensaestopas y conectado a
  Wi-Fi por antena externa si la caja es metálica.

## Adaptador para sensores extra (opcional)

Si más adelante Sergio añade:
- Transductor presión 0-5 bar 0.5-4.5 V → ADS1115 I²C (GPIO21 SDA, GPIO22 SCL)
- DS18B20 ambient → GPIO5 (one-wire con pull-up 4.7 kΩ)
- Sonda fuga → GPIO13 digital input
- Ultrasónico JSN-SR04T → GPIO18 trig, GPIO19 echo

Reservar estos GPIO desde ya en la config ESPHome para no tener que rehacer
después.
