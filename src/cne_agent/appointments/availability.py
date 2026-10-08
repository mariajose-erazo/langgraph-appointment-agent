"""Application boundary for reading schedule data and checking availability."""

from typing import Protocol

from cne_agent.appointments.request import (
    AppointmentRequest,
    ProfessionalStatus,
)
from cne_agent.appointments.scheduling import (
    AvailabilityResult,
    ProfessionalScope,
    ProfessionalScopeKind,
    ScheduleQuery,
    ScheduleSnapshot,
    SchedulingPolicy,
    evaluate_availability,
)


class AvailabilityProvider(Protocol):
    def get_schedule(self, query: ScheduleQuery) -> ScheduleSnapshot: ...


def build_schedule_query(
    request: AppointmentRequest,
    *,
    all_professional_ids: tuple[str, ...],
) -> ScheduleQuery:
    date_value = request.schedule.date.resolved_date
    time_value = request.schedule.time.resolved_time
    if date_value is None or time_value is None:
        raise RuntimeError("la solicitud no esta lista para consultar agenda")
    if request.professional.status is ProfessionalStatus.ANY:
        ids = tuple(sorted(set(all_professional_ids)))
        kind = ProfessionalScopeKind.ANY
    else:
        selected = request.professional.ranked[0].canonical_id
        if selected is None:
            raise RuntimeError("la profesional no tiene identidad canonica")
        ids = (selected,)
        kind = ProfessionalScopeKind.SPECIFIC
    if not ids:
        raise RuntimeError("no hay profesionales activas autorizadas")
    return ScheduleQuery(
        tuple(service.canonical_id for service in request.services if service.canonical_id),
        date_value,
        time_value,
        ProfessionalScope(kind, ids),
        request.removal.status,
        request.removal.role,
    )


def check_appointment_availability(
    query: ScheduleQuery,
    provider: AvailabilityProvider,
    policy: SchedulingPolicy,
) -> AvailabilityResult:
    snapshot = provider.get_schedule(query)
    if not isinstance(snapshot, ScheduleSnapshot):
        raise TypeError("el provider no devolvio ScheduleSnapshot")
    return evaluate_availability(query, snapshot, policy)
