"""
Extractor heurístico de datos de reclamo — MODO DEMO sin Bedrock.

⚠️ Esta adición NO forma parte del design.md original (T5). Se agrega
para poder ejecutar el pipeline completo (run_pipeline.py) sin
AWS_PROFILE, extrayendo los 13 campos REALES del PDF (no inventados),
aprovechando que los formularios de Itaú siguen un formato fijo de
etiquetas "Campo / Valor". Se activa con USE_MOCK_BEDROCK=true.

NO reemplaza a Bedrock para producción: es estrictamente más frágil
(depende del formato exacto del PDF) y no entiende lenguaje natural.
"""

import logging
import re

from agente1.bedrock_client import CAMPOS_OPCIONALES, PENDIENTE_REVISION, DatosReclamo

logger = logging.getLogger(__name__)

# Orden y etiquetas exactas del formulario PDF de Itaú -> campo de DatosReclamo
ETIQUETAS_CAMPOS: list[tuple[str, str]] = [
    ("RUT Cliente", "rut_cliente"),
    ("Nombre Cliente", "nombre_cliente"),
    ("Últimos 4 dígitos tarjeta", "numero_tarjeta"),
    ("Monto Reclamado", "monto_reclamado"),
    ("Moneda", "moneda"),
    ("Fecha de Transacción", "fecha_transaccion"),
    ("Fecha de Reclamo", "fecha_reclamo"),
    ("Nombre del Comercio", "nombre_comercio"),
    ("Canal de Venta", "canal_venta"),
    ("Comercio tiene autenticación 3DS", "tiene_3ds"),
    ("Tipo de Fraude", "tipo_fraude"),
    ("Número de Operación", "numero_operacion"),
]

ETIQUETA_DESCRIPCION = "Descripción del Reclamo:"
PREFIJO_FIRMA = "Firma del Cliente"

_ETIQUETAS_CONOCIDAS = {etiqueta for etiqueta, _ in ETIQUETAS_CAMPOS} | {ETIQUETA_DESCRIPCION}


def extraer_datos_heuristico(texto_limpio: str) -> DatosReclamo:
    """
    Extrae los 13 campos de DatosReclamo por coincidencia de etiquetas
    conocidas del formulario "Campo / Valor" de Itaú.

    Si una etiqueta requerida no tiene línea de valor (porque el PDF
    la dejó en blanco y ExtractorPDF.limpiar_texto() eliminó la línea
    vacía), el campo queda en PENDIENTE_REVISION — igual que haría
    Bedrock ante un dato no extraíble (R3.3).

    Args:
        texto_limpio: texto del PDF tras ExtractorPDF.limpiar_texto().

    Returns:
        DatosReclamo con los valores encontrados en el PDF.
    """
    lineas = texto_limpio.splitlines()
    valores: dict[str, str] = {}

    indice = 0
    while indice < len(lineas):
        linea = lineas[indice].strip()

        if linea == ETIQUETA_DESCRIPCION and "descripcion_reclamo" not in valores:
            descripcion, indice = _extraer_descripcion(lineas, indice + 1)
            valores["descripcion_reclamo"] = descripcion
            continue

        for etiqueta, campo in ETIQUETAS_CAMPOS:
            if linea == etiqueta and campo not in valores:
                siguiente = lineas[indice + 1].strip() if indice + 1 < len(lineas) else ""
                if siguiente and siguiente not in _ETIQUETAS_CONOCIDAS:
                    valores[campo] = siguiente
                    indice += 1
                else:
                    valores[campo] = ""
                break

        indice += 1

    datos = _construir_datos_reclamo(valores)
    logger.info(
        "Extracción heurística (modo demo): %d/%d campos requeridos con valor",
        sum(1 for _, c in ETIQUETAS_CAMPOS if c not in CAMPOS_OPCIONALES and valores.get(c)),
        sum(1 for _, c in ETIQUETAS_CAMPOS if c not in CAMPOS_OPCIONALES),
    )
    return datos


def _extraer_descripcion(lineas: list[str], inicio: int) -> tuple[str, int]:
    """Recolecta las líneas de la descripción hasta 'Firma del Cliente...' (inclusive del índice de corte)."""
    partes: list[str] = []
    indice = inicio
    while indice < len(lineas):
        linea = lineas[indice].strip()
        if linea.startswith(PREFIJO_FIRMA):
            break
        if linea:
            partes.append(linea)
        indice += 1
    return " ".join(partes).strip(), indice


def _limpiar_monto(valor: str) -> int | str:
    """Convierte '$ 185.900' -> 185900. PENDIENTE_REVISION si está vacío o no tiene dígitos."""
    if not valor:
        return PENDIENTE_REVISION

    solo_digitos = re.sub(r"[^\d]", "", valor)
    if not solo_digitos:
        return PENDIENTE_REVISION

    return int(solo_digitos)


def _construir_datos_reclamo(valores: dict[str, str]) -> DatosReclamo:
    """Aplica defaults: campos requeridos vacíos -> PENDIENTE_REVISION; opcionales -> ''."""
    datos: dict[str, str | int] = {}

    for _, campo in ETIQUETAS_CAMPOS:
        valor = valores.get(campo, "")
        if campo == "monto_reclamado":
            datos[campo] = _limpiar_monto(valor)
        elif campo in CAMPOS_OPCIONALES:
            datos[campo] = valor
        else:
            datos[campo] = valor if valor else PENDIENTE_REVISION

    for campo in CAMPOS_OPCIONALES:
        datos.setdefault(campo, valores.get(campo, ""))

    return DatosReclamo(**datos)
