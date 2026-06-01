# 07 · Química del agua — referencias y rangos objetivo

Resumen de los parámetros que vigilaremos en HA y los rangos recomendados,
basado en la comunidad **Trouble Free Pool** (TFP), la referencia anglosajona
para mantenimiento residencial de piscinas con SWG (electrolizador salino).

## Por qué usar TFP como referencia

- Método validado por décadas de discusión técnica abierta.
- Foco en relación **FC/CYA** (cloro libre / ácido cianúrico) que la mayoría
  de manuales de fabricante simplifican demasiado.
- Recomendaciones específicas para piscinas con generador salino (SWG), que es
  exactamente nuestro caso (Idegis Neolysis).

## Rangos objetivo para piscina con SWG + UV

| Parámetro | Rango recomendado | Notas |
|---|---|---|
| **pH** | 7.2 – 7.8 (objetivo 7.4-7.6) | El Idegis lo controla automáticamente (setpoint default 7.20). TFP recomienda apuntar ligeramente arriba (7.4-7.6) para reducir corrosión. |
| **Cloro libre (FC)** | 5 – 10 ppm | Para SWG con CYA 70-80. Nunca bajar de 5 ppm. |
| **Cloro combinado (CC)** | < 0.5 ppm | Por encima de 0.5 ya huele "a cloro" (cloraminas). |
| **CYA (ácido cianúrico)** | 60 – 90 ppm | Cubierta o sin cubierta, SWG quiere CYA alto para que el cloro le dure. **El UV degrada CYA y FC**: vigilar. |
| **TA (alcalinidad total)** | 60 – 80 ppm | TFP recomienda más bajo que los manuales típicos (que dicen 80-120) para reducir tendencia a subida de pH. |
| **CH (dureza cálcica)** | 350 – 550 ppm | Si tienes piscina con liner vinilo es flexible; con gresite/hormigón apuntar a 350+. |
| **Sal (NaCl)** | según el cell — habitualmente 3000-4500 ppm | Nuestro Idegis es **baja salinidad**: rango propio (ver manual, posiblemente 1500-3000 ppm). |
| **Temperatura agua** | — | Nuestra piscina cubierta vive estable ~37 °C. No la controlamos, pero la registramos. |

## Relación FC ↔ CYA (lo más importante)

El cloro "libre" (FC) sin CYA dura horas al sol. Con CYA alto dura días. El
trade-off:

- **CYA bajo (<30)**: el cloro se quema rapidísimo al sol → SWG trabaja a tope
  → cell se gasta antes.
- **CYA alto (60-90)**: cloro estable → SWG trabaja poco → vida cell más larga.
  Pero hay que mantener **FC ≥ CYA/40** para que el cloro siga siendo efectivo
  desinfectante (porque el CYA "secuestra" la mayor parte).

Tabla TFP "Chlorine/CYA chart" en
https://www.troublefreepool.com/threads/chlorine-cya-chart.2177/

Como regla práctica para nosotros con CYA 70-80 y SWG:
- **FC objetivo**: 5-10 ppm (vivimos en 7-8)
- **FC mínimo absoluto**: 5 ppm
- **FC "shock level"** (cuando hay algas/contaminación): 31 ppm para CYA 80

## Implicaciones para nuestra instalación específica

1. **Piscina cubierta a 37 °C**: el agua caliente acelera el consumo de cloro
   y favorece crecimiento bacteriano si FC baja. Mantener el extremo alto del
   rango (FC 8-10) es prudente.
2. **UV activo**: degrada CYA continuamente. Mirar CYA con tira mensualmente y
   reponer cuando baje de 60.
3. **Baja salinidad**: el rango "óptimo de sal" depende del cell. Cuando leamos
   el Modbus, validar contra `threshold_low_salt` y `threshold_high_salt` que
   el equipo tiene programados en holdings `0xC2/0xC3` (defaults 300/800 con
   factor /100 → 3.00–8.00 g/L; **probablemente reprogramados al rango bajo**
   en este equipo, hay que leer al primer pairing).
4. **El Idegis NO mide CYA ni TA ni CH**. Estos siguen siendo manuales con
   tiras/test DPD semanal-mensual. **No hay sensor electrónico real <500 €
   para estos parámetros** (ya descartado en [05-sensors-extra.md](05-sensors-extra.md)).
5. **El Idegis sí mide pH, ORP, sal, temperatura**. Esos son los que van a HA
   vía Modbus.

## Lecturas TFP recomendadas

| Tema | Enlace |
|---|---|
| Relación FC/CYA explicada | https://www.troublefreepool.com/blog/2019/01/18/free-chlorine-and-cyanuric-acid-relationship-explained/ |
| Balance agua para SWG | https://www.troublefreepool.com/blog/2019/01/18/water-balance-for-swgs/ |
| ABC de química de piscina | https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/ |
| CYA (further reading) | https://www.troublefreepool.com/wiki/index.php?title=CYA |
| Chart FC/CYA (foro) | https://www.troublefreepool.com/threads/chlorine-cya-chart.2177/ |
| Método TFP general | https://www.troublefreepool.com/blog/pool-school/ |

## Cómo se traduce esto a Home Assistant

En el dashboard de piscina (futura iteración Fase 4 de
[04-esphome-config.md](04-esphome-config.md)) habrá:

- Gauges con los rangos TFP marcados (verde 5-10 ppm para FC equivalente vía
  ORP, etc.).
- Alarmas: pH<6.8 o >7.8, ORP<600 o >850 mV (proxy de FC fuera de banda),
  Temp>40 °C (anomalía del cerramiento).
- Recordatorio mensual: "comprobar CYA y TA con tira manual".
- Histórico Grafana de pH, ORP, sal, temperatura para detectar tendencias.
