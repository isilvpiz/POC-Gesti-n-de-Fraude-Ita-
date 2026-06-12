"""Tests para agente2/caso_reader.py."""

from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pytest

from agente1.excel_writer import COLUMNAS, EscritorCasos
from agente2.caso_reader import CasoFraude, LectorCasos


@dataclass
class DatosReclamoFalso:
    rut_cliente: str = "12.345.678-9"
    nombre_cliente: str = "María González Fuentes"
    numero_tarjeta: str = "4521"
    monto_reclamado: float = 185900
    moneda: str = "CLP"
    fecha_transaccion: str = "2026-05-20"
    fecha_reclamo: str = "2026-05-25"
    nombre_comercio: str = "TiendaOnline Express Ltda."
    canal_venta: str = "No presencial"
    tiene_3ds: str = "No"
    tipo_fraude: str = "Compra no reconocida por internet"
    descripcion_reclamo: str = "No reconozco esta compra"
    numero_operacion: str = "OP-2026-001-789456"


@dataclass
class DatosCorreoFalso:
    ruta_original: Path


@pytest.fixture
def lector() -> LectorCasos:
    return LectorCasos()


# === leer_casos ===

def test_leer_casos_archivo_no_existe(lector: LectorCasos, tmp_path: Path) -> None:
    assert lector.leer_casos(tmp_path / "casos.xlsx") == []


def test_leer_casos_archivo_vacio(lector: LectorCasos, tmp_path: Path) -> None:
    ruta = tmp_path / "casos.xlsx"
    openpyxl.Workbook().save(ruta)

    assert lector.leer_casos(ruta) == []


def test_leer_casos_encabezados_incorrectos(lector: LectorCasos, tmp_path: Path) -> None:
    ruta = tmp_path / "casos.xlsx"
    libro = openpyxl.Workbook()
    libro.active.append(["col_a", "col_b"])
    libro.save(ruta)

    assert lector.leer_casos(ruta) == []


def test_leer_casos_lee_registros(lector: LectorCasos, tmp_path: Path) -> None:
    ruta = tmp_path / "casos.xlsx"
    escritor = EscritorCasos()
    correo = DatosCorreoFalso(ruta_original=Path("input/emails/caso_001.eml"))

    id_caso = escritor.escribir_caso(
        datos=DatosReclamoFalso(),
        correo=correo,
        hash_dedup="hash-1",
        estado="PROCESADO",
        ruta_excel=ruta,
    )

    casos = lector.leer_casos(ruta)

    assert len(casos) == 1
    caso = casos[0]
    assert isinstance(caso, CasoFraude)
    assert caso.id_caso == id_caso
    assert caso.rut_cliente == "12.345.678-9"
    assert caso.monto_reclamado == 185900
    assert caso.canal_venta == "No presencial"
    assert caso.tiene_3ds == "No"
    assert caso.estado == "PROCESADO"
    assert caso.id_caso_original == ""


# === filtrar_procesables ===

def test_filtrar_procesables(lector: LectorCasos, tmp_path: Path) -> None:
    ruta = tmp_path / "casos.xlsx"
    escritor = EscritorCasos()
    correo = DatosCorreoFalso(ruta_original=Path("input/emails/caso_001.eml"))

    escritor.escribir_caso(DatosReclamoFalso(), correo, "h1", "PROCESADO", ruta)
    escritor.escribir_caso(DatosReclamoFalso(), correo, "h2", "PENDIENTE_REVISION", ruta)
    escritor.escribir_caso(DatosReclamoFalso(), correo, "h3", "ERROR", ruta)
    escritor.escribir_caso(
        DatosReclamoFalso(), correo, "h4", "DUPLICADO", ruta, id_caso_original="caso-h1"
    )
    escritor.escribir_caso(DatosReclamoFalso(), correo, "h5", "PROCESADO", ruta)

    casos = lector.leer_casos(ruta)
    procesables = lector.filtrar_procesables(casos)

    assert len(casos) == 5
    assert len(procesables) == 2
    assert all(c.estado == "PROCESADO" for c in procesables)


def test_filtrar_procesables_sin_casos(lector: LectorCasos) -> None:
    assert lector.filtrar_procesables([]) == []
