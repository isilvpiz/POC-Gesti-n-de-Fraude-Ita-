# Steering Agente 1 — Procesamiento de Correos de Fraude

## Propósito

El Agente 1 automatiza la recepción documental de reclamos de fraude. Simula el proceso que en producción leería desde la casilla de correo de Itaú (Microsoft Graph API) y escribiría al Front de Fraudes. En desarrollo local, lee desde un directorio y escribe a un Excel.

## Flujo del agente

```
1. Escanear directorio input/emails/ en busca de archivos .eml
2. Por cada .eml:
   a. Parsear el correo (asunto, remitente, fecha, cuerpo)
   b. Extraer PDF adjunto
   c. Leer texto del PDF
   d. Enviar texto a Bedrock (Claude Haiku) para extracción estructurada
   e. Validar campos extraídos
   f. Escribir registro en output/casos.xlsx
   g. Mover .eml procesado a input/emails/procesados/
3. Generar resumen de procesamiento en log
```

## Campos a extraer del PDF (via Bedrock)

Bedrock debe extraer los siguientes campos del documento de reclamo:

| Campo | Descripción | Requerido |
|---|---|---|
| `rut_cliente` | RUT del cliente reclamante | Sí |
| `nombre_cliente` | Nombre completo del cliente | Sí |
| `numero_tarjeta` | Últimos 4 dígitos de la tarjeta | Sí |
| `monto_reclamado` | Monto numérico | Sí |
| `moneda` | Moneda del monto (CLP, USD) | Sí |
| `fecha_transaccion` | Fecha de la transacción disputada | Sí |
| `fecha_reclamo` | Fecha en que el cliente presenta el reclamo | Sí |
| `nombre_comercio` | Nombre del comercio involucrado | Sí |
| `canal_venta` | Presencial / No presencial | Sí |
| `tiene_3ds` | Si el comercio tiene autenticación 3DS (Sí/No) | Sí |
| `tipo_fraude` | Tipo de fraude reportado | Sí |
| `descripcion_reclamo` | Descripción libre del reclamo | No |
| `numero_operacion` | Número de operación bancaria | No |

## Prompt para Bedrock

El prompt debe instruir a Claude Haiku a extraer los campos en formato JSON estructurado. Ejemplo de estructura esperada:

```json
{
  "rut_cliente": "12.345.678-9",
  "nombre_cliente": "Juan Pérez González",
  "numero_tarjeta": "4521",
  "monto_reclamado": 150000,
  "moneda": "CLP",
  "fecha_transaccion": "2026-05-15",
  "fecha_reclamo": "2026-05-22",
  "nombre_comercio": "Ripley S.A.",
  "canal_venta": "No presencial",
  "tiene_3ds": "No",
  "tipo_fraude": "Compra no reconocida",
  "descripcion_reclamo": "No reconozco esta compra...",
  "numero_operacion": "OP-2026-789456"
}
```

## Output Excel (output/casos.xlsx)

Columnas del archivo de salida:

| Columna | Descripción |
|---|---|
| `id_caso` | ID único generado (UUID) |
| `fecha_procesamiento` | Timestamp de procesamiento |
| `archivo_origen` | Nombre del .eml procesado |
| `rut_cliente` | RUT extraído |
| `nombre_cliente` | Nombre extraído |
| `numero_tarjeta` | Últimos 4 dígitos |
| `monto_reclamado` | Monto en CLP |
| `fecha_transaccion` | Fecha transacción disputada |
| `nombre_comercio` | Comercio involucrado |
| `tiene_3ds` | Sí / No |
| `tipo_fraude` | Tipo de fraude |
| `descripcion_reclamo` | Descripción libre |
| `numero_operacion` | Número de operación |
| `estado` | PROCESADO / PENDIENTE_REVISION / ERROR |
| `notas` | Observaciones del procesamiento |

## Reglas de validación

- Si `rut_cliente` está vacío → estado = `PENDIENTE_REVISION`
- Si `monto_reclamado` no es numérico → estado = `PENDIENTE_REVISION`
- Si `tiene_3ds` no es Sí/No → normalizar con Bedrock
- Si Bedrock no puede extraer más de 3 campos requeridos → estado = `ERROR`

## Consideraciones de desarrollo local

- En producción este módulo reemplazará la lectura del directorio por Microsoft Graph API
- La escritura al Excel reemplazará la llamada a la API del Front de Fraudes
- El código debe estar estructurado para facilitar ese reemplazo (patrón adaptador)
