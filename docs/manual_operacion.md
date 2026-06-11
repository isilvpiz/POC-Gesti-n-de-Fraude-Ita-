# Manual de Operación — POC Gestión de Fraude Itaú

## Instalación

```bash
git clone <repo>
cd poc_itau
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales AWS reales
```

---

## Configuración AWS

1. Acceder a la consola AWS y habilitar el modelo `anthropic.claude-haiku-3-5` en Amazon Bedrock
2. Crear credenciales IAM con permisos `bedrock:InvokeModel`
3. Agregar credenciales al archivo `.env`

---

## Agregar nuevos correos para procesar

1. Copiar archivo `.eml` a `input/emails/`
2. El correo debe tener un PDF adjunto con el formulario de reclamo
3. Ejecutar `python agente1/main.py`
4. El correo se moverá automáticamente a `input/emails/procesados/` al ser procesado

---

## Ejecución

```bash
# Solo Agente 1 (procesa correos → output/casos.xlsx)
python agente1/main.py

# Solo Agente 2 (evalúa casos → output/decisiones.xlsx)
python agente2/main.py

# Flujo completo (Agente 1 → Agente 2)
python run_pipeline.py
```

---

## Interpretación de outputs

### `output/casos.xlsx` — Output Agente 1

| Estado | Significado | Acción |
|---|---|---|
| `PROCESADO` | Todos los campos extraídos correctamente | Pasa automáticamente al Agente 2 |
| `PENDIENTE_REVISION` | Uno o más campos faltantes o ambiguos | Revisar manualmente y completar |
| `ERROR` | Bedrock no pudo extraer los datos | Revisar el PDF adjunto del correo |

### `output/decisiones.xlsx` — Output Agente 2

| `aplica_chargeback` | `tiene_3ds` | Significado |
|---|---|---|
| Sí | No | El comercio no tiene 3DS → Itaú puede disputar a la marca |
| No | Sí | El comercio tiene 3DS → No aplica chargeback |
| PENDIENTE_REVISION | PENDIENTE_REVISION | Revisar el caso manualmente |

---

## Logs

Los logs se guardan en `output/logs/`:
- `agente1_YYYYMMDD.log` — log del Agente 1
- `agente2_YYYYMMDD.log` — log del Agente 2

Niveles de log: `INFO` (normal), `WARNING` (pendiente revisión), `ERROR` (fallo)

---

## Casos de prueba incluidos

| Archivo | Escenario | Resultado esperado |
|---|---|---|
| `caso_001.eml` | No presencial, SIN 3DS | aplica_chargeback = Sí (Visa 10.4 / MC 4837) |
| `caso_002.eml` | No presencial, CON 3DS | aplica_chargeback = No (liability shift) |
| `caso_003.eml` | Campos faltantes | estado = PENDIENTE_REVISION |
| `caso_004.eml` | Presencial + reclamo a 53 días | PENDIENTE_REVISION + alerta FUERA_DE_PLAZO |

> Nota: la regla 3DS solo aplica a transacciones no presenciales. Cada decisión registra `version_regla` para auditoría.

---

## Ejecución de tests

```bash
# Todos los tests
pytest tests/

# Test específico
pytest tests/test_agente1.py
pytest tests/test_agente2.py
pytest tests/test_pipeline.py

# Con detalle
pytest tests/ -v
```

---

## Migración a producción

Este POC está diseñado con patrón adaptador para facilitar la migración:

| Componente POC | Reemplazar por |
|---|---|
| Directorio `input/emails/` | Microsoft Graph API (casilla email Itaú) |
| `output/casos.xlsx` | API REST Front de Fraudes (escritura) |
| `output/decisiones.xlsx` | API REST Front de Fraudes (actualización decisión) |

Solo se deben modificar los módulos `email_reader.py`, `excel_writer.py` y `decision_writer.py` — la lógica de negocio no cambia.
