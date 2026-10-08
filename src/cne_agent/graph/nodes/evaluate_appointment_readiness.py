from cne_agent.appointments.readiness import evaluate_appointment_readiness
from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.state import ConversationState
from cne_agent.appointments.scheduling import SchedulingPolicy


def create_evaluate_appointment_readiness_node(policy: SchedulingPolicy):
    def node(state: ConversationState) -> dict[str, object]:
        request = state.get("appointment_request")
        if not isinstance(request, AppointmentRequest):
            raise TypeError("appointment_request es obligatorio")
        return {
            "appointment_readiness": evaluate_appointment_readiness(
                request,
                service_definitions=policy.service_definitions,
                independent_removal_service_id=policy.independent_removal_service_id,
            )
        }

    return node
