"""
Tests para agente2/regla_3ds.py.

Cubre los 5 escenarios de tasks.md: no-3DS, 3DS, presencial, pendiente,
fuera de plazo; más casos adicionales (fechas inválidas, dentro de plazo).
"""

import pytest

from agente1.bedrock_client import PENDIENTE_REVISION
from agente2.caso_reader import CasoFraude
from agente2.regla_3ds import (
    ALERTA_FUERA_DE_PLAZO,
    CODIGO_RAZON_SIN_3DS,
    VERSION_REGLA,
    EvaluadorRegla3DS,
)


def _caso(**overrides) -> CasoFraude:
    """Construye un CasoFraude PROCESADO con valores por defecto."""
    valores = {
        "id_caso": "caso-001",
        "fecha_procesamiento": "2026-05-25T10:00:00",
        "archivo_origen": "caso_001.eml",
        "hash_dedup": "hash-1",
        "rut_cliente": "12.345.678-9",
        "nombre_cliente": "María González Fuentes",
        "numero_tarjeta": "4521",
        "monto_reclamado": 185900,
        "moneda": "CLP",
        "fecha_transaccion": "2026-05-20",
        "fecha_reclamo": "2026-05-25",
        "nombre_comercio": "TiendaOnline Express Ltda.",
        "canal_venta": "No presencial",
        "tiene_3ds": "No",
        "tipo_fraude": "Compra no reconocida por internet",
        "descripcion_reclamo": "No reconozco esta compra",
        "numero_operacion": "OP-2026-001-789456",
        "estado": "PROCESADO",
        "id_caso_original": "",
        "notas": "",
    }
    valores.update(overrides)
    return CasoFraude(**valores)


@pytest.fixture
def evaluador():
    return EvaluadorRegla3DS()


# === Escenario 1: no presencial + sin 3DS -> chargeback Sí ===

def test_no_3ds_aplica_chargeback(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(_caso(canal_venta="No presencial", tiene_3ds="No"))

    assert decision.aplica_chargeback == "Sí"
    assert decision.codigo_razon == CODIGO_RAZON_SIN_3DS
    assert decision.estado_decision == "RESUELTA"
    assert decision.version_regla == VERSION_REGLA


# === Escenario 2: no presencial + con 3DS -> NO chargeback (liability shift) ===

def test_con_3ds_no_aplica_chargeback(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(_caso(canal_venta="No presencial", tiene_3ds="Sí"))

    assert decision.aplica_chargeback == "No"
    assert decision.codigo_razon == ""
    assert decision.estado_decision == "RESUELTA"
    assert "Liability shift" in decision.justificacion


# === Escenario 3: presencial -> PENDIENTE_REVISION, regla no aplicable ===

def test_presencial_pendiente_revision(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(_caso(canal_venta="Presencial", tiene_3ds="No"))

    assert decision.aplica_chargeback == "—"
    assert decision.estado_decision == "PENDIENTE_REVISION"
    assert "no aplicable a transacciones presenciales" in decision.justificacion


# === Escenario 4: campo crítico PENDIENTE_REVISION ===

def test_canal_venta_pendiente(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(canal_venta=PENDIENTE_REVISION, tiene_3ds="No")
    )

    assert decision.estado_decision == "PENDIENTE_REVISION"
    assert decision.aplica_chargeback == "—"


def test_tiene_3ds_pendiente(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(canal_venta="No presencial", tiene_3ds=PENDIENTE_REVISION)
    )

    assert decision.estado_decision == "PENDIENTE_REVISION"
    assert decision.aplica_chargeback == "—"


# === Escenario 5: fuera de plazo ===

def test_fuera_de_plazo_agrega_alerta(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(
            canal_venta="No presencial",
            tiene_3ds="No",
            fecha_transaccion="2026-01-01",
            fecha_reclamo="2026-03-01",  # > 30 dias
        )
    )

    assert decision.dias_entre_transaccion_y_reclamo == 59
    assert ALERTA_FUERA_DE_PLAZO in decision.alertas
    # FUERA_DE_PLAZO no bloquea la decision
    assert decision.aplica_chargeback == "Sí"
    assert decision.estado_decision == "RESUELTA"


def test_dentro_de_plazo_sin_alerta(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(fecha_transaccion="2026-05-01", fecha_reclamo="2026-05-15")  # 14 dias
    )

    assert decision.dias_entre_transaccion_y_reclamo == 14
    assert decision.alertas == ""


def test_exactamente_en_el_plazo_sin_alerta(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(fecha_transaccion="2026-05-01", fecha_reclamo="2026-05-31")  # 30 dias
    )

    assert decision.dias_entre_transaccion_y_reclamo == 30
    assert decision.alertas == ""


# === Fechas inválidas ===

def test_fecha_invalida_no_calcula_dias_ni_crashea(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(
        _caso(fecha_transaccion="fecha-invalida", fecha_reclamo="2026-05-25")
    )

    assert decision.dias_entre_transaccion_y_reclamo is None
    assert decision.alertas == ""
    # La decisión principal sigue calculándose
    assert decision.aplica_chargeback == "Sí"


# === Combinación no contemplada ===

def test_canal_venta_inesperado(evaluador: EvaluadorRegla3DS) -> None:
    decision = evaluador.evaluar(_caso(canal_venta="Telefono", tiene_3ds="No"))

    assert decision.estado_decision == "PENDIENTE_REVISION"
    assert decision.aplica_chargeback == "—"
    assert "Combinación no contemplada" in decision.justificacion
