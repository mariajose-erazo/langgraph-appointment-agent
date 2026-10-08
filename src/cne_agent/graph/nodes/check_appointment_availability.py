from collections.abc import Callable

from langgraph.runtime import Runtime

from cne_agent.appointments.availability import (
    AvailabilityProvider,
    build_schedule_query,
    check_appointment_availability,
)
from cne_agent.appointments.readiness import (
    AppointmentReadinessResult,
    AppointmentReadinessStatus,
)
from cne_agent.appointments.request import AppointmentRequest
from cne_agent.appointments.scheduling import SchedulingPolicy
from cne_agent.graph.state import ConversationContext, ConversationState


def create_check_appointment_availability_node(
    provider: AvailabilityProvider | None,
    policy: SchedulingPolicy,
) -> Callable:
    def node(
        state: ConversationState,
        runtime: Runtime[ConversationContext],
    ) -> dict[str, object]:
        readiness = state.get("appointment_readiness")
        if (
            not isinstance(readiness, AppointmentReadinessResult)
            or readiness.status is not AppointmentReadinessStatus.READY
        ):
            raise ValueError("la consulta de disponibilidad exige READY")
        if provider is None:
            raise RuntimeError("no hay AvailabilityProvider configurado")
        request = state.get("appointment_request")
        if not isinstance(request, AppointmentRequest):
            raise TypeError("appointment_request es obligatorio")
        catalog = runtime.context.get("professional_catalog")
        if catalog is None:
            raise KeyError("falta el contexto obligatorio: professional_catalog")
        query = build_schedule_query(
            request,
            all_professional_ids=tuple(item.canonical_id for item in catalog),
        )
        result = check_appointment_availability(query, provider, policy)
        return {"availability_result": result}

    return node
