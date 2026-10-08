"""Respuesta conversacional para un turno normalizado exitosamente."""

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from cne_agent.appointments.request import AppointmentRequest
from cne_agent.chains.conversation import create_conversation_chain
from cne_agent.graph.history import trim_conversation_history
from cne_agent.graph.state import ConversationContext, ConversationState
from cne_agent.interpretation.models import TurnInterpretation
from cne_agent.interpretation.normalizer import (
    NormalizationResult,
    NormalizationStatus,
)


def success_response(
    state: ConversationState,
    runtime: Runtime[ConversationContext],
) -> dict[str, list[AIMessage]]:
    request = state.get("appointment_request")
    interpretation = state.get("turn_interpretation")
    result = state.get("normalization_result")
    if not isinstance(request, AppointmentRequest):
        raise TypeError("appointment_request es obligatorio")
    if not isinstance(interpretation, TurnInterpretation):
        raise TypeError("turn_interpretation es obligatorio")
    if (
        not isinstance(result, NormalizationResult)
        or result.status is not NormalizationStatus.SUCCESS
    ):
        raise ValueError("success_response exige SUCCESS")

    messages = state.get("messages", [])
    if not messages:
        raise ValueError("messages no puede estar vacio")
    response = create_conversation_chain().invoke(
        {
            "current_date": runtime.context["current_date"],
            "business_context": runtime.context["business_context"],
            "capabilities_context": runtime.context["capabilities_context"],
            "appointment_context": _format_request(request),
            "interpretation_context": _format_interpretation(interpretation),
            "information_queries": _format_queries(interpretation),
            "history": trim_conversation_history(messages[:-1]),
            "user_input": messages[-1].content,
        }
    )
    return {"messages": [AIMessage(content=response)]}


def _format_request(request: AppointmentRequest) -> str:
    services = ", ".join(
        service.variant_text or service.family.value
        for service in request.services
    ) or "sin servicios indicados"
    professionals = ", ".join(
        professional.raw_text
        for professional in request.professional.ranked
    ) or request.professional.status.value
    date = request.schedule.date.resolved_date or request.schedule.date.status.value
    selected_time = (
        request.schedule.time.resolved_time
        or request.schedule.time.period
        or request.schedule.time.status.value
    )
    return (
        f"servicios: {services}; profesional: {professionals}; "
        f"fecha: {date}; hora: {selected_time}; "
        f"retiro: {request.removal.status.value}/{request.removal.role.value}"
    )


def _format_interpretation(interpretation: TurnInterpretation) -> str:
    intents = ", ".join(intent.value for intent in interpretation.intents)
    return f"intenciones del turno: {intents or 'ninguna'}"


def _format_queries(interpretation: TurnInterpretation) -> str:
    return "\n".join(interpretation.information_queries) or "ninguna"
