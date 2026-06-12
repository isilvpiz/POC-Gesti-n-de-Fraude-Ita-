"""
Escritura de casos de reclamo de fraude a output/casos.xlsx (Agente 1).

Crea el archivo con sus encabezados si no existe y agrega un registro
por cada correo procesado, con un id_caso (UUID) generado.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Protocol

import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)

# Columnas de output/casos.xlsx.
# Nota: superset de la tabla del steering (que no incluía hash_dedup ni
# id_caso_original) para cubrir R2 (deduplicación) y los 13 campos de
# DatosReclamo definidos en el design de bedrock_client.py.
COLUMNAS = [
    "id_caso",
    "fecha_procesamiento",
    "archivo_origen",
    "hash_dedup",
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
    "descripcion_reclamo",
    "numero_operacion",
    "estado",
    "id_caso_original",
    "notas",
]


class DatosReclamoProtocolo(Protocol):
    """Estructura mínima de DatosReclamo (13 campos) requerida para escribir un caso."""

    rut_cliente: str
    nombre_cliente: str
    numero_tarjeta: str
    monto_reclamado: float
    moneda: str
    fecha_transaccion: str
    fecha_reclamo: str
    nombre_comercio: str
    canal_venta: str
    tiene_3ds: str
    tipo_fraude: str
    descripcion_reclamo: str
    numero_operacion: str


class DatosCorreoProtocolo(Protocol):
    """Estructura mínima de DatosCorreo requerida para escribir un caso."""

    ruta_original: Path


class EscritorCasos:
    """Inicializa y escribe registros en output/casos.xlsx."""

    def inicializar_excel(self, ruta: Path) -> None:
        """
        Crea output/casos.xlsx con sus encabezados si aún no existe.

        Args:
            ruta: ruta al archivo casos.xlsx.
        """
        if ruta.exists():
            return

        ruta.parent.mkdir(parents=True, exist_ok=True)

        libro = Workbook()
        hoja = libro.active
        hoja.title = "casos"
        hoja.append(COLUMNAS)
        libro.save(ruta)

        logger.info("Archivo creado: %s", ruta)

    def escribir_caso(
        self,
        datos: DatosReclamoProtocolo,
        correo: DatosCorreoProtocolo,
        hash_dedup: str,
        estado: str,
        ruta_excel: Path,
        id_caso_original: str | None = None,
        notas: str = "",
    ) -> str:
        """
        Escribe un registro de caso en output/casos.xlsx.

        Crea el archivo con encabezados si no existe (R5.2).

        Args:
            datos: los 13 campos extraídos del reclamo.
            correo: datos del correo de origen (se usa ruta_original para archivo_origen).
            hash_dedup: hash de deduplicación calculado por Deduplicador.
            estado: PROCESADO | PENDIENTE_REVISION | ERROR | DUPLICADO.
            ruta_excel: ruta al archivo casos.xlsx.
            id_caso_original: id_caso del registro original si estado=DUPLICADO.
            notas: observaciones del procesamiento.

        Returns:
            id_caso generado (UUID en formato string).

        Raises:
            ValueError: si el archivo no puede leerse/escribirse.
        """
        self.inicializar_excel(ruta_excel)

        id_caso = str(uuid.uuid4())
        fecha_procesamiento = datetime.now().isoformat()

        fila = [
            id_caso,
            fecha_procesamiento,
            correo.ruta_original.name,
            hash_dedup,
            datos.rut_cliente,
            datos.nombre_cliente,
            datos.numero_tarjeta,
            datos.monto_reclamado,
            datos.moneda,
            datos.fecha_transaccion,
            datos.fecha_reclamo,
            datos.nombre_comercio,
            datos.canal_venta,
            datos.tiene_3ds,
            datos.tipo_fraude,
            datos.descripcion_reclamo,
            datos.numero_operacion,
            estado,
            id_caso_original or "",
            notas,
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

        logger.info("Caso escrito: id_caso=%s, estado=%s", id_caso, estado)
        return id_caso
