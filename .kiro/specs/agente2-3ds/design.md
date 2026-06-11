# Design — Agente 2: Decisión de Chargeback 3DS

## Módulos

### `agente2/caso_reader.py`
```
Clase: LectorCasos
  - leer_casos(ruta: Path) → list[CasoFraude]
  - filtrar_procesables(casos) → list   # solo estado PROCESADO, excluye DUPLICADO/ERROR/PENDIENTE
```

### `agente2/regla_3ds.py`
```
VERSION_REGLA = "3DS-v1.0"
PLAZO_MAXIMO_RECLAMO_DIAS = 30  # configurable vía .env

Clase: EvaluadorRegla3DS
  - evaluar(caso: CasoFraude) → DecisionChargeback

Lógica:
  canal_venta == "No presencial" y tiene_3ds == "No"
      → aplica_chargeback=True, codigo_razon="Visa 10.4 / MC 4837"
  canal_venta == "No presencial" y tiene_3ds == "Sí"
      → aplica_chargeback=False (liability shift)
  canal_venta == "Presencial"
      → estado_decision="PENDIENTE_REVISION" ("Regla 3DS no aplicable")
  cualquier campo crítico PENDIENTE_REVISION
      → estado_decision="PENDIENTE_REVISION"

Cálculo adicional:
  dias_entre_transaccion_y_reclamo = fecha_reclamo - fecha_transaccion
  Si > PLAZO_MAXIMO_RECLAMO_DIAS → alertas += "FUERA_DE_PLAZO"

DataClass DecisionChargeback:
  aplica_chargeback, justificacion, codigo_razon, estado_decision,
  version_regla, dias_entre_transaccion_y_reclamo, alertas
```

### `agente2/decision_writer.py`
```
Clase: EscritorDecisiones
Columnas decisiones.xlsx:
  id_decision, id_caso, fecha_decision, rut_cliente, monto_reclamado, moneda,
  nombre_comercio, canal_venta, tiene_3ds, aplica_chargeback, codigo_razon,
  justificacion, version_regla, dias_entre_transaccion_y_reclamo, alertas, estado_decision
```

### `agente2/main.py`
Orquesta lectura → evaluación → escritura. Log con PII enmascarada (reutiliza agente1/pii.py).
Resumen final: evaluados, chargeback sí/no, pendientes, fuera de plazo.

## Notas de auditoría
- version_regla en cada decisión: permite reproducir decisiones históricas ante auditoría.
- La regla es determinista — NO usa Bedrock. Auditabilidad regulatoria exige reglas trazables.
