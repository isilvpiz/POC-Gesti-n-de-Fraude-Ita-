"""Tests para agente1/email_reader.py."""

import shutil
from pathlib import Path

import pytest

from agente1 import email_reader as email_reader_module
from agente1.email_reader import DatosCorreo, LectorCorreo

RUTA_CASO_001 = Path("input/emails/caso_001.eml")


@pytest.fixture
def lector() -> LectorCorreo:
    return LectorCorreo()


@pytest.fixture
def directorio_emails(tmp_path: Path) -> Path:
    """Copia caso_001.eml a un directorio temporal para no mutar los fixtures."""
    destino = tmp_path / "emails"
    destino.mkdir()
    shutil.copy(RUTA_CASO_001, destino / RUTA_CASO_001.name)
    return destino


@pytest.fixture
def patch_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirige PDFS_DIR y PROCESADOS_DIR del módulo a carpetas temporales."""
    pdfs_dir = tmp_path / "pdfs"
    procesados_dir = tmp_path / "emails" / "procesados"
    monkeypatch.setattr(email_reader_module, "PDFS_DIR", pdfs_dir)
    monkeypatch.setattr(email_reader_module, "PROCESADOS_DIR", procesados_dir)
    return {"pdfs": pdfs_dir, "procesados": procesados_dir}


def test_escanear_directorio_encuentra_eml(lector: LectorCorreo, directorio_emails: Path) -> None:
    archivos = lector.escanear_directorio(directorio_emails)

    assert len(archivos) == 1
    assert archivos[0].name == "caso_001.eml"


def test_escanear_directorio_inexistente(lector: LectorCorreo, tmp_path: Path) -> None:
    archivos = lector.escanear_directorio(tmp_path / "no_existe")

    assert archivos == []


def test_parsear_correo_caso_001(lector: LectorCorreo, directorio_emails: Path) -> None:
    ruta = directorio_emails / "caso_001.eml"

    datos = lector.parsear_correo(ruta)

    assert isinstance(datos, DatosCorreo)
    assert "María González" in datos.asunto
    assert "Reclamo Fraude" in datos.asunto
    assert datos.remitente == "maria.gonzalez@gmail.com"
    assert datos.fecha is not None
    assert datos.fecha.year == 2026
    assert "RUT: 12.345.678-9" in datos.cuerpo
    assert datos.ruta_pdf is None


def test_parsear_correo_archivo_inexistente(lector: LectorCorreo, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        lector.parsear_correo(tmp_path / "no_existe.eml")


def test_extraer_adjunto_pdf(
    lector: LectorCorreo, directorio_emails: Path, patch_dirs: dict[str, Path]
) -> None:
    ruta = directorio_emails / "caso_001.eml"
    datos = lector.parsear_correo(ruta)

    ruta_pdf = lector.extraer_adjunto_pdf(datos)

    assert ruta_pdf is not None
    assert ruta_pdf.exists()
    assert ruta_pdf.name == "formulario_reclamo_001.pdf"
    assert ruta_pdf.read_bytes().startswith(b"%PDF")
    assert datos.ruta_pdf == ruta_pdf


def test_mover_procesado(
    lector: LectorCorreo, directorio_emails: Path, patch_dirs: dict[str, Path]
) -> None:
    ruta = directorio_emails / "caso_001.eml"

    lector.mover_procesado(ruta)

    destino = patch_dirs["procesados"] / "caso_001.eml"
    assert destino.exists()
    assert not ruta.exists()
