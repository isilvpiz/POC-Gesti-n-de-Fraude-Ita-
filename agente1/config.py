"""
Configuración general del Agente 1 - Procesamiento de Correos de Fraude.

Carga variables de entorno desde .env y expone las constantes de
configuración utilizadas por el resto de los módulos. Incluye
validación de las variables requeridas.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# === AWS / Bedrock ===
AWS_PROFILE: str = os.getenv("AWS_PROFILE", "default")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0"
)
BEDROCK_MAX_TOKENS: int = int(os.getenv("BEDROCK_MAX_TOKENS", "1000"))

# Modo demo: usa un extractor heurístico (regex sobre el PDF) en vez de
# Bedrock real. Permite correr run_pipeline.py sin AWS_PROFILE.
# Ver agente1/heuristic_extractor.py — NO es parte del design.md original.
USE_MOCK_BEDROCK: bool = os.getenv("USE_MOCK_BEDROCK", "false").strip().lower() in (
    "true",
    "1",
    "yes",
)

# === Directorios locales ===
INPUT_EMAIL_DIR: Path = Path(os.getenv("INPUT_EMAIL_DIR", "input/emails"))
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))

PDFS_DIR: Path = INPUT_EMAIL_DIR.parent / "pdfs"
PROCESADOS_DIR: Path = INPUT_EMAIL_DIR / "procesados"
LOGS_DIR: Path = OUTPUT_DIR / "logs"
CASOS_EXCEL_PATH: Path = OUTPUT_DIR / "casos.xlsx"
DECISIONES_EXCEL_PATH: Path = OUTPUT_DIR / "decisiones.xlsx"

# === Regla de negocio ===
PLAZO_MAXIMO_RECLAMO_DIAS: int = int(os.getenv("PLAZO_MAXIMO_RECLAMO_DIAS", "30"))

# === Logging ===
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

_NIVELES_LOG_VALIDOS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def validar_configuracion() -> None:
    """
    Valida que las variables de configuración requeridas sean correctas.

    Verifica tipos, valores permitidos y existencia de directorios de
    entrada. Se debe llamar al inicio de la ejecución (main.py).

    Raises:
        ValueError: si alguna variable obligatoria falta o es inválida.
    """
    errores: list[str] = []

    if not AWS_PROFILE:
        errores.append("AWS_PROFILE no puede estar vacío")

    if not AWS_REGION:
        errores.append("AWS_REGION no puede estar vacío")

    if not BEDROCK_MODEL_ID:
        errores.append("BEDROCK_MODEL_ID no puede estar vacío")

    if BEDROCK_MAX_TOKENS <= 0:
        errores.append("BEDROCK_MAX_TOKENS debe ser mayor a 0")

    if PLAZO_MAXIMO_RECLAMO_DIAS <= 0:
        errores.append("PLAZO_MAXIMO_RECLAMO_DIAS debe ser mayor a 0")

    if LOG_LEVEL.upper() not in _NIVELES_LOG_VALIDOS:
        errores.append(f"LOG_LEVEL inválido: {LOG_LEVEL}")

    if not INPUT_EMAIL_DIR.exists():
        errores.append(f"INPUT_EMAIL_DIR no existe: {INPUT_EMAIL_DIR}")

    if not PDFS_DIR.exists():
        errores.append(f"Directorio de PDFs no existe: {PDFS_DIR}")

    if errores:
        for error in errores:
            logger.error("Error de configuración: %s", error)
        raise ValueError(f"Configuración inválida: {'; '.join(errores)}")

    # Crear directorios de salida si no existen
    PROCESADOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Configuración validada correctamente")
