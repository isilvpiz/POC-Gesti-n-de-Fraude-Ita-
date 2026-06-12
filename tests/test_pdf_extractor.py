"""Tests para agente1/pdf_extractor.py."""

from pathlib import Path

import pytest

from agente1.pdf_extractor import ExtractorPDF

RUTA_FORMULARIO_001 = Path("input/pdfs/formulario_001.pdf")


@pytest.fixture
def extractor() -> ExtractorPDF:
    return ExtractorPDF()


def test_leer_texto_formulario_001(extractor: ExtractorPDF) -> None:
    texto = extractor.leer_texto(RUTA_FORMULARIO_001)

    assert "RUT Cliente" in texto
    assert "12.345.678-9" in texto
    assert "TiendaOnline Express" in texto
    assert "185.900" in texto


def test_leer_texto_archivo_inexistente(extractor: ExtractorPDF, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extractor.leer_texto(tmp_path / "no_existe.pdf")


def test_leer_texto_archivo_invalido(extractor: ExtractorPDF, tmp_path: Path) -> None:
    archivo_falso = tmp_path / "no_es_pdf.pdf"
    archivo_falso.write_text("esto no es un pdf")

    with pytest.raises(ValueError):
        extractor.leer_texto(archivo_falso)


def test_limpiar_texto_elimina_lineas_vacias_y_espacios(extractor: ExtractorPDF) -> None:
    texto = "  Línea 1  \n\n\n   Línea 2\n\n"

    resultado = extractor.limpiar_texto(texto)

    assert resultado == "Línea 1\nLínea 2"


def test_limpiar_texto_vacio(extractor: ExtractorPDF) -> None:
    assert extractor.limpiar_texto("") == ""


def test_limpiar_texto_elimina_caracteres_de_control(extractor: ExtractorPDF) -> None:
    texto = "Hola\x00Mundo\n\x07RUT: 12.345.678-9"

    resultado = extractor.limpiar_texto(texto)

    assert "\x00" not in resultado
    assert "\x07" not in resultado
    assert "RUT: 12.345.678-9" in resultado


def test_integracion_leer_y_limpiar(extractor: ExtractorPDF) -> None:
    texto = extractor.leer_texto(RUTA_FORMULARIO_001)
    limpio = extractor.limpiar_texto(texto)

    assert "\n\n" not in limpio
    assert "RUT Cliente" in limpio
    assert "12.345.678-9" in limpio
