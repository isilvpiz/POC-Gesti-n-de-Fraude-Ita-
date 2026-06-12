"""
Tests para agente1/bedrock_client.py.

Todos los tests mockean boto3.Session / client.converse — NO requieren
AWS_PROFILE configurado ni conexión a AWS.
"""

import json

import pytest
from botocore.exceptions import ClientError

from agente1.bedrock_client import (
    CAMPOS_OPCIONALES,
    CAMPOS_REQUERIDOS,
    PENDIENTE_REVISION,
    ClienteBedrock,
    DatosReclamo,
)

DATOS_VALIDOS_JSON = {
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
    "descripcion_reclamo": "No reconozco esta compra.",
    "numero_operacion": "OP-2026-001-789456",
}


def _respuesta_converse(json_texto: str) -> dict:
    return {"output": {"message": {"content": [{"text": json_texto}]}}}


@pytest.fixture
def cliente_y_mock_boto(mocker):
    """ClienteBedrock con boto3.Session mockeado (sin AWS_PROFILE real)."""
    mock_session = mocker.patch("agente1.bedrock_client.boto3.Session")
    mock_cliente_boto = mocker.MagicMock()
    mock_session.return_value.client.return_value = mock_cliente_boto

    cliente = ClienteBedrock()
    return cliente, mock_cliente_boto


# === Instanciación ===

def test_instanciar_cliente_sin_aws_real(cliente_y_mock_boto) -> None:
    cliente, _ = cliente_y_mock_boto
    assert isinstance(cliente, ClienteBedrock)


# === _construir_mensajes ===

def test_construir_mensajes_formato_converse(cliente_y_mock_boto) -> None:
    cliente, _ = cliente_y_mock_boto

    mensajes = cliente._construir_mensajes("texto del pdf")

    assert mensajes[0]["role"] == "user"
    assert "texto del pdf" in mensajes[0]["content"][0]["text"]


# === extraer_datos_reclamo - caso exitoso ===

def test_extraer_datos_reclamo_exitoso(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    mock_cliente_boto.converse.return_value = _respuesta_converse(
        json.dumps(DATOS_VALIDOS_JSON)
    )

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert isinstance(datos, DatosReclamo)
    assert datos.rut_cliente == "12.345.678-9"
    assert datos.monto_reclamado == 185900
    assert datos.numero_operacion == "OP-2026-001-789456"
    assert datos.campos_pendientes() == []

    mock_cliente_boto.converse.assert_called_once()
    _, kwargs = mock_cliente_boto.converse.call_args
    assert kwargs["modelId"]  # se pasa BEDROCK_MODEL_ID


# === extraer_datos_reclamo - Bedrock falla ===

def test_extraer_datos_reclamo_error_bedrock(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    mock_cliente_boto.converse.side_effect = ClientError(
        error_response={"Error": {"Code": "ThrottlingException", "Message": "rate limit"}},
        operation_name="Converse",
    )

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert set(datos.campos_pendientes()) == set(CAMPOS_REQUERIDOS)
    for campo in CAMPOS_OPCIONALES:
        assert getattr(datos, campo) == ""


# === _parsear_respuesta - respuesta inválida ===

def test_parsear_respuesta_json_invalido(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    mock_cliente_boto.converse.return_value = _respuesta_converse("esto no es json")

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert set(datos.campos_pendientes()) == set(CAMPOS_REQUERIDOS)


def test_parsear_respuesta_estructura_inesperada(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    mock_cliente_boto.converse.return_value = {"output": {}}  # sin "message"

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert set(datos.campos_pendientes()) == set(CAMPOS_REQUERIDOS)


# === Campos faltantes en el JSON ===

def test_campo_requerido_faltante_queda_pendiente(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    datos_incompletos = DATOS_VALIDOS_JSON.copy()
    del datos_incompletos["rut_cliente"]
    mock_cliente_boto.converse.return_value = _respuesta_converse(
        json.dumps(datos_incompletos)
    )

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert datos.rut_cliente == PENDIENTE_REVISION
    assert "rut_cliente" in datos.campos_pendientes()


def test_campos_opcionales_faltantes_quedan_vacios(cliente_y_mock_boto) -> None:
    cliente, mock_cliente_boto = cliente_y_mock_boto
    datos_incompletos = DATOS_VALIDOS_JSON.copy()
    del datos_incompletos["numero_operacion"]
    del datos_incompletos["descripcion_reclamo"]
    mock_cliente_boto.converse.return_value = _respuesta_converse(
        json.dumps(datos_incompletos)
    )

    datos = cliente.extraer_datos_reclamo("texto del formulario")

    assert datos.numero_operacion == ""
    assert datos.descripcion_reclamo == ""
    assert datos.campos_pendientes() == []


# === DatosReclamo.campos_pendientes ===

def test_campos_pendientes_detecta_multiples() -> None:
    valores = DATOS_VALIDOS_JSON.copy()
    valores["rut_cliente"] = PENDIENTE_REVISION
    valores["monto_reclamado"] = PENDIENTE_REVISION
    datos = DatosReclamo(**valores)

    pendientes = datos.campos_pendientes()

    assert "rut_cliente" in pendientes
    assert "monto_reclamado" in pendientes
    assert len(pendientes) == 2
