# Steering Agente 2 — Decisión de Chargeback 3DS

## Propósito

El Agente 2 automatiza la decisión de chargeback para transacciones disputadas, aplicando la regla de responsabilidad 3DS. La regla solo aplica a transacciones **no presenciales** (e-commerce / card-not-present).

## Regla de negocio (VERSION_REGLA = "3DS-v1.0")

```
SI canal_venta == "No presencial":
    SI tiene_3ds == "Sí":
        → NO aplica chargeback
        → Justificación: "Comercio con 3DS activo. Liability shift: el emisor
          asumió el riesgo al autenticar la transacción."
    SI tiene_3ds == "No":
        → SÍ aplica chargeback
        → Código de razón sugerido: Visa 10.4 / Mastercard 4837
        → Justificación: "Comercio sin 3DS en venta no presencial.
          Responsabilidad del comercio — Itaú puede disputar a la marca."

SI canal_venta == "Presencial":
    → estado_decision = PENDIENTE_REVISION
    → Justificación: "Regla 3DS no aplicable a transacciones presenciales.
      Requiere evaluación manual (chip/banda, PIN, etc.)."
```

## Validación de plazos

- Calcular `dias_entre_transaccion_y_reclamo = fecha_reclamo - fecha_transaccion`
- Si excede `PLAZO_MAXIMO_RECLAMO_DIAS` (default 30, configurable) → alerta `FUERA_DE_PLAZO` (no bloquea la decisión, pero queda registrada)

## Output Excel (output/decisiones.xlsx)

| Columna | Descripción |
|---|---|
| `id_decision` | UUID de la decisión |
| `id_caso` | FK al caso del Agente 1 |
| `fecha_decision` | Timestamp |
| `rut_cliente` | RUT (los logs lo enmascaran; el Excel lo conserva) |
| `monto_reclamado` | Monto |
| `moneda` | CLP / USD |
| `nombre_comercio` | Comercio |
| `canal_venta` | Presencial / No presencial |
| `tiene_3ds` | Sí / No |
| `aplica_chargeback` | Sí / No / — |
| `codigo_razon` | Visa 10.4 / MC 4837 (solo si aplica) |
| `justificacion` | Texto explicativo |
| `version_regla` | "3DS-v1.0" — auditoría regulatoria |
| `dias_entre_transaccion_y_reclamo` | Entero |
| `alertas` | FUERA_DE_PLAZO u otras |
| `estado_decision` | RESUELTA / PENDIENTE_REVISION |

## Reglas de validación

- Solo procesar casos con estado = `PROCESADO` del Agente 1
- Excluir `DUPLICADO`, `ERROR`, `PENDIENTE_REVISION`
- Si `canal_venta` o `tiene_3ds` es `PENDIENTE_REVISION` → decisión `PENDIENTE_REVISION`

## Consideraciones

- La regla es determinista — NO usa Bedrock (auditabilidad regulatoria)
- `version_regla` en cada registro permite reproducir decisiones históricas ante auditoría
- En producción: lectura/escritura via API Front de Fraudes (patrón adaptador)
