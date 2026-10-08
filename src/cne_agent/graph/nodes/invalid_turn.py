"""Respuesta determinista para cambios semanticamente invalidos."""

from langchain_core.messages import AIMessage

from cne_agent.graph.state import ConversationState
from cne_agent.interpretation.normalizer import (
    NormalizationIssue,
    NormalizationIssueCode,
    NormalizationResult,
    NormalizationStatus,
)


def invalid_turn(state: ConversationState) -> dict[str, list[AIMessage]]:
    result = state.get("normalization_result")
    if (
        not isinstance(result, NormalizationResult)
        or result.status is not NormalizationStatus.INVALID
    ):
        raise ValueError("invalid_turn exige INVALID")
    explanations = list(dict.fromkeys(_explanation(issue) for issue in result.issues))
    content = "No pude aplicar esos cambios. " + " ".join(explanations)
    return {"messages": [AIMessage(content=content)]}


def _explanation(issue: NormalizationIssue) -> str:
    if issue.code is NormalizationIssueCode.CONFLICTING_CHANGES:
        return "Hay indicaciones incompatibles para el mismo dato; ¿cuál deseas conservar?"
    if issue.code is NormalizationIssueCode.INCOHERENT_SERVICE_VALUES:
        return "Los servicios indicados no coinciden entre sí; ¿puedes confirmar cuáles deseas?"
    if issue.code is NormalizationIssueCode.INCOMPATIBLE_WITH_CURRENT_REQUEST:
        return "La combinación no es compatible con la solicitud actual; ¿qué opción deseas mantener?"
    return "La combinación indicada no es válida; ¿puedes reformularla?"
