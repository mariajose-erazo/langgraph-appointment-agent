from collections.abc import Callable

from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from cne_agent.appointments.readiness import (
    AppointmentReadinessResult,
    AppointmentReadinessStatus,
    MissingAppointmentField,
)
from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.state import ConversationContext, ConversationState
from cne_agent.graph.nodes.success_response import success_response
from cne_agent.interpretation.models import TurnIntent, TurnInterpretation


def missing_data_response(
    state: ConversationState,
    runtime: Runtime[ConversationContext],
) -> dict[str, list[AIMessage]]:
    readiness = state.get("appointment_readiness")
    request = state.get("appointment_request")
    if (
        not isinstance(readiness, AppointmentReadinessResult)
        or readiness.status is not AppointmentReadinessStatus.MISSING_INFORMATION
    ):
        raise ValueError("missing_data_response exige MISSING_INFORMATION")
    if not isinstance(request, AppointmentRequest):
        raise TypeError("appointment_request es obligatorio")
    question = _question(readiness, request)
    interpretation = state.get("turn_interpretation")
    if (
        isinstance(interpretation, TurnInterpretation)
        and (
            TurnIntent.INFORMATION_QUERY in interpretation.intents
            or interpretation.information_queries
        )
    ):
        informational = success_response(state, runtime)["messages"][0].content
        return {"messages": [AIMessage(content=f"{informational} {question}")]}
    return {"messages": [AIMessage(content=question)]}


def _question(readiness, request):
    fields = readiness.missing_fields
    service = _service_name(request)
    if fields == (MissingAppointmentField.TIME,):
        return f"¿A qué hora te gustaría el {service}?"
    if (
        MissingAppointmentField.DATE in fields
        and MissingAppointmentField.TIME in fields
    ):
        return f"¿Para qué fecha y hora te gustaría el {service}?"
    if fields == (MissingAppointmentField.PROFESSIONAL,):
        return "¿Prefieres alguna profesional o puede ser cualquiera?"
    labels = {
        MissingAppointmentField.SERVICES: "qué servicio deseas",
        MissingAppointmentField.DATE: "para qué fecha",
        MissingAppointmentField.TIME: "a qué hora",
        MissingAppointmentField.PROFESSIONAL: "si prefieres alguna profesional o puede ser cualquiera",
    }
    details = [labels[field] for field in fields]
    if len(details) == 1:
        joined = details[0]
    else:
        joined = ", ".join(details[:-1]) + f" y {details[-1]}"
    return f"¿Puedes indicarme {joined}?"


def _service_name(request):
    if len(request.services) == 1:
        service = request.services[0]
        return service.variant_text or service.family.value
    return "servicio"
