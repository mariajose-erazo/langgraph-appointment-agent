"""Inicialización única de la solicitud acumulada de un thread."""

from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.state import ConversationState


def initialize_appointment_request(
    state: ConversationState,
) -> dict[str, object]:
    """Crea la solicitud inicial sin sobrescribir una solicitud existente."""

    updates: dict[str, object] = {
        "appointment_readiness": None,
        "availability_result": None,
    }
    if state.get("appointment_request") is None:
        updates["appointment_request"] = AppointmentRequest()
    return updates
