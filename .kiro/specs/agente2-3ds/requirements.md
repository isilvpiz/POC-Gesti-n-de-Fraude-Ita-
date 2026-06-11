# Requirements — Agente 2: Decisión de Chargeback 3DS

## Introducción

El Agente 2 evalúa los casos procesados por el Agente 1 y decide si aplica chargeback según la regla de responsabilidad 3DS. La regla 3DS solo es aplicable a transacciones **no presenciales** (e-commerce / card-not-present). Las decisiones deben ser auditables: cada decisión registra la versión de la regla aplicada.

## Regla de negocio (versión 1.0)

```
SI canal_venta == "No presencial":
    SI tiene_3ds == "Sí" → NO aplica chargeback
        (liability shift: el emisor asumió el riesgo al autenticar)
    SI tiene_3ds == "No" → SÍ aplica chargeback
        (comercio sin 3DS: responsabilidad del comercio, Itaú disputa a la marca)
SI canal_venta == "Presencial":
    → regla 3DS NO aplicable → estado PENDIENTE_REVISION
      (requiere evaluación manual por otro criterio: chip/banda, PIN, etc.)
```

## Requisitos (notación EARS)

### R1 — Lectura de casos

#### Acceptance Criteria
1. WHEN el agente se ejecuta, THE SYSTEM SHALL leer `output/casos.xlsx`
2. THE SYSTEM SHALL procesar solo registros con estado `PROCESADO`
3. THE SYSTEM SHALL excluir registros con estado `DUPLICADO`, `ERROR` o `PENDIENTE_REVISION`

### R2 — Evaluación de la regla 3DS

**User Story:** Como analista de fraudes, quiero que las decisiones de chargeback en e-commerce se tomen automáticamente, para reducir el tiempo de resolución.

#### Acceptance Criteria
1. WHEN un caso tiene `canal_venta == "No presencial"` AND `tiene_3ds == "No"`, THE SYSTEM SHALL decidir `aplica_chargeback = Sí` con justificación y código de razón sugerido (Visa 10.4 / Mastercard 4837)
2. WHEN un caso tiene `canal_venta == "No presencial"` AND `tiene_3ds == "Sí"`, THE SYSTEM SHALL decidir `aplica_chargeback = No` con justificación de liability shift
3. WHEN un caso tiene `canal_venta == "Presencial"`, THE SYSTEM SHALL marcar `estado_decision = PENDIENTE_REVISION` con justificación "Regla 3DS no aplicable a transacciones presenciales"
4. WHEN cualquier campo crítico (`canal_venta`, `tiene_3ds`) sea `PENDIENTE_REVISION`, THE SYSTEM SHALL marcar `estado_decision = PENDIENTE_REVISION`

### R3 — Trazabilidad y auditoría

**User Story:** Como auditor, necesito saber qué versión de la regla generó cada decisión, para responder a requerimientos regulatorios.

#### Acceptance Criteria
1. THE SYSTEM SHALL registrar en cada decisión el campo `version_regla` (ej: "3DS-v1.0")
2. THE SYSTEM SHALL registrar `dias_entre_transaccion_y_reclamo` calculado desde `fecha_transaccion` y `fecha_reclamo`
3. IF `dias_entre_transaccion_y_reclamo` excede el plazo configurable `PLAZO_MAXIMO_RECLAMO_DIAS` (default 30), THEN THE SYSTEM SHALL agregar la alerta "FUERA_DE_PLAZO" en el campo `alertas` sin bloquear la decisión

### R4 — Escritura de decisiones

#### Acceptance Criteria
1. WHEN una decisión es generada, THE SYSTEM SHALL escribirla en `output/decisiones.xlsx` con `id_decision` (UUID), `id_caso` (FK), timestamp y todos los campos definidos en el steering
2. WHEN el procesamiento finaliza, THE SYSTEM SHALL registrar en log un resumen: total evaluados, chargeback sí/no, pendientes, alertas de plazo
