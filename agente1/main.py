"""
Orquestación del Agente 1 - Procesamiento de correos de reclamo de fraude.

Flujo (steering agente1.md):
  escanear -> por cada .eml: parsear -> extraer PDF -> leer/limpiar texto
  -> Bedrock -> calcular hash dedup -> validar -> escribir en casos.xlsx
  -> mover .eml a procesados/. Al final, log de resumen.
"""

import logging
from datetime import datetime
from pathlib import Path

from agente1.bedrock_client import ClienteBedrock, DatosReclamo, datos_reclamo_pendiente
from agente1.config import (
    CASOS_EXCEL_PATH,
    INPUT_EMAIL_DIR,
    LOG_LEVEL,
    LOGS_DIR,
    validar_configuracion,
)
from agente1.dedup import Deduplicador
from agente1.email_reader import LectorCorreo
from agente1.excel_writer import EscritorCasos
from agente1.pdf_extractor import ExtractorPDF
from agente1.pii import configurar_filtro_pii

logger = logging.getLogger("agente1")

ESTADOS = ("PROCESADO", "PENDIENTE_REVISION", "ERROR", "DUPLICADO")


def configurar_logging() -> None:
    """
    Configura el logger 'agente1': salida a output/logs/agente1_YYYYMMDD.log
    y a consola, con FiltroPII aplicado a ambos handlers (R4.2).
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta_log = LOGS_DIR / f"agente1_{datetime.now():%Y%m%d}.log"

    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    handler_archivo = logging.FileHandler(ruta_log, encoding="utf-8")
    handler_archivo.setFormatter(formato)
    configurar_filtro_pii(handler_archivo)

    handler_consola = logging.StreamHandler()
    handler_consola.setFormatter(formato)
    configurar_filtro_pii(handler_consola)

    logger.setLevel(LOG_LEVEL)
    logger.handlers.clear()
    logger.addHandler(handler_archivo)
    logger.addHandler(handler_consola)


def _es_monto_numerico(valor: object) -> bool:
    """Retorna True si `valor` puede interpretarse como número."""
    try:
        float(valor)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def determinar_estado(datos: DatosReclamo) -> tuple[str, str]:
    """
    Determina el estado de un caso a partir de DatosReclamo.

    Reglas (steering: "Reglas de validación" + R3.5):
      - Más de 3 campos requeridos en PENDIENTE_REVISION -> ERROR.
      - rut_cliente vacío/pendiente, monto_reclamado no numérico, o
        tiene_3ds fuera de {"Sí","No"} -> PENDIENTE_REVISION.
      - En otro caso -> PROCESADO.

    Returns:
        (estado, notas) — notas describe los motivos si no es PROCESADO.
    """
    pendientes = datos.campos_pendientes()

    if len(pendientes) > 3:
        return "ERROR", f"Mas de 3 campos requeridos sin extraer: {', '.join(pendientes)}"

    motivos: list[str] = list(pendientes)

    if "monto_reclamado" not in pendientes and not _es_monto_numerico(datos.monto_reclamado):
        motivos.append("monto_reclamado no es numerico")

    if "tiene_3ds" not in pendientes and datos.tiene_3ds not in ("Sí", "No"):
        motivos.append("tiene_3ds no es Si/No")

    if motivos:
        return "PENDIENTE_REVISION", "; ".join(motivos)

    return "PROCESADO", ""


def procesar_correo(
    ruta_eml: Path,
    lector: LectorCorreo,
    extractor_pdf: ExtractorPDF,
    cliente_bedrock: ClienteBedrock,
    deduplicador: Deduplicador,
    escritor: EscritorCasos,
) -> str:
    """
    Procesa un único correo .eml de punta a punta.

    Args:
        ruta_eml: ruta al archivo .eml a procesar.
        lector, extractor_pdf, cliente_bedrock, deduplicador, escritor:
            dependencias del pipeline (inyectadas para facilitar tests).

    Returns:
        Estado final del caso: PROCESADO | PENDIENTE_REVISION | ERROR | DUPLICADO.
    """
    correo = lector.parsear_correo(ruta_eml)
    ruta_pdf = lector.extraer_adjunto_pdf(correo)

    if ruta_pdf is None:
        # R1.4: sin adjunto PDF -> ERROR. No se calcula hash (datos vacíos).
        logger.warning("Correo %s sin adjunto PDF -> ERROR", ruta_eml.name)
        escritor.escribir_caso(
            datos=datos_reclamo_pendiente(),
            correo=correo,
            hash_dedup="",
            estado="ERROR",
            ruta_excel=CASOS_EXCEL_PATH,
            notas="sin adjunto",
        )
        lector.mover_procesado(ruta_eml)
        return "ERROR"

    texto = extractor_pdf.leer_texto(ruta_pdf)
    texto_limpio = extractor_pdf.limpiar_texto(texto)

    datos = cliente_bedrock.extraer_datos_reclamo(texto_limpio)

    hash_dedup = deduplicador.calcular_hash(datos)
    id_caso_original = deduplicador.existe_en_excel(hash_dedup, CASOS_EXCEL_PATH)

    if id_caso_original:
        # R2.2/R2.3: DUPLICADO -> no se envía al flujo del Agente 2 (fuera de este módulo).
        estado, notas = "DUPLICADO", f"Duplicado de {id_caso_original}"
    else:
        estado, notas = determinar_estado(datos)

    escritor.escribir_caso(
        datos=datos,
        correo=correo,
        hash_dedup=hash_dedup,
        estado=estado,
        ruta_excel=CASOS_EXCEL_PATH,
        id_caso_original=id_caso_original,
        notas=notas,
    )

    lector.mover_procesado(ruta_eml)
    logger.info("Correo %s procesado -> %s", ruta_eml.name, estado)
    return estado


def ejecutar() -> dict[str, int]:
    """
    Ejecuta el pipeline completo sobre los .eml en INPUT_EMAIL_DIR.

    Returns:
        Resumen con conteos: total, PROCESADO, PENDIENTE_REVISION, ERROR, DUPLICADO.
    """
    validar_configuracion()
    configurar_logging()

    lector = LectorCorreo()
    extractor_pdf = ExtractorPDF()
    cliente_bedrock = ClienteBedrock()
    deduplicador = Deduplicador()
    escritor = EscritorCasos()

    resumen: dict[str, int] = {"total": 0, **{estado: 0 for estado in ESTADOS}}

    archivos = lector.escanear_directorio(INPUT_EMAIL_DIR)
    logger.info("Iniciando procesamiento de %d correo(s)", len(archivos))

    for ruta_eml in archivos:
        resumen["total"] += 1
        try:
            estado = procesar_correo(
                ruta_eml, lector, extractor_pdf, cliente_bedrock, deduplicador, escritor
            )
            resumen[estado] += 1
        except Exception as error:  # noqa: BLE001 - aislar fallas por correo (steering: continuar)
            logger.error("Error inesperado procesando %s: %s", ruta_eml.name, error)
            resumen["ERROR"] += 1

    logger.info(
        "Resumen: total=%d procesados=%d pendientes=%d errores=%d duplicados=%d",
        resumen["total"],
        resumen["PROCESADO"],
        resumen["PENDIENTE_REVISION"],
        resumen["ERROR"],
        resumen["DUPLICADO"],
    )

    return resumen


if __name__ == "__main__":
    ejecutar()
