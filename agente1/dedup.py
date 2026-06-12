"""
Deduplicación de casos de reclamo de fraude (Agente 1).

Calcula un hash de deduplicación a partir de los datos extraídos del
reclamo y verifica si ya existe un caso con ese hash en output/casos.xlsx.
"""

import hashlib
import logging
from pathlib import Path
from typing import Protocol

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)


class DatosReclamoProtocolo(Protocol):
    """
    Estructura mínima requerida para calcular el hash de deduplicación.

    Cualquier objeto con estos atributos (p. ej. DatosReclamo de
    bedrock_client.py) puede usarse aquí sin import directo.
    """

    rut_cliente: str
    numero_operacion: str
    monto_reclamado: float


class Deduplicador:
    """Calcula y verifica hashes de deduplicación de casos de reclamo."""

    def calcular_hash(self, datos: DatosReclamoProtocolo) -> str:
        """
        Calcula el hash SHA-256 de deduplicación: rut + numero_operacion + monto.

        El monto se normaliza a 2 decimales para que el mismo valor
        numérico (int o float) produzca siempre el mismo hash.

        Args:
            datos: objeto con rut_cliente, numero_operacion y monto_reclamado.

        Returns:
            Hash SHA-256 en hexadecimal.
        """
        rut = (datos.rut_cliente or "").strip()
        numero_operacion = str(datos.numero_operacion or "").strip()

        valor_monto = datos.monto_reclamado
        if isinstance(valor_monto, (int, float)):
            # Normaliza int/float al mismo formato para que representen el mismo hash
            monto = f"{float(valor_monto):.2f}"
        else:
            # Valor no numérico (ej. PENDIENTE_REVISION): usar tal cual
            monto = str(valor_monto or "").strip()

        contenido = f"{rut}|{numero_operacion}|{monto}"
        hash_dedup = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

        logger.debug("Hash de deduplicación calculado: %s", hash_dedup)
        return hash_dedup

    def existe_en_excel(self, hash_dedup: str, ruta_excel: Path) -> str | None:
        """
        Verifica si un hash de deduplicación ya existe en output/casos.xlsx.

        Args:
            hash_dedup: hash a buscar.
            ruta_excel: ruta al archivo casos.xlsx.

        Returns:
            El id_caso del registro original si el hash ya existe,
            o None si no existe (o si el archivo aún no existe).
        """
        if not ruta_excel.exists():
            logger.info("No existe %s aún; no hay duplicados posibles", ruta_excel)
            return None

        try:
            libro = openpyxl.load_workbook(ruta_excel, read_only=True, data_only=True)
        except (OSError, InvalidFileException) as error:
            logger.error("No se pudo abrir %s: %s", ruta_excel, error)
            return None

        try:
            hoja = libro.active
            filas = hoja.iter_rows(values_only=True)

            try:
                encabezados = next(filas)
            except StopIteration:
                logger.warning("%s está vacío", ruta_excel)
                return None

            try:
                indice_hash = encabezados.index("hash_dedup")
                indice_id_caso = encabezados.index("id_caso")
            except ValueError as error:
                logger.error(
                    "Columnas requeridas no encontradas en %s: %s", ruta_excel, error
                )
                return None

            for fila in filas:
                if fila[indice_hash] == hash_dedup:
                    id_caso_original = fila[indice_id_caso]
                    logger.info(
                        "Hash %s ya existe (id_caso original: %s)",
                        hash_dedup,
                        id_caso_original,
                    )
                    return str(id_caso_original)

            return None
        finally:
            libro.close()
