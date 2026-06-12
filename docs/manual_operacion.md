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

Autenticación vía **AWS_PROFILE** (SSO o perfil local) — **nunca** access keys en `.env`.

1. Configurar un perfil AWS: `aws configure sso` (o `aws configure --profile <nombre>` para un perfil local)
2. Habilitar el modelo Claude 3.5 Haiku en Amazon Bedrock, región `us-east-1` (`BEDROCK_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0`, prefijo `us.` por ser inference profile)
3. Asegurar que el perfil tenga permiso para invocar Bedrock Converse API
4. En `.env`, configurar `AWS_PROFILE=<nombre-del-perfil>`

> Sin AWS configurado, todo el código corre igual: los tests usan mocks de Bedrock (ver sección "Ejecución de tests").

---

## Agregar nuevos correos para procesar

1. Copiar archivo `.eml` a `input/emails/`
2. El correo debe tener un PDF adjunto con el formulario de reclamo
3. Ejecutar `python -m agente1.main`
4. El correo se moverá automáticamente a `input/emails/procesados/` al ser procesado

---

## Ejecución

```bash
# Solo Agente 1 (procesa correos -> output/casos.xlsx)
python -m agente1.main

# Solo Agente 2 (evalúa casos -> output/decisiones.xlsx)
python -m agente2.main

# Flujo completo (Agente 1 -> Agente 2)
python run_pipeline.py
```

> `agente1` y `agente2` son paquetes Python (usan imports absolutos como
> `from agente1.config import ...`), por eso se ejecutan con `-m`.
> `run_pipeline.py` sí se ejecuta como script normal (está en la raíz).

---

## Interpretación de outputs

### `output/casos.xlsx` — Output Agente 1

| Estado | Significado | Acción |
|---|---|---|
| `PROCESADO` | Todos los campos requeridos extraídos y válidos | Pasa automáticamente al Agente 2 |
| `PENDIENTE_REVISION` | 1-3 campos requeridos en `PENDIENTE_REVISION`, o `monto_reclamado`/`tiene_3ds` con valor inválido | Revisar manualmente y completar en el Excel |
| `ERROR` | Más de 3 campos requeridos en `PENDIENTE_REVISION` (R3.5), o correo sin adjunto PDF (`notas="sin adjunto"`) | Revisar el correo/PDF original manualmente |
| `DUPLICADO` | Mismo hash de deduplicación (`rut + numero_operacion + monto`) que un caso previo (ver `id_caso_original`) | No se reenvía al Agente 2; verificar si es reclamo repetido |

### `output/decisiones.xlsx` — Output Agente 2

Solo se generan decisiones para casos con `estado == PROCESADO` (R1.2/R1.3).

| `canal_venta` | `tiene_3ds` | `aplica_chargeback` | `estado_decision` | Significado |
|---|---|---|---|---|
| No presencial | No | Sí | RESUELTA | Comercio sin 3DS — Itaú puede disputar a la marca (`codigo_razon`: Visa 10.4 / MC 4837) |
| No presencial | Sí | No | RESUELTA | Liability shift: comercio con 3DS, no aplica chargeback |
| Presencial | (cualquiera) | — | PENDIENTE_REVISION | Regla 3DS no aplicable a presenciales; requiere evaluación manual (chip/banda, PIN, etc.) |
| `PENDIENTE_REVISION` | / | — | PENDIENTE_REVISION | `canal_venta` o `tiene_3ds` venía pendiente desde Agente 1 (no debería ocurrir en casos `PROCESADO`, pero se valida por robustez) |

**Otras columnas relevantes:**
- `alertas`: puede contener `FUERA_DE_PLAZO` si `dias_entre_transaccion_y_reclamo > PLAZO_MAXIMO_RECLAMO_DIAS` (default 30 días, configurable en `.env`). **No bloquea** la decisión, solo queda registrada.
- `version_regla`: siempre `"3DS-v1.0"` — permite reproducir decisiones históricas ante auditoría regulatoria.
- `dias_entre_transaccion_y_reclamo`: entero calculado como `fecha_reclamo - fecha_transaccion`. Puede ser vacío si alguna fecha no tiene formato `YYYY-MM-DD` válido.

---

## Logs

Los logs se guardan en `output/logs/`:
- `agente1_YYYYMMDD.log` — log del Agente 1
- `agente2_YYYYMMDD.log` — log del Agente 2

Niveles de log: `INFO` (normal), `WARNING` (pendiente revisión), `ERROR` (fallo)

---

## Casos de prueba incluidos

| Archivo | Escenario (datos del PDF) | Resultado esperado |
|---|---|---|
| `caso_001.eml` | No presencial, sin 3DS, 5 días entre transacción y reclamo | Agente1=`PROCESADO` → Agente2: `aplica_chargeback=Sí` (Visa 10.4 / MC 4837), `estado_decision=RESUELTA` |
| `caso_002.eml` | No presencial, con 3DS, 3 días | Agente1=`PROCESADO` → Agente2: `aplica_chargeback=No` (liability shift), `estado_decision=RESUELTA` |
| `caso_003.eml` | 5 campos requeridos vacíos en el PDF (`numero_tarjeta`, `monto_reclamado`, `moneda`, `canal_venta`, `tiene_3ds`) | Agente1=`ERROR` (>3 campos `PENDIENTE_REVISION`, R3.5) — **no llega al Agente 2** |
| `caso_004.eml` | Presencial, 53 días entre transacción (2026-04-10) y reclamo (2026-06-02) | Agente1=`PROCESADO` → Agente2: `estado_decision=PENDIENTE_REVISION` (presencial), `alertas=FUERA_DE_PLAZO` (53 > 30 días) |

> Nota: la regla 3DS solo aplica a transacciones no presenciales. Cada decisión registra `version_regla="3DS-v1.0"` para auditoría.
>
> ⚠️ `caso_003.eml` requiere extracción real vía Bedrock para confirmar este resultado: con los mocks de los tests se simula manualmente que falta `nombre_comercio` (1 campo), por lo que en los tests automatizados ese caso queda en `PENDIENTE_REVISION`, no `ERROR`. El resultado de esta tabla (`ERROR`) corresponde al contenido real de `formulario_003.pdf` evaluado contra R3.5, pendiente de validar con Bedrock real.

---

## Ejecución de tests

```bash
# Todos los tests (91 tests, sin AWS - todo mockeado)
python -m pytest tests/

# Con detalle
python -m pytest tests/ -v

# Agente 1
python -m pytest tests/test_email_reader.py tests/test_pdf_extractor.py tests/test_pii.py \
  tests/test_dedup.py tests/test_excel_writer.py tests/test_bedrock_client.py tests/test_main.py

# Agente 2
python -m pytest tests/test_caso_reader.py tests/test_regla_3ds.py \
  tests/test_decision_writer.py tests/test_main_agente2.py

# Pipeline end-to-end (caso_001-004)
python -m pytest tests/test_pipeline_integracion.py -v
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
