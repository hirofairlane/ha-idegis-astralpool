# 08 · Descubrimiento de la API Cloud Idegis (HTTP plano)

Resultado de la ventana de diagnóstico activa del **2026-06-02 00:08-00:12**
durante la cual la depuradora estaba en marcha y el Idegis con la electrónica
alimentada.

## Hallazgos críticos

### 1. El Idegis NO expone NINGÚN puerto entrante por LAN

Confirmado con dos escaneos nmap independientes (top-1000 en 101 s y los 65535
puertos en 131 s) durante ventana activa:

- ICMP responde (host UP)
- **0 puertos TCP abiertos**
- Modbus TCP (502) cerrado/timeout
- HTTP (80, 8080, 443, 8443) cerrado
- Cualquier puerto: cerrado

**Consecuencia**: integración Modbus TCP **descartada**. El Idegis es
**únicamente cliente**, no servidor.

### 2. El Idegis hace polling HTTP plano a `api.idegis.net`

Capturado por **conntrack del router Principal** y confirmado por **dnsmasq
query log**:

- **Dominio**: `api.idegis.net`
- **Puerto**: 80 (HTTP, **sin TLS**)
- **CDN**: Imperva/Incapsula (IP anycast 45.60.153.189, AS19551)
- **DNS resolver usado**: 9.9.9.9 (Quad9) — el equipo ignora el DNS local; va a un upstream público fijo
- **Frecuencia**: 1 request cada 3-4 segundos (write.php intercalado con read.php)

### 3. Estructura del protocolo

Endpoints observados:

| Endpoint | Función inferida |
|---|---|
| `GET /interface/write.php` | El Idegis **envía** telemetría/estado al cloud |
| `GET /interface/read.php` | El Idegis **pregunta** al cloud si hay órdenes pendientes |

Ambos llevan dos parámetros query string:

```
?B0=<payload codificado alfanumérico>&H=<hash MD5 32 hex>
```

#### Ejemplo capturado

```
GET /interface/write.php?B0=JS4fUX2d24UWcVbXJYfYfd4fU0W430TD4fUX2d24cbabWbcaXXaba4fU0W430CI4fUX2d24a4fU0W430LI4fUX2d24aacad4fU0W430CD4fUX2d24bVWadfbWaa4fU0W430SG4fUX2d24aVgfW&H=C651B84CA98BD763E88A7CFD6DE86EC6 HTTP/1.1
```

User-Agent: vacío (`"-"`).

#### Análisis preliminar del payload `B0`

- Caracteres: alfanumérico (`0-9 A-Z a-z`)
- **Separador candidato**: la secuencia `4fU0W430` aparece repetida varias
  veces actuando como delimitador entre campos.
- Tokens entre separadores parecen **identificadores de campo**:
  - `TD` → temperature data?
  - `CI` → current?
  - `LI` → limit?
  - `CD` → code/status?
  - `SG` → setpoint generic?
- Y otra subdivisión interna con el patrón `4fU0W430<FIELD>4fUX2d24<VALUE>`.
- Hay un prefijo `JS4fUX2d24UWcVbXJYfYfd` que probablemente codifique
  identidad del equipo + token de sesión.

Hipótesis a validar:
1. El payload es una codificación reversible (no cifrado fuerte), tipo
   sustitución alfabética o base32 modificado, sobre un formato key-value.
2. `H` es **MD5(B0 + shared_secret)** o **MD5(B0 + serial_equipo + timestamp_truncado)**.
3. Si la hipótesis se confirma, podemos generar requests válidos y simular
   tanto telemetría como respuestas del cloud.

### 4. Capacidad de MITM verificada

Durante 60 s se aplicó un DNS override en el router Principal
(`api.idegis.net → 192.168.1.70` = CT104) y el Idegis envió correctamente sus
requests a CT104:80, donde nginx existente respondió 404 (5 conexiones
TIME_WAIT confirmadas en `ss`). El equipo siguió funcionando aunque las
respuestas eran erróneas — es **resiliente a fallos transitorios** y reintenta.

Esto demuestra que es viable:
- Montar un **proxy reverso permanente** en CT104 que intercepte, decodifique
  y reenvíe al cloud original.
- Exponer cada métrica del payload como sensor HA.
- Inyectar respuestas modificadas en `read.php` para enviar órdenes al equipo
  sin pasar por el cloud Idegis (control bidireccional cloud-emulado).

## Nuevo plan de arquitectura — 3 vías complementarias

| Vía | Propósito | Estado | Coste |
|---|---|---|---|
| **A) Cloud-MITM proxy** (nuevo, vía descubierta) | Telemetría push del equipo cada 3-4 s, sin tocar el Idegis | Por desarrollar | ~0 € (solo software en CT104) |
| **B) Modbus RTU + ESP32** (plan original) | Control local total, lectura síncrona, no depende de internet | Por desarrollar | ~30 € hardware |
| **C) Cloud PoolStation** (`cibernox/homeassistant-poolstation`) | Backup, validación cruzada | Listo, plug-and-play | 0 € |

**Recomendación revisada**: empezar por la vía **A**. Es la que más rápido
da resultado (sin esperar componentes), no requiere intervención física, y
nos da telemetría inmediata. La vía B (RTU) sigue siendo deseable para
control offline y desconectar del cloud, pero ya no es urgente.

## Siguiente fase técnica (vía A)

1. **Decodificar `B0`** completo a partir de muestras múltiples capturadas en
   nginx access log. Buscar invariantes (prefijo de identidad) y patrón de
   incremento (timestamps/contadores).
2. **Verificar la fórmula del hash H**: probar `MD5(B0)`, `MD5(B0+H)` no
   aplica obviamente, `MD5(B0+serial)`, etc.
3. **Implementar proxy reverso transparente** en CT104:
   - Escuchar :80 en una IP nueva (puerto 80 ya está ocupado por nginx
     general) o reorganizar nginx para hacer reverse-proxy con location
     `/interface/`.
   - Reenviar a `api.idegis.net` real con DNS resuelto manualmente
     (evitando el bucle del propio override).
   - Loguear cada request/response.
   - Publicar las métricas decodificadas a MQTT (mosquitto disponible en
     CT104).
4. **HA**: consumir MQTT → entidades sensor.

## Riesgo: ¿se entera Imperva del MITM?

El equipo Idegis no usa TLS, no usa certificate pinning. El MITM via DNS
override es **invisible para el Idegis y para Imperva** (el reenvío al cloud
real va por el mismo path TCP de siempre). Solo se vería como una latencia
extra de 1-2 ms.

## Log de captura

```
/opt/piscina/captures/idegis-cloud-protocol-<TIMESTAMP>.log
```

Contiene la copia completa del nginx access.log durante la ventana de DNS
override (5 requests del Idegis, todas con respuesta 404 de nginx por defecto).

## TODOs derivados

- [ ] Capturar 100+ requests del Idegis (otra ventana, este vez con un
      listener custom que responde 200 OK vacío para no romper el polling).
- [ ] Decodificar empíricamente `B0`.
- [ ] Validar fórmula `H`.
- [ ] Decidir si reescribir nginx para proxy reverso o crear un container/IP
      dedicada para el listener Idegis.
- [ ] Una vez funcionando: borrar la vía cloud PoolStation (vía C) por
      redundante, o mantenerla como backup.
- [ ] Considerar **bloquear DNS de `api.idegis.net` en el router** una vez el
      proxy esté operativo, para que el equipo no llegue NUNCA al cloud real
      y todo viva 100% local.
