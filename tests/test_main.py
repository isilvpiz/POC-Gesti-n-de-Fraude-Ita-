"""
Tests para agente1/main.py (T8: orquestación, T9: integración).

Los tests de integración procesan los .eml reales de input/emails/ con
ClienteBedrock mockeado (sin AWS) y verifican output/casos.xlsx.
"""

import shutil
from email.message import EmailMessage
from pathlib import Path

import openpyxl
import pytest

from agente1 import email_reader as email_reader_module
from agente1 import main as main_module
from agente1.bedrock_client import CAMPOS_OPCIONALES, CAMPOS_REQUERIDOS, PENDIENTE_REVISION, DatosReclamo
from agente1.dedup import Deduplicador
from agente1.email_reader import LectorCorreo
from agente1.excel_writer import EscritorCasos
from agente1.main import _es_monto_numerico, determinar_estado, ejecutar, procesar_correo
from agente1.pdf_extractor import ExtractorPDF

RUTA_EMAILS = Path("input/emails")


def _datos(**overrides) -> DatosReclamo:
    """Construye un DatosReclamo válido, con overrides opcionales."""
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


# === determinar_estado ===

def test_determinar_estado_procesado() -> None:
    estado, notas = determinar_estado(_datos())
    assert estado == "PROCESADO"
    assert notas == ""


def test_determinar_estado_pocos_pendientes() -> None:
    datos = _datos(nombre_comercio=PENDIENTE_REVISION)
    estado, notas = determinar_estado(datos)
    assert estado == "PENDIENTE_REVISION"
    assert "nombre_comercio" in notas


def test_determinar_estado_mas_de_3_pendientes_es_error() -> None:
    datos = _datos(
        rut_cliente=PENDIENTE_REVISION,
        nombre_cliente=PENDIENTE_REVISION,
        numero_tarjeta=PENDIENTE_REVISION,
        moneda=PENDIENTE_REVISION,
    )
    estado, notas = determinar_estado(datos)
    assert estado == "ERROR"
    assert "rut_cliente" in notas


def test_determinar_estado_monto_no_numerico() -> None:
    datos = _datos(monto_reclamado="ciento ochenta mil")
    estado, notas = determinar_estado(datos)
    assert estado == "PENDIENTE_REVISION"
    assert "monto_reclamado" in notas


def test_determinar_estado_tiene_3ds_invalido() -> None:
    datos = _datos(tiene_3ds="Tal vez")
    estado, notas = determinar_estado(datos)
    assert estado == "PENDIENTE_REVISION"
    assert "tiene_3ds" in notas


# === _es_monto_numerico ===

@pytest.mark.parametrize(
    "valor, esperado",
    [(185900, True), (185900.0, True), ("185900", True), ("PENDIENTE_REVISION", False), (None, False)],
)
def test_es_monto_numerico(valor: object, esperado: bool) -> None:
    assert _es_monto_numerico(valor) == esperado


# === Fixtures de entorno temporal ===

