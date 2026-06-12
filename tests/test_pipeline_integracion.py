"""
T6: Test de integración del pipeline completo Agente 1 -> Agente 2.

Procesa los 4 .eml reales (caso_001-004) con ClienteBedrock mockeado
(sin AWS), genera output/casos.xlsx (Agente 1) y luego output/decisiones.xlsx
(Agente 2), verificando los resultados esperados:

  - caso_001 -> Agente1=PROCESADO, Agente2 aplica_chargeback="Sí"
  - caso_002 -> Agente1=PROCESADO, Agente2 aplica_chargeback="No"
  - caso_003 -> Agente1=PENDIENTE_REVISION (no llega a Agente 2)
  - caso_004 -> Agente1=PROCESADO (presencial), Agente2 estado_decision=PENDIENTE_REVISION
"""

import shutil
from pathlib import Path

import openpyxl
import pytest

from agente1 import email_reader as email_reader_module
from agente1 import main as agente1_main_module
from agente1.bedrock_client import PENDIENTE_REVISION, DatosReclamo
from agente1.dedup import Deduplicador
from agente1.email_reader import LectorCorreo
from agente1.excel_writer import EscritorCasos
from agente1.main import procesar_correo
from agente1.pdf_extractor import ExtractorPDF
from agente2 import main as agente2_main_module
from agente2.main import ejecutar as ejecutar_agente2

RUTA_EMAILS = Path("input/emails")


def _datos(**overrides) -> DatosReclamo:
    valores = {
        "rut_cliente": "12.345.678-9",
        "nombre_cliente": "María González Fuentes",
        "numero_tarjeta": "4521",
        "monto_reclamado": 185900,
        "moneda": "CLP",
        "fecha_transaccion": "2026-05-20",
        "fecha_reclamo": "2026-05-25",
        "nombre_comercio": "TiendaOnline Express Ltda.",
        "canal_venta": "No presencial",
        "tiene_3ds": "No",
        "tipo_fraude": "Compra no reconocida por internet",
        "descripcion_reclamo": "No reconozco esta compra.",
        "numero_operacion": "OP-2026-001-789456",
    }
    valores.update(overrides)
    return DatosReclamo(**valores)


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker) -> dict[str, Path]:
    emails_dir = tmp_path / "emails"
    pdfs_dir = tmp_path / "pdfs"
    procesados_dir = emails_dir / "procesados"
    casos_excel = tmp_path / "output" / "casos.xlsx"
    decisiones_excel = tmp_path / "output" / "decisiones.xlsx"

    emails_dir.mkdir()

    monkeypatch.setattr(email_reader_module, "PDFS_DIR", pdfs_dir)
    monkeypatch.setattr(email_reader_module, "PROCESADOS_DIR", procesados_dir)
    monkeypatch.setattr(agente1_main_module, "CASOS_EXCEL_PATH", casos_excel)
    monkeypatch.setattr(agente2_main_module, "CASOS_EXCEL_PATH", casos_excel)
    monkeypatch.setattr(agente2_main_module, "DECISIONES_EXCEL_PATH", decisiones_excel)
    mocker.patch.object(agente2_main_module, "configurar_logging")

    for nombre in ("caso_001.eml", "caso_002.eml", "caso_003.eml", "caso_004.eml"):
        shutil.copy(RUTA_EMAILS / nombre, emails_dir / nombre)

    return {
        "emails": emails_dir,
        "casos": casos_excel,
        "decisiones": decisiones_excel,
    }


def _filas(ruta: Path) -> list[dict]:
    libro = openpyxl.load_workbook(ruta)
    encabezados, *registros = libro.active.iter_rows(values_only=True)
    return [dict(zip(encabezados, fila)) for fila in registros]


def test_pipeline_completo_4_correos(entorno: dict[str, Path], mocker) -> None:
    cliente_bedrock = mocker.MagicMock()
    cliente_bedrock.extraer_datos_reclamo.side_effect = [
        _datos(numero_operacion="OP-001", canal_venta="No presencial", tiene_3ds="No"),
        _datos(numero_operacion="OP-002", canal_venta="No presencial", tiene_3ds="Sí"),
        _datos(numero_operacion="OP-003", nombre_comercio=PENDIENTE_REVISION),
        _datos(numero_operacion="OP-004", canal_venta="Presencial", tiene_3ds="No",
               fecha_transaccion="2026-04-10", fecha_reclamo="2026-06-02"),
    ]

    lector = LectorCorreo()
    dependencias = {
        "lector": lector,
        "extractor_pdf": ExtractorPDF(),
        "cliente_bedrock": cliente_bedrock,
        "deduplicador": Deduplicador(),
        "escritor": EscritorCasos(),
    }

    # --- Agente 1 ---
    estados_agente1 = [
        procesar_correo(ruta, **dependencias)
        for ruta in lector.escanear_directorio(entorno["emails"])
    ]

    assert estados_agente1 == ["PROCESADO", "PROCESADO", "PENDIENTE_REVISION", "PROCESADO"]

    casos = _filas(entorno["casos"])
    assert [c["archivo_origen"] for c in casos] == [
        "caso_001.eml",
        "caso_002.eml",
        "caso_003.eml",
        "caso_004.eml",
    ]
    assert [c["estado"] for c in casos] == estados_agente1

    # --- Agente 2 ---
    resumen_agente2 = ejecutar_agente2()

    # caso_001 (chargeback Sí) y caso_004 (presencial, pendiente) son PROCESADO -> 2 evaluados
    # caso_002 (con 3DS, chargeback No) tambien es PROCESADO -> total real = 3
    assert resumen_agente2["total"] == 3
    assert resumen_agente2["chargeback_si"] == 1  # caso_001
    assert resumen_agente2["chargeback_no"] == 1  # caso_002
    assert resumen_agente2["pendientes"] == 1  # caso_004 (presencial)

    decisiones = _filas(entorno["decisiones"])
    decisiones_por_caso = {
        c["archivo_origen"]: d
        for c, d in zip(
            [c for c in casos if c["estado"] == "PROCESADO"], decisiones
        )
    }

    assert decisiones_por_caso["caso_001.eml"]["aplica_chargeback"] == "Sí"
    assert decisiones_por_caso["caso_001.eml"]["estado_decision"] == "RESUELTA"

    assert decisiones_por_caso["caso_002.eml"]["aplica_chargeback"] == "No"
    assert decisiones_por_caso["caso_002.eml"]["estado_decision"] == "RESUELTA"

    assert decisiones_por_caso["caso_004.eml"]["aplica_chargeback"] == "—"
    assert decisiones_por_caso["caso_004.eml"]["estado_decision"] == "PENDIENTE_REVISION"
    assert decisiones_por_caso["caso_004.eml"]["alertas"] == "FUERA_DE_PLAZO"
    assert decisiones_por_caso["caso_004.eml"]["dias_entre_transaccion_y_reclamo"] == 53

    # caso_003 nunca llega a Agente 2 (PENDIENTE_REVISION en Agente 1)
    assert "caso_003.eml" not in decisiones_por_caso
