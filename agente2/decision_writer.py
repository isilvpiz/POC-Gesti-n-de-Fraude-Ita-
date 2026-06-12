"""
Escritura de decisiones de chargeback a output/decisiones.xlsx (Agente 2).
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import InvalidFileException

from agente2.caso_reader import CasoFraude
from agente2.regla_3ds import DecisionChargeback

logger = logging.getLogger(__name__)

# 16 columnas (steering agente2.md)
COLUMNAS_DECISIONES = [
    "id_decision",
    "id_caso",
    "fecha_decision",
    "rut_cliente",
    "monto_reclamado",
    "moneda",
    "nombre_comercio",
    "canal_venta",
    "tiene_3ds",
    "aplica_chargeback",
    "codigo_razon",
    "justificacion",
    "version_regla",
    "dias_entre_transaccion_y_reclamo",
    "alertas",
    "estado_decision",
]


class EscritorDecisiones:
    """Inicializa y escribe registros en output/decisiones.xlsx."""

    def inicializar_excel(self, ruta: Path) -> None:
        """
        Crea output/decisiones.xlsx con sus encabezados si aún no existe.

        Args:
            ruta: ruta al archivo decisiones.xlsx.
        """
        if ruta.exists():
            return

        ruta.parent.mkdir(parents=True, exist_ok=True)

        libro = Workbook()
        hoja = libro.active
        hoja.title = "decisiones"
        hoja.append(COLUMNAS_DECISIONES)
        libro.save(ruta)

        logger.info("Archivo creado: %s", ruta)

    def escribir_decision(
        self,
        caso: CasoFraude,
        decision: DecisionChargeback,
        ruta_excel: Path,
    ) -> str:
        """
        Escribe un registro de decisión en output/decisiones.xlsx.

        Crea el archivo con encabezados si no existe (R4.1).

        Args:
            caso: caso evaluado (CasoFraude, estado PROCESADO).
            decision: resultado de EvaluadorRegla3DS.evaluar().
            ruta_excel: ruta al archivo decisiones.xlsx.

        Returns:
            id_decision generado (UUID en formato string).

        Raises:
            ValueError: si el archivo no puede leerse/escribirse.
        """
        self.inicializar_excel(ruta_excel)

        id_decision = str(uuid.uuid4())
        fecha_decision = datetime.now().isoformat()

        fila = [
            id_decision,
            caso.id_caso,
            fecha_decision,
            caso.rut_cliente,
            caso.monto_reclamado,
            caso.moneda,
            caso.nombre_comercio,
            caso.canal_venta,
            caso.tiene_3ds,
            decision.aplica_chargeback,
            decision.codigo_razon,
            decision.justificacion,
            decision.version_regla,
            decision.dias_entre_transaccion_y_reclamo,
            decision.alertas,
            decision.estado_decision,
        ]

        try:
            libro = openpyxl.load_workbook(ruta_excel)
            hoja = libro.active
            hoja.append(fila)
            libro.save(ruta_excel)
            libro.close()
        except (OSError, InvalidFileException) as error:
            logger.error("No se pudo escribir en %s: %s", ruta_excel, error)
            raise ValueError(f"No se pudo escribir en {ruta_excel}") from error

        logger.info(
            "Decisión escrita: id_decision=%s, id_caso=%s, aplica_chargeback=%s, estado_decision=%s",
            id_decision,
            caso.id_caso,
            decision.aplica_chargeback,
            decision.estado_decision,
        )
        return id_decision
