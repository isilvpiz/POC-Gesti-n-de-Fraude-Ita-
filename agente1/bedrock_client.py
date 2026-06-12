"""
Cliente Bedrock para extracción de datos de reclamos de fraude (Agente 1).

Usa la Converse API de Amazon Bedrock (bedrock-runtime) con el modelo
definido en BEDROCK_MODEL_ID para extraer los 13 campos del formulario
de reclamo a partir del texto del PDF.

IMPORTANTE: usa client.converse (Converse API), nunca invoke_model.
Autenticación vía AWS_PROFILE (perfil/SSO) — nunca access keys.
"""

import json
import logging
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from agente1.config import (
    AWS_PROFILE,
    AWS_REGION,
    BEDROCK_MAX_TOKENS,
    BEDROCK_MODEL_ID,
    USE_MOCK_BEDROCK,
)

logger = logging.getLogger(__name__)

PENDIENTE_REVISION = "PENDIENTE_REVISION"

# 11 campos obligatorios (steering agente1.md, columna "Requerido")
CAMPOS_REQUERIDOS = (
    "rut_cliente",
    "nombre_cliente",
    "numero_tarjeta",
    "monto_reclamado",
    "moneda",
    "fecha_transaccion",
    "fecha_reclamo",
    "nombre_comercio",
    "canal_venta",
    "tiene_3ds",
    "tipo_fraude",
)

# 2 campos opcionales
CAMPOS_OPCIONALES = ("descripcion_reclamo", "numero_operacion")


@dataclass
class DatosReclamo:
    """Los 13 campos extraídos del formulario de reclamo (ver steering)."""

    rut_cliente: str
    nombre_cliente: str
    numero_tarjeta: str
    monto_reclamado: float | str
    moneda: str
    fecha_transaccion: str
    fecha_reclamo: str
    nombre_comercio: str
    canal_venta: str
    tiene_3ds: str
    tipo_fraude: str
    descripcion_reclamo: str
    numero_operacion: str

    def campos_pendientes(self) -> list[str]:
        """Retorna los campos requeridos cuyo valor es PENDIENTE_REVISION (R3.5)."""
        return [
            campo
            for campo in CAMPOS_REQUERIDOS
            if getattr(self, campo) == PENDIENTE_REVISION
        ]


PROMPT_TEMPLATE = """Eres un asistente que extrae datos estructurados de formularios de reclamo de fraude bancario de Itaú Chile.

A partir del texto extraído de un formulario PDF, extrae los siguientes 13 campos y responde ÚNICAMENTE con un objeto JSON válido (sin texto adicional, sin bloques de código markdown):

- rut_cliente
- nombre_cliente
- numero_tarjeta (solo los últimos 4 dígitos)
- monto_reclamado (numérico, sin símbolos de moneda ni separadores de miles)
- moneda (ej: CLP, USD)
- fecha_transaccion (formato YYYY-MM-DD)
- fecha_reclamo (formato YYYY-MM-DD)
- nombre_comercio
- canal_venta ("Presencial" o "No presencial")
- tiene_3ds ("Sí" o "No")
- tipo_fraude
- descripcion_reclamo
- numero_operacion

Si no puedes determinar con certeza el valor de un campo REQUERIDO (todos excepto descripcion_reclamo y numero_operacion), usa el valor "PENDIENTE_REVISION" para ese campo.

Texto del formulario:
---
{texto_pdf}
---
"""


def datos_reclamo_pendiente() -> DatosReclamo:
    """
    Construye un DatosReclamo con todos los campos requeridos en
    PENDIENTE_REVISION y los opcionales vacíos.

    Útil para casos que no llegan a invocar Bedrock (ej. sin adjunto PDF, R1.4).
    """
    valores: dict[str, str] = {campo: PENDIENTE_REVISION for campo in CAMPOS_REQUERIDOS}
    valores.update({campo: "" for campo in CAMPOS_OPCIONALES})
    return DatosReclamo(**valores)


class ClienteBedrock:
    """Cliente para extracción de datos de reclamo vía Bedrock Converse API."""

    def __init__(self) -> None:
        if USE_MOCK_BEDROCK:
            # Modo demo: no se crea sesión AWS (ver heuristic_extractor.py)
            logger.warning(
                "USE_MOCK_BEDROCK=true -> usando extractor heurístico (NO Bedrock real, solo demo)"
            )
            self._cliente = None
            return

        config = Config(retries={"max_attempts": 3, "mode": "adaptive"})
        sesion = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        self._cliente = sesion.client("bedrock-runtime", config=config)

    def extraer_datos_reclamo(self, texto_pdf: str) -> DatosReclamo:
        """
        Extrae los 13 campos del reclamo a partir del texto del PDF.

        Args:
            texto_pdf: texto limpio extraído del formulario (ExtractorPDF).

        Returns:
            DatosReclamo con los 13 campos. Si Bedrock falla (tras los
            reintentos nativos de boto3) o la respuesta es inválida,
            retorna todos los campos requeridos en PENDIENTE_REVISION (R3.3/R3.4).
            Si USE_MOCK_BEDROCK=true, usa el extractor heurístico (modo demo).
        """
        if USE_MOCK_BEDROCK:
            from agente1.heuristic_extractor import extraer_datos_heuristico

            return extraer_datos_heuristico(texto_pdf)

        mensajes = self._construir_mensajes(texto_pdf)

        try:
            respuesta = self._cliente.converse(
                modelId=BEDROCK_MODEL_ID,
                messages=mensajes,
                inferenceConfig={"maxTokens": BEDROCK_MAX_TOKENS, "temperature": 0},
            )
        except (ClientError, BotoCoreError) as error:
            logger.error("Error al invocar Bedrock (Converse API): %s", error)
            return self._datos_pendientes_revision()

        return self._parsear_respuesta(respuesta)

    def _construir_mensajes(self, texto: str) -> list[dict]:
        """Construye el array `messages` en formato Converse API."""
        prompt = PROMPT_TEMPLATE.format(texto_pdf=texto)
        return [{"role": "user", "content": [{"text": prompt}]}]

    def _parsear_respuesta(self, respuesta: dict) -> DatosReclamo:
        """Parsea la respuesta de converse() y construye un DatosReclamo."""
        try:
            contenido = respuesta["output"]["message"]["content"][0]["text"]
            datos_json = json.loads(contenido)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            logger.error("Respuesta de Bedrock con formato inesperado: %s", error)
            return self._datos_pendientes_revision()

        valores: dict[str, str | float] = {}
        for campo in CAMPOS_REQUERIDOS:
            valor = datos_json.get(campo)
            valores[campo] = valor if valor not in (None, "") else PENDIENTE_REVISION
        for campo in CAMPOS_OPCIONALES:
            valores[campo] = datos_json.get(campo) or ""

        return DatosReclamo(**valores)

    def _datos_pendientes_revision(self) -> DatosReclamo:
        """Construye un DatosReclamo con todos los campos requeridos pendientes."""
        return datos_reclamo_pendiente()
