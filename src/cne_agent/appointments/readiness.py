"""Deterministic completeness checks before reading an appointment schedule."""

from dataclasses import dataclass
from enum import StrEnum

from cne_agent.appointments.request import (
    AppointmentRequest,
    DateStatus,
    ProfessionalResolution,
    ProfessionalStatus,
    RemovalRole,
    RemovalStatus,
    ServiceFamily,
    TimeStatus,
)
from cne_agent.appointments.scheduling import ServiceDefinition


class AppointmentReadinessStatus(StrEnum):
    READY = "ready"
    MISSING_INFORMATION = "missing_information"


class MissingAppointmentField(StrEnum):
    SERVICES = "services"
    DATE = "date"
    TIME = "time"
    PROFESSIONAL = "professional"


@dataclass(frozen=True)
class AppointmentReadinessResult:
    status: AppointmentReadinessStatus
    missing_fields: tuple[MissingAppointmentField, ...] = ()

    def __post_init__(self) -> None:
        if self.status is AppointmentReadinessStatus.READY:
            if self.missing_fields:
                raise ValueError("READY no admite campos faltantes")
        elif not self.missing_fields:
            raise ValueError("MISSING_INFORMATION exige campos faltantes")


def evaluate_appointment_readiness(
    request: AppointmentRequest,
    *,
    service_definitions: tuple[ServiceDefinition, ...],
    independent_removal_service_id: str = "removal-independent",
) -> AppointmentReadinessResult:
    """Return missing data without interpreting or mutating the request."""

    if not isinstance(request, AppointmentRequest):
        raise TypeError("request debe ser AppointmentRequest")
    missing: list[MissingAppointmentField] = []

    is_removal_only = (
        request.removal.status is RemovalStatus.REQUIRED
        and request.removal.role is RemovalRole.ONLY
    )
    if not request.services and not is_removal_only:
        missing.append(MissingAppointmentField.SERVICES)
    for service in request.services:
        if service.family is ServiceFamily.UNRESOLVED or service.canonical_id is None:
            raise RuntimeError("la solicitud contiene un servicio no resuelto")

    date_preference = request.schedule.date
    if date_preference.status is DateStatus.UNSPECIFIED:
        missing.append(MissingAppointmentField.DATE)
    elif date_preference.status is not DateStatus.EXACT:
        raise RuntimeError("la fecha no exacta debio bloquear la normalizacion")

    time_preference = request.schedule.time
    if time_preference.status in {TimeStatus.UNSPECIFIED, TimeStatus.PERIOD}:
        missing.append(MissingAppointmentField.TIME)
    elif time_preference.status is not TimeStatus.EXACT:
        raise RuntimeError("la hora no exacta debio bloquear la normalizacion")

    professional = request.professional
    if professional.status is ProfessionalStatus.UNSPECIFIED:
        missing.append(MissingAppointmentField.PROFESSIONAL)
    elif professional.status is ProfessionalStatus.PREFERRED:
        if len(professional.ranked) != 1:
            raise RuntimeError("PREFERRED exige exactamente una profesional")
        selected = professional.ranked[0]
        if (
            selected.resolution_status is not ProfessionalResolution.RESOLVED
            or selected.canonical_id is None
        ):
            raise RuntimeError("la profesional preferida no esta resuelta")
    elif professional.status is not ProfessionalStatus.ANY:
        raise RuntimeError("estado profesional desconocido")

    if missing:
        return AppointmentReadinessResult(
            AppointmentReadinessStatus.MISSING_INFORMATION,
            tuple(missing),
        )

    definitions = {
        definition.canonical_id: definition
        for definition in service_definitions
    }
    required_service_ids = [
        service.canonical_id for service in request.services
    ]
    if is_removal_only:
        required_service_ids = [independent_removal_service_id]
    for service_id in required_service_ids:
        definition = definitions.get(service_id)
        if definition is None or not definition.active:
            raise RuntimeError(
                f"falta definicion operacional activa: {service_id}"
            )
    return AppointmentReadinessResult(AppointmentReadinessStatus.READY)
