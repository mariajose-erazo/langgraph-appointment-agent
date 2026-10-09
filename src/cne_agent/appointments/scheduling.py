"""Pure appointment duration and availability rules."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from enum import StrEnum

from cne_agent.appointments.request import RemovalRole, RemovalStatus


class ExistingAppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ProfessionalScopeKind(StrEnum):
    SPECIFIC = "specific"
    ANY = "any"


class ScheduleBlockKind(StrEnum):
    LUNCH = "lunch"
    ABSENCE = "absence"
    VACATION = "vacation"
    OTHER = "other"


@dataclass(frozen=True)
class ServiceDefinition:
    canonical_id: str
    duration: timedelta
    active: bool = True

    def __post_init__(self) -> None:
        if not self.canonical_id.strip() or self.duration <= timedelta(0):
            raise ValueError("definicion operacional de servicio invalida")


@dataclass(frozen=True)
class ProfessionalScope:
    kind: ProfessionalScopeKind
    professional_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.professional_ids or any(not value.strip() for value in self.professional_ids):
            raise ValueError("el alcance profesional exige IDs")
        if self.kind is ProfessionalScopeKind.SPECIFIC and len(self.professional_ids) != 1:
            raise ValueError("SPECIFIC exige una profesional")


@dataclass(frozen=True)
class ScheduleQuery:
    service_ids: tuple[str, ...]
    requested_date: date
    requested_time: time
    professional_scope: ProfessionalScope
    removal_status: RemovalStatus
    removal_role: RemovalRole


@dataclass(frozen=True)
class ExistingAppointment:
    professional_id: str
    starts_at: datetime
    service_ends_at: datetime
    status: ExistingAppointmentStatus = ExistingAppointmentStatus.SCHEDULED

    def __post_init__(self) -> None:
        _validate_interval(self.starts_at, self.service_ends_at)


@dataclass(frozen=True)
class ScheduleBlock:
    professional_id: str
    starts_at: datetime
    ends_at: datetime
    kind: ScheduleBlockKind = ScheduleBlockKind.LUNCH

    def __post_init__(self) -> None:
        _validate_interval(self.starts_at, self.ends_at)
        if not isinstance(self.kind, ScheduleBlockKind):
            raise TypeError("kind debe ser ScheduleBlockKind")
        if (
            self.kind is ScheduleBlockKind.LUNCH
            and self.ends_at - self.starts_at != timedelta(minutes=60)
        ):
            raise ValueError("el bloqueo de almuerzo debe durar 60 minutos")


@dataclass(frozen=True)
class ScheduleSnapshot:
    professional_ids: tuple[str, ...]
    appointments: tuple[ExistingAppointment, ...] = ()
    schedule_blocks: tuple[ScheduleBlock, ...] = ()
    closed_dates: frozenset[date] = frozenset()


@dataclass(frozen=True)
class SchedulingPolicy:
    service_definitions: tuple[ServiceDefinition, ...]
    timezone: tzinfo = timezone(timedelta(hours=-5), "America/Bogota")
    opens_at: time = time(8)
    closes_at: time = time(18)
    buffer: timedelta = timedelta(minutes=10)
    addon_removal_duration: timedelta = timedelta(minutes=15)
    independent_removal_service_id: str = "removal-independent"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class UnavailabilityReason(StrEnum):
    CLOSED_DAY = "closed_day"
    OUTSIDE_BUSINESS_HOURS = "outside_business_hours"
    LUNCH_BLOCK = "lunch_block"
    SCHEDULE_BLOCK = "schedule_block"
    APPOINTMENT_CONFLICT = "appointment_conflict"
    NO_PROFESSIONAL_AVAILABLE = "no_professional_available"


@dataclass(frozen=True)
class AvailabilityOption:
    professional_id: str
    starts_at: datetime
    service_ends_at: datetime
    occupied_until: datetime
    service_duration: timedelta
    buffer_duration: timedelta


@dataclass(frozen=True)
class AvailabilityResult:
    status: AvailabilityStatus
    requested_start: datetime
    service_duration: timedelta
    available_options: tuple[AvailabilityOption, ...] = ()
    unavailable_professional_ids: tuple[str, ...] = ()
    reason: UnavailabilityReason | None = None
    alternatives: tuple[AvailabilityOption, ...] = ()

    def __post_init__(self) -> None:
        if self.status is AvailabilityStatus.AVAILABLE:
            if not self.available_options or self.reason is not None:
                raise ValueError("AVAILABLE exige opciones y no admite motivo")
        elif self.available_options or self.reason is None:
            raise ValueError("UNAVAILABLE exige motivo y no admite opciones")


def calculate_service_duration(query: ScheduleQuery, policy: SchedulingPolicy) -> timedelta:
    definitions = {item.canonical_id: item for item in policy.service_definitions}
    ids = query.service_ids
    if query.removal_role is RemovalRole.ONLY:
        ids = (policy.independent_removal_service_id,)
    if not ids:
        raise RuntimeError("la consulta no contiene servicios operacionales")
    total = timedelta()
    for service_id in ids:
        definition = definitions.get(service_id)
        if definition is None or not definition.active:
            raise RuntimeError(f"falta definicion operacional activa: {service_id}")
        total += definition.duration
    if query.removal_role is RemovalRole.ADDON:
        total += policy.addon_removal_duration
    return total


def evaluate_availability(
    query: ScheduleQuery,
    snapshot: ScheduleSnapshot,
    policy: SchedulingPolicy,
) -> AvailabilityResult:
    duration = calculate_service_duration(query, policy)
    start = datetime.combine(query.requested_date, query.requested_time, policy.timezone)
    service_end = start + duration
    occupied_until = service_end + policy.buffer
    requested_ids = set(query.professional_scope.professional_ids)
    snapshot_ids = set(snapshot.professional_ids)
    if query.professional_scope.kind is ProfessionalScopeKind.SPECIFIC:
        if not requested_ids <= snapshot_ids:
            raise RuntimeError("el snapshot no contiene la profesional especifica")
        candidates = tuple(sorted(requested_ids))
    else:
        if not snapshot_ids <= requested_ids:
            raise RuntimeError("el snapshot contiene profesionales no solicitadas")
        candidates = tuple(sorted(snapshot_ids))

    if query.requested_date.weekday() == 6 or query.requested_date in snapshot.closed_dates:
        return _unavailable(start, duration, candidates, UnavailabilityReason.CLOSED_DAY)
    opening = datetime.combine(query.requested_date, policy.opens_at, policy.timezone)
    closing = datetime.combine(query.requested_date, policy.closes_at, policy.timezone)
    if start < opening or service_end > closing:
        return _unavailable(
            start, duration, candidates, UnavailabilityReason.OUTSIDE_BUSINESS_HOURS
        )

    available: list[AvailabilityOption] = []
    unavailable: list[str] = []
    reasons: list[UnavailabilityReason] = []
    for professional_id in candidates:
        reason = _conflict_reason(
            professional_id, start, occupied_until, snapshot, policy.buffer
        )
        if reason is None:
            available.append(
                AvailabilityOption(
                    professional_id,
                    start,
                    service_end,
                    occupied_until,
                    duration,
                    policy.buffer,
                )
            )
        else:
            unavailable.append(professional_id)
            reasons.append(reason)
    if available:
        return AvailabilityResult(
            AvailabilityStatus.AVAILABLE,
            start,
            duration,
            tuple(available),
            tuple(unavailable),
        )
    reason = (
        reasons[0]
        if reasons and len(set(reasons)) == 1
        else UnavailabilityReason.NO_PROFESSIONAL_AVAILABLE
    )
    return _unavailable(start, duration, tuple(unavailable), reason)


def _conflict_reason(professional_id, start, occupied_until, snapshot, buffer):
    for block in snapshot.schedule_blocks:
        if block.professional_id == professional_id and _overlaps(
            start, occupied_until, block.starts_at, block.ends_at
        ):
            return (
                UnavailabilityReason.LUNCH_BLOCK
                if block.kind is ScheduleBlockKind.LUNCH
                else UnavailabilityReason.SCHEDULE_BLOCK
            )
    for appointment in snapshot.appointments:
        if (
            appointment.professional_id == professional_id
            and appointment.status is not ExistingAppointmentStatus.CANCELLED
            and _overlaps(
                start,
                occupied_until,
                appointment.starts_at,
                appointment.service_ends_at + buffer,
            )
        ):
            return UnavailabilityReason.APPOINTMENT_CONFLICT
    return None


def _overlaps(first_start, first_end, second_start, second_end):
    return first_start < second_end and second_start < first_end


def _validate_interval(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
        raise ValueError("intervalo de agenda invalido")


def _unavailable(start, duration, ids, reason):
    return AvailabilityResult(
        AvailabilityStatus.UNAVAILABLE,
        start,
        duration,
        unavailable_professional_ids=tuple(ids),
        reason=reason,
    )
