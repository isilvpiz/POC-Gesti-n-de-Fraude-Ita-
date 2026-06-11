# Requirements — Agente 1: Procesamiento de Correos de Fraude

## Introducción

El Agente 1 automatiza la recepción documental de reclamos de fraude que llegan por correo electrónico con formulario PDF adjunto. En desarrollo local lee desde directorio y escribe a Excel; en producción leerá desde Microsoft Graph API y escribirá al Front de Fraudes.

## Requisitos (notación EARS)

### R1 — Escaneo de correos

**User Story:** Como analista de fraudes, quiero que el sistema procese automáticamente los correos de reclamo, para no ingresar datos manualmente.

#### Acceptance Criteria
1. WHEN el agente se ejecuta, THE SYSTEM SHALL escanear el directorio `input/emails/` en busca de archivos `.eml`
2. WHEN un archivo `.eml` es encontrado, THE SYSTEM SHALL parsear asunto, remitente, fecha y cuerpo
3. WHEN un `.eml` contiene un adjunto PDF, THE SYSTEM SHALL extraerlo a `input/pdfs/`
4. IF un `.eml` no contiene adjunto PDF, THEN THE SYSTEM SHALL registrar el caso con estado `ERROR` y motivo "sin adjunto"
5. WHEN un `.eml` es procesado exitosamente, THE SYSTEM SHALL moverlo a `input/emails/procesados/`

### R2 — Deduplicación

**User Story:** Como analista, quiero que reclamos duplicados no generen casos duplicados, para evitar doble gestión.

#### Acceptance Criteria
1. WHEN un correo es procesado, THE SYSTEM SHALL calcular un hash de deduplicación con: `rut_cliente + numero_operacion + monto_reclamado`
2. IF el hash ya existe en `output/casos.xlsx`, THEN THE SYSTEM SHALL marcar el registro nuevo con estado `DUPLICADO` y referenciar el `id_caso` original
3. WHEN un caso es marcado `DUPLICADO`, THE SYSTEM SHALL NO enviarlo al flujo del Agente 2

### R3 — Extracción con Bedrock

**User Story:** Como analista, quiero que la IA extraiga los datos del formulario PDF, para eliminar la transcripción manual.

#### Acceptance Criteria
1. WHEN el texto del PDF es extraído, THE SYSTEM SHALL enviarlo a Amazon Bedrock vía **Converse API** usando el modelo definido en `BEDROCK_MODEL_ID`
2. THE SYSTEM SHALL solicitar a Bedrock los 13 campos definidos en el steering del Agente 1 en formato JSON
3. IF un campo requerido no puede extraerse, THEN THE SYSTEM SHALL asignar el valor `PENDIENTE_REVISION` a ese campo
4. IF Bedrock falla, THEN THE SYSTEM SHALL reintentar usando la configuración nativa de boto3 (`Config(retries={'max_attempts': 3, 'mode': 'adaptive'})`)
5. IF más de 3 campos requeridos resultan `PENDIENTE_REVISION`, THEN THE SYSTEM SHALL marcar el caso completo con estado `ERROR`

### R4 — Protección de datos personales (PII)

**User Story:** Como oficial de cumplimiento, necesito que los datos personales estén protegidos, para cumplir PCI-DSS y normativa de datos.

#### Acceptance Criteria
1. THE SYSTEM SHALL almacenar solo los últimos 4 dígitos del número de tarjeta
2. WHEN se escriba a logs, THE SYSTEM SHALL enmascarar el RUT (ej: `12.***.**8-9`) y omitir nombres completos
3. THE SYSTEM SHALL NO incluir el contenido completo del PDF en ningún log

### R5 — Escritura de casos

#### Acceptance Criteria
1. WHEN los datos son validados, THE SYSTEM SHALL escribir un registro en `output/casos.xlsx` con `id_caso` (UUID), `fecha_procesamiento` (timestamp ISO) y los 13 campos
2. IF `output/casos.xlsx` no existe, THEN THE SYSTEM SHALL crearlo con los encabezados definidos en el steering
3. WHEN el procesamiento finaliza, THE SYSTEM SHALL registrar en log un resumen: total procesados, errores, pendientes, duplicados
