"""
Evaluación de la regla de responsabilidad 3DS (Agente 2).

Regla determinista (NO usa Bedrock) — auditabilidad regulatoria.
Ver .kiro/steering/agente2.md para la regla de negocio completa.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from agente1.bedrock_client import PENDIENTE_REVISION
from agente1.config import PLAZO_MAXIMO_RECLAMO_DIAS
from agente2.caso_reader import CasoFraude

logger = logging.getLogger(__name__)

VERSION_REGLA = "3DS-v1.0"

CODIGO_RAZON_SIN_3DS = "Visa 10.4 / MC 4837"

JUSTIFICACION_SIN_3DS = (
    "Comercio sin 3DS en venta no presencial. Responsabilidad del comercio "
    "— Itaú puede disputar a la marca."
)
JUSTIFICACION_CON_3DS = (
    "Comercio con 3DS activo. Liability shift: el emisor asumió el riesgo "
    "al autenticar la transacción."
)
JUSTIFICACION_PRESENCIAL = (
    "Regla 3DS no aplicable a transacciones presenciales. Requiere "
    "evaluación manual (chip/banda, PIN, etc.)."
)
JUSTIFICACION_CAMPO_PENDIENTE = "canal_venta o tiene_3ds en PENDIENTE_REVISION"

ALERTA_FUERA_DE_PLAZO = "FUERA_DE_PLAZO"


@dataclass
class DecisionChargeback:
    """Resultado de evaluar la regla 3DS sobre un CasoFraude."""

    aplica_chargeback: str  # "Sí" | "No" | "—"
    justificacion: str
    codigo_razon: str
    estado_decision: str  # "RESUELTA" | "PENDIENTE_REVISION"
    version_regla: str
    dias_entre_transaccion_y_reclamo: int | None
    alertas: str  # "" o lista separada por comas, ej. "FUERA_DE_PLAZO"


class EvaluadorRegla3DS:
    """Aplica la regla de responsabilidad 3DS (VERSION_REGLA) a un caso."""

    def evaluar(self, caso: CasoFraude) -> DecisionChargeback:
        """
        Evalúa un CasoFraude y retorna la decisión de chargeback.

        Args:
            caso: caso con estado PROCESADO (filtrado por LectorCasos).

        Returns:
            DecisionChargeback con la decisión, justificación y alertas.
        """
        dias = self._calcular_dias(caso.fecha_transaccion, caso.fecha_reclamo)
        alertas = self._calcular_alertas(dias)

        # R2.4: campos críticos pendientes -> PENDIENTE_REVISION
        if caso.canal_venta == PENDIENTE_REVISION or caso.tiene_3ds == PENDIENTE_REVISION:
            return self._decision(
                aplica="—",
                justificacion=JUSTIFICACION_CAMPO_PENDIENTE,
                codigo_razon="",
                estado_decision="PENDIENTE_REVISION",
                dias=dias,
                alertas=alertas,
            )

        # R2.3: presencial -> regla no aplicable
        if caso.canal_venta == "Presencial":
            return self._decision(
                aplica="—",
                justificacion=JUSTIFICACION_PRESENCIAL,
                codigo_razon="",
                estado_decision="PENDIENTE_REVISION",
                dias=dias,
                alertas=alertas,
            )

        # R2.1/R2.2: no presencial
        if caso.canal_venta == "No presencial":
            if caso.tiene_3ds == "No":
                return self._decision(
                    aplica="Sí",
                    justificacion=JUSTIFICACION_SIN_3DS,
                    codigo_razon=CODIGO_RAZON_SIN_3DS,
                    estado_decision="RESUELTA",
                    dias=dias,
                    alertas=alertas,
                )
            if caso.tiene_3ds == "Sí":
                return self._decision(
                    aplica="No",
                    justificacion=JUSTIFICACION_CON_3DS,
                    codigo_razon="",
                    estado_decision="RESUELTA",
                    dias=dias,
                    alertas=alertas,
                )

        # Combinación no contemplada (canal_venta/tiene_3ds con valor inesperado)
        logger.warning(
            "Combinación no contemplada para id_caso=%s: canal_venta=%r, tiene_3ds=%r",
            caso.id_caso,
            caso.canal_venta,
            caso.tiene_3ds,
        )
        return self._decision(
            aplica="—",
            justificacion=(
                f"Combinación no contemplada: canal_venta={caso.canal_venta!r}, "
                f"tiene_3ds={caso.tiene_3ds!r}"
            ),
            codigo_razon="",
            estado_decision="PENDIENTE_REVISION",
            dias=dias,
            alertas=alertas,
        )

    def _decision(
        self,
        aplica: str,
        justificacion: str,
        codigo_razon: str,
        estado_decision: str,
        dias: int | None,
        alertas: list[str],
    ) -> DecisionChargeback:
        return DecisionChargeback(
            aplica_chargeback=aplica,
            justificacion=justificacion,
            codigo_razon=codigo_razon,
            estado_decision=estado_decision,
            version_regla=VERSION_REGLA,
            dias_entre_transaccion_y_reclamo=dias,
            alertas=", ".join(alertas),
        )

    def _calcular_dias(self, fecha_transaccion: str, fecha_reclamo: str) -> int | None:
        """
        Calcula días entre fecha_transaccion y fecha_reclamo (R3.2).

        Returns:
            Días (entero, puede ser negativo si las fechas están invertidas),
            o None si alguna fecha no tiene formato YYYY-MM-DD válido.
        """
        try:
            transaccion = datetime.strptime(fecha_transaccion, "%Y-%m-%d")
            reclamo = datetime.strptime(fecha_reclamo, "%Y-%m-%d")
        except (TypeError, ValueError) as error:
            logger.warning(
                "No se pudo calcular dias_entre_transaccion_y_reclamo "
                "(fecha_transaccion=%r, fecha_reclamo=%r): %s",
                fecha_transaccion,
                fecha_reclamo,
                error,
            )
            return None

        return (reclamo - transaccion).days

    def _calcular_alertas(self, dias: int | None) -> list[str]:
        """Genera alertas según los días calculados (R3.3)."""
        if dias is not None and dias > PLAZO_MAXIMO_RECLAMO_DIAS:
            return [ALERTA_FUERA_DE_PLAZO]
        return []
