"""Routing determinista posterior a la normalizacion."""

from cne_agent.graph.state import ConversationState
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
    if (
        TurnIntent.INFORMATION_QUERY in interpretation.intents
        or bool(interpretation.information_queries)
    ):
        return "success_information"
    return "success_conversation"
