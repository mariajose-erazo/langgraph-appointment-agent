"""Inicialización única de la solicitud acumulada de un thread."""

from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.state import ConversationState


def initialize_appointment_request(
    state: ConversationState,
) -> dict[str, AppointmentRequest]:
    """Crea la solicitud inicial sin sobrescribir una solicitud existente."""

    if state.get("appointment_request") is not None:
        return {}
    return {"appointment_request": AppointmentRequest()}
