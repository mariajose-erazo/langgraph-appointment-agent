"""Routing determinista posterior a la normalizacion."""

from cne_agent.graph.state import ConversationState
from cne_agent.appointments.readiness import (
    AppointmentReadinessResult,
    AppointmentReadinessStatus,
)
from cne_agent.interpretation.models import TurnIntent, TurnInterpretation
from cne_agent.interpretation.normalizer import (
    NormalizationIssueKind,
    NormalizationResult,
    NormalizationStatus,
)


def route_after_normalization(state: ConversationState) -> str:
    """Selecciona una rama semantica sin invocar un modelo de lenguaje."""

    result = state.get("normalization_result")
    if not isinstance(result, NormalizationResult):
        raise TypeError("normalization_result es obligatorio para enrutar")
    if any(
        issue.kind is NormalizationIssueKind.CONFIGURATION
        for issue in result.issues
    ):
        raise RuntimeError("la normalizacion encontro una configuracion invalida")
    if result.status is NormalizationStatus.INVALID:
        return "invalid"
    if result.status is NormalizationStatus.NEEDS_CLARIFICATION:
        return "clarification"
    if result.status is not NormalizationStatus.SUCCESS:
        raise RuntimeError("estado de normalizacion desconocido")

    interpretation = state.get("turn_interpretation")
    if not isinstance(interpretation, TurnInterpretation):
        raise TypeError("turn_interpretation es obligatorio para enrutar")
    return "success"


def route_after_success(state: ConversationState) -> str:
    interpretation = state.get("turn_interpretation")
    if not isinstance(interpretation, TurnInterpretation):
        raise TypeError("turn_interpretation es obligatorio para enrutar")
    operational = {
        TurnIntent.CHECK_AVAILABILITY,
        TurnIntent.BOOK_APPOINTMENT,
    }
    return "readiness" if operational.intersection(interpretation.intents) else "response"


def route_after_readiness(state: ConversationState) -> str:
    result = state.get("appointment_readiness")
    if not isinstance(result, AppointmentReadinessResult):
        raise TypeError("appointment_readiness es obligatorio para enrutar")
    if result.status is AppointmentReadinessStatus.READY:
        return "availability"
    if result.status is AppointmentReadinessStatus.MISSING_INFORMATION:
        return "missing"
    raise RuntimeError("estado de readiness desconocido")
