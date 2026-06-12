"""
Protección de datos personales (PII) para Agente 1.

Provee funciones de enmascaramiento de RUT y un filtro de logging que
evita exponer RUTs sin enmascarar en los logs (PCI-DSS / cumplimiento).

Reglas obligatorias (ver steering general):
  - NUNCA loguear: nombre_cliente, RUT sin enmascarar, texto completo del PDF.
  - numero_tarjeta: solo últimos 4 dígitos en cualquier almacenamiento.
"""

import logging
import re

logger = logging.getLogger(__name__)

RUT_INVALIDO = "RUT_INVALIDO"

_PATRON_RUT_COMPLETO = re.compile(r"^(\d{1,2})\.?(\d{3})\.?(\d{3})-?([0-9kK])$")
_PATRON_RUT_EN_TEXTO = re.compile(r"\b(\d{1,2})\.(\d{3})\.(\d{3})-([0-9kK])\b")


def enmascarar_rut(rut: str) -> str:
    """
    Enmascara un RUT chileno para uso en logs.

    El primer grupo de dígitos se mantiene visible, el grupo intermedio
    se enmascara por completo y del último grupo solo se muestra el
    último dígito. El dígito verificador se mantiene visible.

    Ejemplo:
        "12.345.678-9" -> "12.***.**8-9"
        "1.234.567-8"  -> "1.***.**7-8"

    Args:
        rut: RUT en formato "XX.XXX.XXX-X", "XXXXXXXX-X" o sin guion.

    Returns:
        RUT enmascarado en formato "XX.***.**X-X", o RUT_INVALIDO si el
        valor no tiene un formato de RUT reconocible.
    """
    if not rut:
        return RUT_INVALIDO

    coincidencia = _PATRON_RUT_COMPLETO.fullmatch(rut.strip())
    if not coincidencia:
        return RUT_INVALIDO

    primer_grupo, grupo_medio, ultimo_grupo, digito_verificador = coincidencia.groups()

    grupo_medio_enmascarado = "*" * len(grupo_medio)
    ultimo_grupo_enmascarado = "*" * (len(ultimo_grupo) - 1) + ultimo_grupo[-1]

    return (
        f"{primer_grupo}.{grupo_medio_enmascarado}."
        f"{ultimo_grupo_enmascarado}-{digito_verificador.upper()}"
    )


class FiltroPII(logging.Filter):
    """
    Filtro de logging que enmascara RUTs en formato XX.XXX.XXX-X
    presentes en mensajes y argumentos de log.

    Esta es una capa de defensa adicional: el código NO debe loguear
    RUTs sin enmascarar, nombres completos ni el texto del PDF.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._enmascarar_texto(record.msg)

        if record.args:
            record.args = tuple(
                self._enmascarar_texto(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )

        return True

    @staticmethod
    def _enmascarar_texto(texto: str) -> str:
        def _reemplazar(coincidencia: re.Match) -> str:
            return enmascarar_rut(coincidencia.group(0))

        return _PATRON_RUT_EN_TEXTO.sub(_reemplazar, texto)


def configurar_filtro_pii(logger_objetivo: logging.Logger) -> None:
    """
    Agrega FiltroPII al logger indicado, si no está ya presente.

    Args:
        logger_objetivo: logger al que se le aplicará el filtro.
    """
    if not any(isinstance(f, FiltroPII) for f in logger_objetivo.filters):
        logger_objetivo.addFilter(FiltroPII())
