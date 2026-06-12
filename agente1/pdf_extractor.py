"""
Extractor de texto desde formularios PDF de reclamo (Agente 1).

Lee el texto plano de un PDF y lo normaliza/limpia para su posterior
envío a Bedrock (extracción de campos estructurados).
"""

import logging
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)


class ExtractorPDF:
    """Extrae y limpia texto de formularios PDF de reclamo de fraude."""

    def leer_texto(self, ruta_pdf: Path) -> str:
        """
        Lee y concatena el texto de todas las páginas de un PDF.

        Args:
            ruta_pdf: ruta al archivo PDF.

        Returns:
            Texto extraído del PDF (todas las páginas, separadas por
            salto de línea). Si una página falla, se omite su texto
            y se registra una advertencia.

        Raises:
            FileNotFoundError: si el archivo no existe.
            ValueError: si el PDF no puede abrirse/leerse.
        """
        if not ruta_pdf.exists():
            logger.error("El archivo PDF no existe: %s", ruta_pdf)
            raise FileNotFoundError(f"El archivo PDF no existe: {ruta_pdf}")

        try:
            lector = PdfReader(str(ruta_pdf))
        except (PdfReadError, OSError) as error:
            logger.error("No se pudo abrir el PDF %s: %s", ruta_pdf.name, error)
            raise ValueError(f"No se pudo abrir el PDF {ruta_pdf.name}") from error

        textos_paginas: list[str] = []
        for numero, pagina in enumerate(lector.pages, start=1):
            try:
                texto_pagina = pagina.extract_text() or ""
            except Exception as error:  # pypdf puede lanzar distintos errores según el PDF
                logger.warning(
                    "Error al extraer texto de la página %d de %s: %s",
                    numero,
                    ruta_pdf.name,
                    error,
                )
                texto_pagina = ""
            textos_paginas.append(texto_pagina)

        texto_completo = "\n".join(textos_paginas)
        logger.info(
            "Texto extraído de %s: %d caracter(es), %d página(s)",
            ruta_pdf.name,
            len(texto_completo),
            len(lector.pages),
        )
        return texto_completo

    def limpiar_texto(self, texto: str) -> str:
        """
        Normaliza y limpia el texto extraído de un PDF.

        Aplica normalización Unicode (NFKC), elimina caracteres de
        control, recorta espacios por línea y descarta líneas vacías.

        Args:
            texto: texto crudo extraído del PDF.

        Returns:
            Texto limpio, listo para enviar a Bedrock.
        """
        if not texto:
            return ""

        texto_normalizado = unicodedata.normalize("NFKC", texto)

        # Eliminar caracteres de control (excepto salto de línea)
        texto_normalizado = "".join(
            caracter
            for caracter in texto_normalizado
            if caracter == "\n" or not unicodedata.category(caracter).startswith("C")
        )

        lineas = [linea.strip() for linea in texto_normalizado.splitlines()]
        lineas_no_vacias = [linea for linea in lineas if linea]

        texto_limpio = "\n".join(lineas_no_vacias)
        logger.debug(
            "Texto limpiado: %d -> %d caracter(es)", len(texto), len(texto_limpio)
        )
        return texto_limpio
