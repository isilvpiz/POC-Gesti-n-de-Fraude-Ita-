"""
Lector de correos de reclamos de fraude (Agente 1).

Escanea el directorio de entrada en busca de archivos .eml, parsea sus
datos (asunto, remitente, fecha, cuerpo), extrae el formulario PDF
adjunto y mueve los correos procesados a la carpeta de procesados.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from agente1.config import PDFS_DIR, PROCESADOS_DIR

logger = logging.getLogger(__name__)


@dataclass
class DatosCorreo:
    """Datos extraídos de un correo de reclamo de fraude."""

    asunto: str
    remitente: str
    fecha: datetime | None
    cuerpo: str
    ruta_original: Path
    _mensaje: EmailMessage
    ruta_pdf: Path | None = None


class LectorCorreo:
    """Lee y procesa correos de reclamo de fraude desde un directorio local."""

    def escanear_directorio(self, directorio: Path) -> list[Path]:
        """
        Busca archivos .eml en el directorio indicado.

        Args:
            directorio: ruta al directorio de correos.

        Returns:
            Lista de rutas a archivos .eml encontrados, ordenadas por nombre.
            Lista vacía si el directorio no existe.
        """
        if not directorio.exists():
            logger.error("El directorio no existe: %s", directorio)
            return []

        archivos = sorted(directorio.glob("*.eml"))
        logger.info("Se encontraron %d archivo(s) .eml en %s", len(archivos), directorio)
        return archivos

    def parsear_correo(self, ruta: Path) -> DatosCorreo:
        """
        Parsea un archivo .eml y extrae asunto, remitente, fecha y cuerpo.

        Args:
            ruta: ruta al archivo .eml.

        Returns:
            DatosCorreo con la información extraída. El PDF adjunto aún
            no se ha extraído (ruta_pdf=None); usar `extraer_adjunto_pdf`.

        Raises:
            ValueError: si el archivo no puede leerse o parsearse.
        """
        try:
            with open(ruta, "rb") as archivo:
                mensaje = BytesParser(policy=policy.default).parse(archivo)
        except OSError as error:
            logger.error("No se pudo leer el archivo %s: %s", ruta, error)
            raise ValueError(f"No se pudo leer el archivo {ruta}") from error

        asunto = str(mensaje.get("Subject", "")).strip()
        remitente = str(mensaje.get("From", "")).strip()
        fecha = self._parsear_fecha(mensaje.get("Date"))
        cuerpo = self._extraer_cuerpo(mensaje)

        logger.info("Correo parseado: %s (de %s)", ruta.name, remitente)

        return DatosCorreo(
            asunto=asunto,
            remitente=remitente,
            fecha=fecha,
            cuerpo=cuerpo,
            ruta_original=ruta,
            _mensaje=mensaje,
        )

    def _parsear_fecha(self, valor: str | None) -> datetime | None:
        """Convierte el header Date a datetime; retorna None si no es válido."""
        if not valor:
            return None
        try:
            return parsedate_to_datetime(str(valor))
        except (TypeError, ValueError) as error:
            logger.warning("No se pudo parsear la fecha '%s': %s", valor, error)
            return None

    def _extraer_cuerpo(self, mensaje: EmailMessage) -> str:
        """Extrae el cuerpo de texto plano del mensaje."""
        parte_cuerpo = mensaje.get_body(preferencelist=("plain",))
        if parte_cuerpo is None:
            logger.warning("El correo no tiene cuerpo de texto plano")
            return ""
        try:
            return parte_cuerpo.get_content().strip()
        except (LookupError, UnicodeError) as error:
            logger.warning("Error al decodificar el cuerpo: %s", error)
            return ""

    def extraer_adjunto_pdf(self, correo: DatosCorreo) -> Path | None:
        """
        Extrae el primer adjunto PDF del correo a PDFS_DIR.

        Args:
            correo: datos del correo obtenidos de `parsear_correo`.

        Returns:
            Ruta al PDF extraído, o None si el correo no tiene adjunto PDF.
            Si se extrae correctamente, también actualiza `correo.ruta_pdf`.
        """
        for parte in correo._mensaje.iter_attachments():
            if parte.get_content_type() != "application/pdf":
                continue

            nombre = parte.get_filename() or f"{correo.ruta_original.stem}.pdf"

            try:
                contenido = parte.get_content()
            except (LookupError, UnicodeError) as error:
                logger.error(
                    "Error al leer adjunto PDF de %s: %s", correo.ruta_original.name, error
                )
                return None

            PDFS_DIR.mkdir(parents=True, exist_ok=True)
            ruta_pdf = PDFS_DIR / nombre

            try:
                with open(ruta_pdf, "wb") as destino:
                    destino.write(contenido)
            except OSError as error:
                logger.error("No se pudo escribir el PDF %s: %s", ruta_pdf, error)
                return None

            logger.info("PDF extraído: %s", ruta_pdf)
            correo.ruta_pdf = ruta_pdf
            return ruta_pdf

        logger.warning("El correo %s no contiene adjunto PDF", correo.ruta_original.name)
        return None

    def mover_procesado(self, ruta: Path) -> None:
        """
        Mueve un archivo .eml procesado a PROCESADOS_DIR.

        Args:
            ruta: ruta al archivo .eml ya procesado.

        Raises:
            OSError: si el archivo no puede moverse.
        """
        PROCESADOS_DIR.mkdir(parents=True, exist_ok=True)
        destino = PROCESADOS_DIR / ruta.name

        try:
            ruta.rename(destino)
            logger.info("Correo movido a procesados: %s", destino)
        except OSError as error:
            logger.error("No se pudo mover %s a %s: %s", ruta, destino, error)
            raise
