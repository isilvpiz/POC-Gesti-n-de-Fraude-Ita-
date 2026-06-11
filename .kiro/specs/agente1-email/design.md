# Design — Agente 1: Procesamiento de Correos de Fraude

## Módulos

### `agente1/email_reader.py`
```
Clase: LectorCorreo
  - escanear_directorio(directorio: str) → list[Path]
  - parsear_correo(ruta: Path) → DatosCorreo
  - extraer_adjunto_pdf(correo: DatosCorreo) → Path | None
  - mover_procesado(ruta: Path) → None

DataClass DatosCorreo: asunto, remitente, fecha, cuerpo, ruta_pdf
```

### `agente1/pdf_extractor.py`
```
Clase: ExtractorPDF
  - leer_texto(ruta_pdf: Path) → str
  - limpiar_texto(texto: str) → str
```

### `agente1/bedrock_client.py`
```
Clase: ClienteBedrock
  - __init__: usa boto3 con Config(retries={'max_attempts': 3, 'mode': 'adaptive'})
  - extraer_datos_reclamo(texto_pdf: str) → DatosReclamo
  - _construir_mensajes(texto: str) → list   # formato Converse API
  - _parsear_respuesta(respuesta: dict) → DatosReclamo

IMPORTANTE: usar bedrock-runtime **Converse API** (client.converse), NO invoke_model.
Modelo: variable BEDROCK_MODEL_ID = us.anthropic.claude-3-5-haiku-20241022-v1:0

DataClass DatosReclamo (13 campos):
  rut_cliente, nombre_cliente, numero_tarjeta (últimos 4),
  monto_reclamado, moneda, fecha_transaccion, fecha_reclamo,
  nombre_comercio, canal_venta ("Presencial"|"No presencial"),
  tiene_3ds ("Sí"|"No"), tipo_fraude, descripcion_reclamo, numero_operacion
```

### `agente1/dedup.py`
```
Clase: Deduplicador
  - calcular_hash(datos: DatosReclamo) → str   # sha256(rut+num_operacion+monto)
  - existe_en_excel(hash: str, ruta_excel: Path) → str | None  # retorna id_caso original
```

### `agente1/pii.py`
```
Funciones de enmascaramiento para logging:
  - enmascarar_rut("12.345.678-9") → "12.***.**8-9"
  - El logger NUNCA recibe nombre_cliente ni texto completo del PDF
```

### `agente1/excel_writer.py`
```
Clase: EscritorCasos
  - inicializar_excel(ruta) / escribir_caso(datos, correo, hash_dedup) → id_caso (UUID)
Columnas: id_caso, fecha_procesamiento, archivo_origen, hash_dedup,
  + los 13 campos de DatosReclamo + estado + id_caso_original (si DUPLICADO) + notas
```

### `agente1/main.py`
Orquesta: escanear → parsear → extraer PDF → Bedrock → dedup → validar → escribir → mover.
Logger `agente1` → output/logs/agente1_YYYYMMDD.log (con PII enmascarada).

## Patrón adaptador
Interfaces abstractas FuenteCorreos / DestinoCasos para reemplazar en producción por
Microsoft Graph API y API Front de Fraudes sin tocar lógica de negocio.

## Configuración AWS
- Autenticación preferida: AWS_PROFILE (SSO o perfil local). NO access keys en .env.
- Solo permiso requerido: bedrock:InvokeModel sobre el inference profile de Haiku.
