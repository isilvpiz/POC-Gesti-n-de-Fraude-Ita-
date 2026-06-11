# Steering General — POC Gestión de Fraude Itaú

## Contexto del proyecto

Este proyecto es un POC (Proof of Concept) de dos agentes de IA para automatizar la gestión de reclamos de fraude bancario para Itaú Chile. El desarrollo es **local** — sin conexión a sistemas productivos de Itaú. Los servicios AWS (S3, Front de Fraudes) se simulan con directorios locales y archivos Excel.

## Reglas generales

- Todo el código debe estar en **Python 3.11+**
- Usar **type hints** en todas las funciones
- Documentar cada función con **docstrings** en español
- Manejar **todas las excepciones** explícitamente — nunca usar `except: pass`
- Usar **logging** en lugar de `print()` para toda salida de consola
- Las rutas de archivos deben leerse desde **variables de entorno** — nunca hardcodeadas
- Cada módulo debe tener su propio **logger** nombrado con el nombre del módulo

## Convenciones de código

- Nombres de variables y funciones: **snake_case** en español (ej: `leer_correo`, `extraer_datos`)
- Nombres de clases: **PascalCase** en español (ej: `LectorCorreo`, `EvaluadorRegla3DS`)
- Constantes: **UPPER_SNAKE_CASE** (ej: `MODELO_BEDROCK`, `DIRECTORIO_INPUT`)
- Archivos de módulo: **snake_case** descriptivo (ej: `email_reader.py`, `regla_3ds.py`)

## Estructura de outputs

- Todos los outputs van a `/output/`
- Los archivos Excel deben tener encabezados claros en español
- Cada registro debe incluir: `id_caso`, `fecha_procesamiento`, `estado`
- Los logs deben guardarse en `/output/logs/`

## Manejo de errores

- Si un correo no puede procesarse → registrar en log y continuar con el siguiente
- Si Bedrock no responde → reintentar 3 veces con backoff exponencial
- Si un campo requerido no se extrae → marcar como `PENDIENTE_REVISION` en el Excel

## Testing

- Cada módulo principal debe tener su test unitario en `/tests/`
- Usar `pytest` como framework de testing
- Los tests deben poder ejecutarse sin conexión a AWS (usar mocks)

## Protección de datos personales (PII) — OBLIGATORIO

- NUNCA escribir en logs: nombre completo del cliente, RUT sin enmascarar, contenido completo del PDF
- RUT en logs siempre enmascarado: `12.***.**8-9` (usar agente1/pii.py)
- Número de tarjeta: SOLO últimos 4 dígitos en cualquier almacenamiento (PCI-DSS)
- Los archivos Excel de output son datos sensibles — están en .gitignore y no se versionan

## Bedrock — convenciones obligatorias

- Usar SIEMPRE la Converse API (`client.converse`), nunca `invoke_model`
- Model ID desde variable de entorno BEDROCK_MODEL_ID
- Retries con configuración nativa de boto3: `Config(retries={'max_attempts': 3, 'mode': 'adaptive'})`
- Autenticación con AWS_PROFILE — nunca access keys hardcodeadas
