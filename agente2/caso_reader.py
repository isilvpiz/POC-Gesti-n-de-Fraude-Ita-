"""
Lectura de casos procesados por el Agente 1 (output/casos.xlsx) para
el Agente 2.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from agente1.excel_writer import COLUMNAS

logger = logging.getLogger(__name__)


@dataclass
class CasoFraude:
    """Un registro de output/casos.xlsx (las 20 columnas escritas por Agente 1)."""

    id_caso: str
    fecha_procesamiento: str
    archivo_origen: str
    hash_dedup: str
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
    estado: str
    id_caso_original: str
    notas: str


class LectorCasos:
    """Lee casos desde output/casos.xlsx y filtra los procesables por Agente 2."""

    def leer_casos(self, ruta: Path) -> list[CasoFraude]:
        """
        Lee todos los registros de output/casos.xlsx.

        Args:
            ruta: ruta al archivo casos.xlsx.

        Returns:
            Lista de CasoFraude. Lista vacía si el archivo no existe, no
            puede leerse, o sus encabezados no coinciden con los esperados.
        """
        if not ruta.exists():
            logger.warning("No existe %s; no hay casos para leer", ruta)
            return []

        try:
            libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        except (OSError, InvalidFileException) as error:
            logger.error("No se pudo abrir %s: %s", ruta, error)
            return []

        try:
            hoja = libro.active
            filas = hoja.iter_rows(values_only=True)

            try:
                encabezados = list(next(filas))
            except StopIteration:
                logger.warning("%s está vacío", ruta)
                return []

            if encabezados != COLUMNAS:
                logger.error(
                    "Encabezados de %s no coinciden con los esperados (COLUMNAS)", ruta
                )
                return []

            casos: list[CasoFraude] = []
            for fila in filas:
                valores = {
                    columna: (valor if valor is not None else "")
                    for columna, valor in zip(COLUMNAS, fila)
                }
                casos.append(CasoFraude(**valores))

            logger.info("Se leyeron %d caso(s) de %s", len(casos), ruta)
            return casos
        finally:
            libro.close()

    def filtrar_procesables(self, casos: list[CasoFraude]) -> list[CasoFraude]:
        """
        Filtra solo los casos con estado PROCESADO (R1.2/R1.3).

        Excluye DUPLICADO, ERROR y PENDIENTE_REVISION.

        Args:
            casos: lista de casos leídos con `leer_casos`.

        Returns:
            Lista de casos con estado == "PROCESADO".
        """
        procesables = [caso for caso in casos if caso.estado == "PROCESADO"]
        logger.info(
            "Casos procesables (PROCESADO): %d de %d", len(procesables), len(casos)
        )
        return procesables
