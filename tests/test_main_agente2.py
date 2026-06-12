"""Tests para agente2/main.py."""

import uuid
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pytest

from agente1.excel_writer import EscritorCasos
from agente2 import main as main_module
from agente2.main import ejecutar


@dataclass
class DatosReclamoFalso:
    rut_cliente: str = "12.345.678-9"
    nombre_cliente: str = "María González Fuentes"
    numero_tarjeta: str = "4521"
    monto_reclamado: float = 185900
    moneda: str = "CLP"
    fecha_transaccion: str = "2026-05-01"
    fecha_reclamo: str = "2026-05-15"
    nombre_comercio: str = "TiendaOnline Express Ltda."
    canal_venta: str = "No presencial"
    tiene_3ds: str = "No"
    tipo_fraude: str = "Compra no reconocida por internet"
    descripcion_reclamo: str = "No reconozco esta compra"
    numero_operacion: str = "OP-1"


@dataclass
class DatosCorreoFalso:
    ruta_original: Path


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker) -> dict[str, Path]:
    ruta_casos = tmp_path / "casos.xlsx"
    ruta_decisiones = tmp_path / "decisiones.xlsx"

    monkeypatch.setattr(main_module, "CASOS_EXCEL_PATH", ruta_casos)
    monkeypatch.setattr(main_module, "DECISIONES_EXCEL_PATH", ruta_decisiones)
    mocker.patch.object(main_module, "configurar_logging")

    return {"casos": ruta_casos, "decisiones": ruta_decisiones}


def _escribir_caso(ruta: Path, estado: str, **overrides) -> None:
    escritor = EscritorCasos()
    correo = DatosCorreoFalso(ruta_original=Path("input/emails/caso.eml"))
    escritor.escribir_caso(
        datos=DatosReclamoFalso(**overrides),
        correo=correo,
        hash_dedup=f"hash-{uuid.uuid4()}",
        estado=estado,
        ruta_excel=ruta,
    )


def test_ejecutar_sin_casos_xlsx(entorno: dict[str, Path]) -> None:
    resumen = ejecutar()

    assert resumen == {
        "total": 0,
        "chargeback_si": 0,
        "chargeback_no": 0,
        "pendientes": 0,
        "fuera_de_plazo": 0,
    }
    assert not entorno["decisiones"].exists()


def test_ejecutar_con_casos_mixtos(entorno: dict[str, Path]) -> None:
    ruta_casos = entorno["casos"]

    # 1) PROCESADO, no presencial + sin 3DS -> chargeback Sí
    _escribir_caso(ruta_casos, "PROCESADO", canal_venta="No presencial", tiene_3ds="No")

    # 2) PROCESADO, no presencial + con 3DS -> chargeback No
    _escribir_caso(ruta_casos, "PROCESADO", canal_venta="No presencial", tiene_3ds="Sí")

    # 3) PROCESADO, presencial -> pendiente
    _escribir_caso(ruta_casos, "PROCESADO", canal_venta="Presencial", tiene_3ds="No")

    # 4) PROCESADO, fuera de plazo (no presencial + sin 3DS, >30 dias)
    _escribir_caso(
        ruta_casos,
        "PROCESADO",
        canal_venta="No presencial",
        tiene_3ds="No",
        fecha_transaccion="2026-01-01",
        fecha_reclamo="2026-03-01",
    )

    # 5-7) Excluidos: PENDIENTE_REVISION, ERROR, DUPLICADO
    _escribir_caso(ruta_casos, "PENDIENTE_REVISION", canal_venta="No presencial", tiene_3ds="No")
    _escribir_caso(ruta_casos, "ERROR", canal_venta="No presencial", tiene_3ds="No")
    _escribir_caso(ruta_casos, "DUPLICADO", canal_venta="No presencial", tiene_3ds="No")

    resumen = ejecutar()

    assert resumen["total"] == 4
    assert resumen["chargeback_si"] == 2  # casos 1 y 4
    assert resumen["chargeback_no"] == 1  # caso 2
    assert resumen["pendientes"] == 1  # caso 3 (presencial)
    assert resumen["fuera_de_plazo"] == 1  # caso 4

    libro = openpyxl.load_workbook(entorno["decisiones"])
    filas = list(libro.active.iter_rows(values_only=True))
    assert len(filas) == 5  # encabezado + 4 decisiones


def test_ejecutar_resumen_solo_procesados(entorno: dict[str, Path]) -> None:
    ruta_casos = entorno["casos"]

    _escribir_caso(ruta_casos, "ERROR", canal_venta="No presencial", tiene_3ds="No")
    _escribir_caso(ruta_casos, "PENDIENTE_REVISION", canal_venta="No presencial", tiene_3ds="No")

    resumen = ejecutar()

    assert resumen["total"] == 0
    assert not entorno["decisiones"].exists()
