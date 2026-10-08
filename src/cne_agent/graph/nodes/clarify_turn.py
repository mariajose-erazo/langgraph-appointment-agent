"""Respuesta determinista para turnos que necesitan aclaracion."""

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from cne_agent.graph.state import ConversationContext, ConversationState
from cne_agent.interpretation.normalizer import (
    NormalizationIssue,
    NormalizationIssueCode,
    NormalizationResult,
    NormalizationStatus,
)


def clarify_turn(
    state: ConversationState,
    runtime: Runtime[ConversationContext],
) -> dict[str, list[AIMessage]]:
    result = state.get("normalization_result")
    if (
        not isinstance(result, NormalizationResult)
        or result.status is not NormalizationStatus.NEEDS_CLARIFICATION
    ):
        raise ValueError("clarify_turn exige NEEDS_CLARIFICATION")

    questions = [_question(issue, runtime.context) for issue in result.issues]
    unique_questions = list(dict.fromkeys(questions))
    return {"messages": [AIMessage(content=" ".join(unique_questions))]}


def _question(issue: NormalizationIssue, context: ConversationContext) -> str:
    raw = f'“{issue.raw_text}”' if issue.raw_text else "esa expresion"
    if issue.code is NormalizationIssueCode.AMBIGUOUS_TIME:
        return f"Para {raw}, ¿te refieres a la mañana o a la tarde?"
    if issue.code is NormalizationIssueCode.AMBIGUOUS_PROFESSIONAL:
        names = _candidate_names(issue.candidate_ids, context)
        if names:
            return f"¿Te refieres a {_join_options(names)}?"
        return "¿Puedes indicar el nombre completo de la profesional?"
    if issue.code is NormalizationIssueCode.AMBIGUOUS_SERVICE:
        names = _candidate_names(issue.candidate_ids, context)
        if names:
            return f"¿Te refieres a {_join_options(names)}?"
        return "¿Puedes precisar qué servicio deseas?"
    if issue.code is NormalizationIssueCode.UNKNOWN_PROFESSIONAL:
        return "No pude identificar esa profesional. ¿Puedes indicar su nombre completo?"
    if issue.code is NormalizationIssueCode.UNKNOWN_SERVICE:
        return "No pude identificar ese servicio. ¿Puedes precisar cuál deseas?"
    if issue.code is NormalizationIssueCode.AMBIGUOUS_DATE:
        return f"¿Puedes precisar la fecha de {raw}?"
    if issue.code is NormalizationIssueCode.UNSUPPORTED_DATE:
        return "¿Puedes indicar una fecha más precisa?"
    if issue.code is NormalizationIssueCode.UNSUPPORTED_TIME:
        return "¿Puedes indicar una hora exacta, incluyendo mañana o tarde?"
    if issue.code is NormalizationIssueCode.UNSUPPORTED_REMOVAL:
        return "¿Puedes aclarar si deseas solo retiro o retiro junto con otro servicio?"
    if issue.code is NormalizationIssueCode.INPUT_AMBIGUITY:
        return "¿Puedes aclarar ese dato de la solicitud?"
    return "¿Puedes precisar ese dato para continuar con la solicitud?"


def _candidate_names(
    candidate_ids: tuple[str, ...],
    context: ConversationContext,
) -> list[str]:
    professionals = {
        entry.canonical_id: entry.display_name
        for entry in context.get("professional_catalog", ())
    }
    services = {
        entry.canonical_id: entry.names[0]
        for entry in context.get("service_catalog", ())
        if entry.names
    }
    return [
        professionals.get(candidate_id) or services.get(candidate_id)
        for candidate_id in candidate_ids
        if professionals.get(candidate_id) or services.get(candidate_id)
    ]


def _join_options(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" o {values[-1]}"
