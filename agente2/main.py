"""
Orquestación del Agente 2 - Decisión de Chargeback 3DS.

Flujo: leer output/casos.xlsx -> filtrar PROCESADO -> evaluar regla 3DS
-> escribir output/decisiones.xlsx. Log con resumen final (R4.2).
"""

import logging
from datetime import datetime

from agente1.config import CASOS_EXCEL_PATH, DECISIONES_EXCEL_PATH, LOG_LEVEL, LOGS_DIR
from agente1.pii import configurar_filtro_pii
from agente2.caso_reader import LectorCasos
from agente2.decision_writer import EscritorDecisiones
from agente2.regla_3ds import ALERTA_FUERA_DE_PLAZO, EvaluadorRegla3DS

logger = logging.getLogger("agente2")


def configurar_logging() -> None:
    """
    Configura el logger 'agente2': salida a output/logs/agente2_YYYYMMDD.log
    y a consola, con FiltroPII aplicado a ambos handlers (reutiliza agente1/pii.py).
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta_log = LOGS_DIR / f"agente2_{datetime.now():%Y%m%d}.log"

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


def ejecutar() -> dict[str, int]:
    """
    Ejecuta el pipeline del Agente 2: lee casos PROCESADO, evalúa la regla
    3DS para cada uno y escribe las decisiones.

    Returns:
        Resumen con conteos: total, chargeback_si, chargeback_no,
        pendientes, fuera_de_plazo (R4.2).
    """
    configurar_logging()

    lector = LectorCasos()
    evaluador = EvaluadorRegla3DS()
    escritor = EscritorDecisiones()

    casos = lector.leer_casos(CASOS_EXCEL_PATH)
    procesables = lector.filtrar_procesables(casos)

    resumen = {
        "total": 0,
        "chargeback_si": 0,
        "chargeback_no": 0,
        "pendientes": 0,
        "fuera_de_plazo": 0,
    }

    for caso in procesables:
        resumen["total"] += 1

        decision = evaluador.evaluar(caso)
        escritor.escribir_decision(caso, decision, DECISIONES_EXCEL_PATH)

        if decision.estado_decision == "PENDIENTE_REVISION":
            resumen["pendientes"] += 1
        elif decision.aplica_chargeback == "Sí":
            resumen["chargeback_si"] += 1
        elif decision.aplica_chargeback == "No":
            resumen["chargeback_no"] += 1

        if ALERTA_FUERA_DE_PLAZO in decision.alertas:
            resumen["fuera_de_plazo"] += 1

        logger.info(
            "Caso %s evaluado -> aplica_chargeback=%s, estado_decision=%s",
            caso.id_caso,
            decision.aplica_chargeback,
            decision.estado_decision,
        )

    logger.info(
        "Resumen: total=%d chargeback_si=%d chargeback_no=%d pendientes=%d fuera_de_plazo=%d",
        resumen["total"],
        resumen["chargeback_si"],
        resumen["chargeback_no"],
        resumen["pendientes"],
        resumen["fuera_de_plazo"],
    )

    return resumen


if __name__ == "__main__":
    ejecutar()
