"""
Pipeline end-to-end: Agente 1 (procesamiento de correos de fraude) ->
Agente 2 (decisión de chargeback 3DS).

Ejecuta ambos agentes en secuencia: Agente 1 escribe output/casos.xlsx,
Agente 2 lo lee y escribe output/decisiones.xlsx.
"""

import logging

from agente1 import main as agente1_main
from agente2 import main as agente2_main

logger = logging.getLogger("pipeline")


def ejecutar() -> dict[str, dict[str, int]]:
    """
    Ejecuta el pipeline completo: Agente 1 -> Agente 2.

    Returns:
        {"agente1": resumen_agente1, "agente2": resumen_agente2}
    """
    logger.info("=== Iniciando pipeline: Agente 1 ===")
    resumen_agente1 = agente1_main.ejecutar()

    logger.info("=== Iniciando pipeline: Agente 2 ===")
    resumen_agente2 = agente2_main.ejecutar()

    logger.info("=== Pipeline finalizado ===")
    return {"agente1": resumen_agente1, "agente2": resumen_agente2}


if __name__ == "__main__":
    resultado = ejecutar()
    print(resultado)
