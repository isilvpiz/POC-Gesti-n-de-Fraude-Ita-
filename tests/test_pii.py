"""Tests para agente1/pii.py."""

import logging

import pytest

from agente1.pii import RUT_INVALIDO, FiltroPII, configurar_filtro_pii, enmascarar_rut


# === enmascarar_rut ===

@pytest.mark.parametrize(
    "rut, esperado",
    [
        ("12.345.678-9", "12.***.**8-9"),
        ("1.234.567-8", "1.***.**7-8"),
        ("12345678-9", "12.***.**8-9"),
        ("12.345.678-k", "12.***.**8-K"),
        ("  12.345.678-9  ", "12.***.**8-9"),
    ],
)
def test_enmascarar_rut_formatos_validos(rut: str, esperado: str) -> None:
    assert enmascarar_rut(rut) == esperado


@pytest.mark.parametrize("rut", ["", "no es un rut", "123", "12.345.678", "12.345.678-99"])
def test_enmascarar_rut_invalido(rut: str) -> None:
    assert enmascarar_rut(rut) == RUT_INVALIDO


# === FiltroPII ===

@pytest.fixture
def logger_con_filtro() -> logging.Logger:
    logger = logging.getLogger("test_pii_logger")
    logger.setLevel(logging.INFO)
    configurar_filtro_pii(logger)
    yield logger
    logger.filters.clear()


def test_filtro_enmascara_rut_en_mensaje(logger_con_filtro: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="test_pii_logger"):
        logger_con_filtro.info("Procesando reclamo de RUT 12.345.678-9")

    assert "12.345.678-9" not in caplog.text
    assert "12.***.**8-9" in caplog.text


def test_filtro_enmascara_rut_en_argumentos(logger_con_filtro: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="test_pii_logger"):
        logger_con_filtro.info("RUT recibido: %s", "12.345.678-9")

    assert "12.345.678-9" not in caplog.text
    assert "12.***.**8-9" in caplog.text


def test_filtro_no_modifica_mensajes_sin_rut(logger_con_filtro: logging.Logger, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="test_pii_logger"):
        logger_con_filtro.info("Correo procesado correctamente")

    assert "Correo procesado correctamente" in caplog.text


def test_configurar_filtro_pii_no_duplica(logger_con_filtro: logging.Logger) -> None:
    configurar_filtro_pii(logger_con_filtro)

    filtros_pii = [f for f in logger_con_filtro.filters if isinstance(f, FiltroPII)]
    assert len(filtros_pii) == 1