@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirige directorios de email_reader y casos.xlsx de main a tmp_path."""
    emails_dir = tmp_path / "emails"
    pdfs_dir = tmp_path / "pdfs"
    procesados_dir = emails_dir / "procesados"
    casos_excel = tmp_path / "output" / "casos.xlsx"

    emails_dir.mkdir()

    monkeypatch.setattr(email_reader_module, "PDFS_DIR", pdfs_dir)
    monkeypatch.setattr(email_reader_module, "PROCESADOS_DIR", procesados_dir)
    monkeypatch.setattr(main_module, "CASOS_EXCEL_PATH", casos_excel)

    return {
        "emails": emails_dir,
        "pdfs": pdfs_dir,
        "procesados": procesados_dir,
        "casos_excel": casos_excel,
    }


@pytest.fixture
def dependencias(mocker):
    """Dependencias reales para LectorCorreo/ExtractorPDF/Deduplicador/EscritorCasos + ClienteBedrock mock."""
    return {
        "lector": LectorCorreo(),
        "extractor_pdf": ExtractorPDF(),
        "deduplicador": Deduplicador(),
        "escritor": EscritorCasos(),
        "cliente_bedrock": mocker.MagicMock(),
    }


def _filas_casos_excel(ruta: Path) -> list[dict]:
    libro = openpyxl.load_workbook(ruta)
    filas = list(libro.active.iter_rows(values_only=True))
    encabezados, *registros = filas
    return [dict(zip(encabezados, fila)) for fila in registros]


# === procesar_correo: sin adjunto PDF (R1.4) ===

def test_procesar_correo_sin_adjunto_es_error(entorno: dict[str, Path], dependencias) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Reclamo sin adjunto"
    msg["From"] = "cliente@example.com"
    msg["Date"] = "Mon, 01 Jun 2026 10:00:00 -0400"
    msg.set_content("Reclamo sin formulario adjunto.")

    ruta_eml = entorno["emails"] / "sin_adjunto.eml"
    ruta_eml.write_bytes(bytes(msg))

    estado = procesar_correo(ruta_eml, **dependencias)

    assert estado == "ERROR"
    dependencias["cliente_bedrock"].extraer_datos_reclamo.assert_not_called()

    filas = _filas_casos_excel(entorno["casos_excel"])
    assert len(filas) == 1
    assert filas[0]["estado"] == "ERROR"
    assert filas[0]["notas"] == "sin adjunto"
    assert (entorno["procesados"] / "sin_adjunto.eml").exists()


# === procesar_correo: caso completo -> PROCESADO ===

def test_procesar_correo_completo_es_procesado(entorno: dict[str, Path], dependencias) -> None:
    ruta_eml = entorno["emails"] / "caso_001.eml"
    shutil.copy(RUTA_EMAILS / "caso_001.eml", ruta_eml)

    dependencias["cliente_bedrock"].extraer_datos_reclamo.return_value = _datos()

    estado = procesar_correo(ruta_eml, **dependencias)

    assert estado == "PROCESADO"
    filas = _filas_casos_excel(entorno["casos_excel"])
    assert filas[0]["estado"] == "PROCESADO"
    assert filas[0]["rut_cliente"] == "12.345.678-9"
    assert (entorno["pdfs"] / "formulario_reclamo_001.pdf").exists()
    assert (entorno["procesados"] / "caso_001.eml").exists()


# === procesar_correo: duplicado ===

def test_procesar_correo_duplicado(entorno: dict[str, Path], dependencias) -> None:
    ruta_1 = entorno["emails"] / "caso_001.eml"
    ruta_3 = entorno["emails"] / "caso_003.eml"
    shutil.copy(RUTA_EMAILS / "caso_001.eml", ruta_1)
    shutil.copy(RUTA_EMAILS / "caso_003.eml", ruta_3)

    dependencias["cliente_bedrock"].extraer_datos_reclamo.return_value = _datos()

    estado_1 = procesar_correo(ruta_1, **dependencias)
    estado_2 = procesar_correo(ruta_3, **dependencias)

    assert estado_1 == "PROCESADO"
    assert estado_2 == "DUPLICADO"

    filas = _filas_casos_excel(entorno["casos_excel"])
    assert len(filas) == 2
    assert filas[1]["estado"] == "DUPLICADO"
    assert filas[0]["id_caso"] in filas[1]["id_caso_original"]


# === T9: integración con los 4 .eml reales ===

def test_integracion_cuatro_correos(entorno: dict[str, Path], dependencias) -> None:
    for nombre in ("caso_001.eml", "caso_002.eml", "caso_003.eml", "caso_004.eml"):
        shutil.copy(RUTA_EMAILS / nombre, entorno["emails"] / nombre)

    datos_caso_001 = _datos(numero_operacion="OP-A")  # PROCESADO
    datos_caso_002 = _datos(nombre_comercio=PENDIENTE_REVISION, numero_operacion="OP-B")  # PENDIENTE_REVISION
    datos_caso_003 = _datos(numero_operacion="OP-A")  # mismo hash que caso_001 -> DUPLICADO
    datos_caso_004 = _datos(
        rut_cliente=PENDIENTE_REVISION,
        nombre_cliente=PENDIENTE_REVISION,
        numero_tarjeta=PENDIENTE_REVISION,
        monto_reclamado=PENDIENTE_REVISION,
        numero_operacion="OP-D",
    )  # 4 pendientes -> ERROR

    dependencias["cliente_bedrock"].extraer_datos_reclamo.side_effect = [
        datos_caso_001,
        datos_caso_002,
        datos_caso_003,
        datos_caso_004,
    ]

    lector = dependencias["lector"]
    estados = [
        procesar_correo(ruta, **dependencias)
        for ruta in lector.escanear_directorio(entorno["emails"])
    ]

    assert estados == ["PROCESADO", "PENDIENTE_REVISION", "DUPLICADO", "ERROR"]

    filas = _filas_casos_excel(entorno["casos_excel"])
    assert [f["estado"] for f in filas] == ["PROCESADO", "PENDIENTE_REVISION", "DUPLICADO", "ERROR"]
    assert [f["archivo_origen"] for f in filas] == [
        "caso_001.eml",
        "caso_002.eml",
        "caso_003.eml",
        "caso_004.eml",
    ]

    # Todos los .eml movidos a procesados/
    for nombre in ("caso_001.eml", "caso_002.eml", "caso_003.eml", "caso_004.eml"):
        assert (entorno["procesados"] / nombre).exists()
        assert not (entorno["emails"] / nombre).exists()

    # 4 PDFs extraídos
    assert len(list(entorno["pdfs"].glob("*.pdf"))) == 4


# === ejecutar(): resumen y manejo de errores por correo ===

def test_ejecutar_resumen_y_continua_ante_error(mocker, monkeypatch: pytest.MonkeyPatch) -> None:
    mocker.patch.object(main_module, "validar_configuracion")
    mocker.patch.object(main_module, "configurar_logging")

    mock_lector_cls = mocker.patch.object(main_module, "LectorCorreo")
    mocker.patch.object(main_module, "ExtractorPDF")
    mocker.patch.object(main_module, "ClienteBedrock")
    mocker.patch.object(main_module, "Deduplicador")
    mocker.patch.object(main_module, "EscritorCasos")

    rutas = [Path("caso_a.eml"), Path("caso_b.eml"), Path("caso_c.eml")]
    mock_lector_cls.return_value.escanear_directorio.return_value = rutas

    # caso_a -> PROCESADO, caso_b -> lanza excepción, caso_c -> DUPLICADO
    mocker.patch.object(
        main_module,
        "procesar_correo",
        side_effect=["PROCESADO", RuntimeError("fallo inesperado"), "DUPLICADO"],
    )

    resumen = ejecutar()

    assert resumen["total"] == 3
    assert resumen["PROCESADO"] == 1
    assert resumen["DUPLICADO"] == 1
    assert resumen["ERROR"] == 1
    assert resumen["PENDIENTE_REVISION"] == 0
