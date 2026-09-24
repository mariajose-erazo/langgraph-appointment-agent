"""Foto vigente de una solicitud de cita y cambios de un turno.

Este módulo representa y valida datos. No fusiona parches, no resuelve
lenguaje natural y no consulta la agenda.

Limitación V1: no existe una operación para modificar solo la variante de
un servicio ya presente. Una frase como «que sea semipermanente» no tiene
representación aquí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import StrEnum
from typing import Generic, TypeVar


T = TypeVar("T")


class ServiceFamily(StrEnum):
    MANICURE = "manicure"
    PEDICURE = "pedicure"
    UNRESOLVED = "unresolved"


class ProfessionalStatus(StrEnum):
    UNSPECIFIED = "unspecified"
    ANY = "any"
    PREFERRED = "preferred"


class ProfessionalFallback(StrEnum):
    NONE = "none"
    ANY = "any"


class ProfessionalResolution(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class DateStatus(StrEnum):
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown"
    EXACT = "exact"
    AMBIGUOUS = "ambiguous"


class TimeStatus(StrEnum):
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown"
    EXACT = "exact"
    PERIOD = "period"


class TimePeriod(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class RemovalStatus(StrEnum):
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown"
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"


class RemovalRole(StrEnum):
    UNSPECIFIED = "unspecified"
    ADDON = "addon"
    ONLY = "only"


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} debe contener texto")


def _require_tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} debe ser una tupla")


def _service_identity(mention: ServiceMention) -> tuple[object, ...]:
    if mention.family is ServiceFamily.UNRESOLVED:
        return ("raw_text", mention.raw_text)
    return ("family", mention.family, mention.variant_text)


def _professional_identity(
    mention: ProfessionalMention,
) -> tuple[object, ...]:
    if mention.resolution_status is ProfessionalResolution.RESOLVED:
        return ("canonical_id", mention.canonical_id)
    return ("raw_text", mention.raw_text)


def _ensure_unique(
    items: tuple[object, ...],
    identity,
    message: str,
) -> None:
    seen: set[tuple[object, ...]] = set()
    for item in items:
        key = identity(item)
        if key in seen:
            raise ValueError(message)
        seen.add(key)


@dataclass(frozen=True)
class Omitted:
    """El turno no mencionó este dato."""


@dataclass(frozen=True)
class Clear:
    """Reinicia un bloque completo o vacía una lista."""


@dataclass(frozen=True)
class SetValue(Generic[T]):
    """Sustituye un dato por un valor nuevo."""

    value: T

    def __post_init__(self) -> None:
        if self.value is None:
            raise ValueError("SetValue no acepta None")


@dataclass(frozen=True)
class ServiceMention:
    raw_text: str
    family: ServiceFamily
    variant_text: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.raw_text, "raw_text")
        if not isinstance(self.family, ServiceFamily):
            raise TypeError("family debe ser ServiceFamily")
        if self.variant_text is not None:
            _require_text(self.variant_text, "variant_text")
        if (
            self.family is ServiceFamily.UNRESOLVED
            and self.variant_text is not None
        ):
            raise ValueError(
                "un servicio unresolved no puede tener variant_text"
            )


@dataclass(frozen=True)
class ServiceSelector:
    """Identidad de un servicio que una operación REMOVE quiere señalar.

    Manicure y pedicure se identifican con familia y variante. Un servicio
    unresolved se identifica solo con raw_text. La variante vacía significa
    el servicio sin variante, no cualquier variante.
    """

    family: ServiceFamily | None = None
    variant_text: str | None = None
    raw_text: str | None = None

    def __post_init__(self) -> None:
        classified = self.family in {
            ServiceFamily.MANICURE,
            ServiceFamily.PEDICURE,
        }
        has_raw_text = self.raw_text is not None
        if classified and has_raw_text:
            raise ValueError(
                "el selector de servicio no puede mezclar familia y raw_text"
            )
        if classified:
            if self.variant_text is not None:
                _require_text(self.variant_text, "variant_text")
            return
        if has_raw_text:
            if self.family is not None or self.variant_text is not None:
                raise ValueError(
                    "el selector unresolved solo puede contener raw_text"
                )
            _require_text(self.raw_text, "raw_text")
            return
        raise ValueError("el selector de servicio no tiene identidad")


@dataclass(frozen=True)
class SetServiceOperation:
    mentions: tuple[ServiceMention, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.mentions, "mentions")
        if not self.mentions:
            raise ValueError("SET requiere al menos un servicio")
        for mention in self.mentions:
            if not isinstance(mention, ServiceMention):
                raise TypeError("SET solo acepta ServiceMention")
        _ensure_unique(
            self.mentions,
            _service_identity,
            "SET contiene servicios duplicados",
        )


@dataclass(frozen=True)
class AddServiceOperation:
    mention: ServiceMention

    def __post_init__(self) -> None:
        if not isinstance(self.mention, ServiceMention):
            raise TypeError("ADD solo acepta ServiceMention")


@dataclass(frozen=True)
class RemoveServiceOperation:
    selector: ServiceSelector

    def __post_init__(self) -> None:
        if not isinstance(self.selector, ServiceSelector):
            raise TypeError("REMOVE solo acepta ServiceSelector")


ServiceOperation = (
    SetServiceOperation
    | AddServiceOperation
    | RemoveServiceOperation
    | Clear
)


@dataclass(frozen=True)
class ProfessionalMention:
    raw_text: str
    canonical_id: str | None
    resolution_status: ProfessionalResolution

    def __post_init__(self) -> None:
        _require_text(self.raw_text, "raw_text")
        if not isinstance(self.resolution_status, ProfessionalResolution):
            raise TypeError(
                "resolution_status debe ser ProfessionalResolution"
            )
        if self.resolution_status is ProfessionalResolution.RESOLVED:
            if self.canonical_id is None:
                raise ValueError(
                    "canonical_id es obligatorio cuando la profesional está resuelta"
                )
            _require_text(self.canonical_id, "canonical_id")
            return
        if self.canonical_id is not None:
            raise ValueError(
                "canonical_id debe estar vacío cuando la profesional no está resuelta"
            )


@dataclass(frozen=True)
class ProfessionalSelector:
    """Identidad de una profesional que REMOVE quiere señalar.

    Una profesional resuelta se indica con canonical_id. Una unresolved se
    indica con raw_text. Este módulo no busca ni compara alias.
    """

    canonical_id: str | None = None
    raw_text: str | None = None

    def __post_init__(self) -> None:
        has_canonical_id = self.canonical_id is not None
        has_raw_text = self.raw_text is not None
        if has_canonical_id == has_raw_text:
            raise ValueError(
                "el selector profesional debe tener una sola identidad"
            )
        if has_canonical_id:
            _require_text(self.canonical_id, "canonical_id")
            return
        _require_text(self.raw_text, "raw_text")


@dataclass(frozen=True)
class SetRankOperation:
    mentions: tuple[ProfessionalMention, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.mentions, "mentions")
        if not self.mentions:
            raise ValueError("SET requiere al menos una profesional")
        for mention in self.mentions:
            if not isinstance(mention, ProfessionalMention):
                raise TypeError("SET solo acepta ProfessionalMention")
        _ensure_unique(
            self.mentions,
            _professional_identity,
            "SET contiene profesionales duplicadas",
        )


@dataclass(frozen=True)
class AddRankOperation:
    mention: ProfessionalMention

    def __post_init__(self) -> None:
        if not isinstance(self.mention, ProfessionalMention):
            raise TypeError("ADD solo acepta ProfessionalMention")


@dataclass(frozen=True)
class RemoveRankOperation:
    selector: ProfessionalSelector

    def __post_init__(self) -> None:
        if not isinstance(self.selector, ProfessionalSelector):
            raise TypeError("REMOVE solo acepta ProfessionalSelector")


RankOperation = (
    SetRankOperation
    | AddRankOperation
    | RemoveRankOperation
    | Clear
)


@dataclass(frozen=True)
class ProfessionalPreference:
    status: ProfessionalStatus = ProfessionalStatus.UNSPECIFIED
    ranked: tuple[ProfessionalMention, ...] = ()
    fallback: ProfessionalFallback = ProfessionalFallback.NONE

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProfessionalStatus):
            raise TypeError("status debe ser ProfessionalStatus")
        if not isinstance(self.fallback, ProfessionalFallback):
            raise TypeError("fallback debe ser ProfessionalFallback")
        _require_tuple(self.ranked, "ranked")
        for mention in self.ranked:
            if not isinstance(mention, ProfessionalMention):
                raise TypeError("ranked solo acepta ProfessionalMention")
        _ensure_unique(
            self.ranked,
            _professional_identity,
            "hay profesionales duplicadas",
        )
        if self.status in {
            ProfessionalStatus.UNSPECIFIED,
            ProfessionalStatus.ANY,
        }:
            if self.ranked or self.fallback is not ProfessionalFallback.NONE:
                raise ValueError(
                    "unspecified y any exigen ranking vacío y fallback none"
                )
            return
        if not self.ranked:
            raise ValueError("preferred exige al menos una profesional")


@dataclass(frozen=True)
class DatePreference:
    status: DateStatus = DateStatus.UNSPECIFIED
    expression: str | None = None
    resolved_date: date | None = None
    alternatives: tuple[date, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, DateStatus):
            raise TypeError("status debe ser DateStatus")
        _require_tuple(self.alternatives, "alternatives")
        if self.expression is not None:
            _require_text(self.expression, "expression")
        if self.resolved_date is not None and type(self.resolved_date) is not date:
            raise TypeError("resolved_date debe ser datetime.date")
        for alternative in self.alternatives:
            if type(alternative) is not date:
                raise TypeError("alternatives solo acepta datetime.date")
        if self.status is DateStatus.UNSPECIFIED:
            if (
                self.expression is not None
                or self.resolved_date is not None
                or self.alternatives
            ):
                raise ValueError(
                    "unspecified no admite expresión, fecha ni alternativas"
                )
            return
        if self.status is DateStatus.UNKNOWN:
            if self.resolved_date is not None or self.alternatives:
                raise ValueError(
                    "unknown no admite fecha resuelta ni alternativas"
                )
            return
        if self.status is DateStatus.EXACT:
            if self.resolved_date is None or self.alternatives:
                raise ValueError(
                    "exact exige resolved_date y no admite alternativas"
                )
            return
        alternatives_are_distinct = len(set(self.alternatives)) == len(
            self.alternatives
        )
        if (
            self.resolved_date is not None
            or len(self.alternatives) < 2
            or not alternatives_are_distinct
        ):
            raise ValueError(
                "ambiguous exige al menos dos fechas distintas y ninguna fecha única"
            )


@dataclass(frozen=True)
class TimePreference:
    status: TimeStatus = TimeStatus.UNSPECIFIED
    expression: str | None = None
    resolved_time: time | None = None
    period: TimePeriod | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, TimeStatus):
            raise TypeError("status debe ser TimeStatus")
        if self.expression is not None:
            _require_text(self.expression, "expression")
        if self.resolved_time is not None and type(self.resolved_time) is not time:
            raise TypeError("resolved_time debe ser datetime.time")
        if self.period is not None and not isinstance(self.period, TimePeriod):
            raise TypeError("period debe ser TimePeriod")
        if self.status is TimeStatus.UNSPECIFIED:
            if (
                self.expression is not None
                or self.resolved_time is not None
                or self.period is not None
            ):
                raise ValueError(
                    "unspecified no admite expresión, hora ni periodo"
                )
            return
        if self.status is TimeStatus.UNKNOWN:
            if self.resolved_time is not None or self.period is not None:
                raise ValueError("unknown no admite hora resuelta ni periodo")
            return
        if self.status is TimeStatus.EXACT:
            if self.resolved_time is None or self.period is not None:
                raise ValueError("exact exige resolved_time y no admite periodo")
            return
        if self.period is None or self.resolved_time is not None:
            raise ValueError("period exige un periodo y no admite hora resuelta")


@dataclass(frozen=True)
class RemovalPreference:
    status: RemovalStatus = RemovalStatus.UNSPECIFIED
    role: RemovalRole = RemovalRole.UNSPECIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.status, RemovalStatus):
            raise TypeError("status debe ser RemovalStatus")
        if not isinstance(self.role, RemovalRole):
            raise TypeError("role debe ser RemovalRole")
        if self.status is not RemovalStatus.REQUIRED:
            if self.role is not RemovalRole.UNSPECIFIED:
                raise ValueError(
                    "addon y only solo existen cuando el retiro es required"
                )


@dataclass(frozen=True)
class SchedulePreference:
    """Fecha y hora vigentes de la solicitud."""

    date: DatePreference = field(default_factory=DatePreference)
    time: TimePreference = field(default_factory=TimePreference)

    def __post_init__(self) -> None:
        if not isinstance(self.date, DatePreference):
            raise TypeError("date debe ser DatePreference")
        if not isinstance(self.time, TimePreference):
            raise TypeError("time debe ser TimePreference")


@dataclass(frozen=True)
class AppointmentRequest:
    """Foto vigente de lo que el cliente ha expresado."""

    services: tuple[ServiceMention, ...] = ()
    professional: ProfessionalPreference = field(
        default_factory=ProfessionalPreference
    )
    schedule: SchedulePreference = field(default_factory=SchedulePreference)
    removal: RemovalPreference = field(default_factory=RemovalPreference)

    def __post_init__(self) -> None:
        _require_tuple(self.services, "services")
        for mention in self.services:
            if not isinstance(mention, ServiceMention):
                raise TypeError("services solo acepta ServiceMention")
        _ensure_unique(
            self.services,
            _service_identity,
            "hay servicios duplicados",
        )
        if not isinstance(self.professional, ProfessionalPreference):
            raise TypeError("professional debe ser ProfessionalPreference")
        if not isinstance(self.schedule, SchedulePreference):
            raise TypeError("schedule debe ser SchedulePreference")
        if not isinstance(self.removal, RemovalPreference):
            raise TypeError("removal debe ser RemovalPreference")
        if self.removal.role is RemovalRole.ONLY and self.services:
            raise ValueError("role only exige services vacío")
        if self.removal.role is RemovalRole.ADDON and not self.services:
            raise ValueError("role addon exige al menos un servicio")


def _validate_operation_sequence(
    operations: object,
    *,
    set_type: type,
    add_type: type,
    remove_type: type,
    identity,
    duplicate_message: str,
) -> None:
    _require_tuple(operations, "operations")
    if not operations:
        return
    for operation in operations:
        if not isinstance(operation, (set_type, add_type, remove_type, Clear)):
            raise TypeError("la lista contiene una operación desconocida")
    replaces_everything = any(
        isinstance(operation, (set_type, Clear)) for operation in operations
    )
    if replaces_everything:
        if len(operations) != 1:
            raise ValueError(
                "SET y CLEAR deben ser la única operación de la lista"
            )
        return
    seen: set[tuple[object, ...]] = set()
    for operation in operations:
        if not isinstance(operation, add_type):
            continue
        key = identity(operation.mention)
        if key in seen:
            raise ValueError(duplicate_message)
        seen.add(key)


def _validate_block_change(
    change: object,
    preference_type: type,
    unspecified_status: StrEnum,
) -> None:
    if isinstance(change, (Omitted, Clear)):
        return
    if not isinstance(change, SetValue):
        raise TypeError("se esperaba Omitted, SetValue o Clear")
    if not isinstance(change.value, preference_type):
        raise TypeError(f"SetValue debe envolver {preference_type.__name__}")
    if change.value.status is unspecified_status:
        raise ValueError(
            "SetValue no puede envolver un estado unspecified; usa Clear"
        )


@dataclass(frozen=True)
class ProfessionalPreferencePatch:
    """Cambios parciales de la preferencia de profesional."""

    status: Omitted | SetValue[ProfessionalStatus] = field(
        default_factory=Omitted
    )
    ranked_operations: tuple[RankOperation, ...] = ()
    fallback: Omitted | SetValue[ProfessionalFallback] = field(
        default_factory=Omitted
    )

    def __post_init__(self) -> None:
        _validate_status_or_fallback(
            self.status,
            ProfessionalStatus,
            "status",
        )
        _validate_status_or_fallback(
            self.fallback,
            ProfessionalFallback,
            "fallback",
        )
        _validate_operation_sequence(
            self.ranked_operations,
            set_type=SetRankOperation,
            add_type=AddRankOperation,
            remove_type=RemoveRankOperation,
            identity=_professional_identity,
            duplicate_message="la lista repite una profesional",
        )
        if not isinstance(self.status, SetValue):
            return
        if self.status.value in {
            ProfessionalStatus.ANY,
            ProfessionalStatus.UNSPECIFIED,
        }:
            if self.ranked_operations != (Clear(),):
                raise ValueError(
                    "any y unspecified exigen ranked_operations [CLEAR]"
                )
            if (
                not isinstance(self.fallback, SetValue)
                or self.fallback.value is not ProfessionalFallback.NONE
            ):
                raise ValueError(
                    "any y unspecified exigen fallback SetValue(none)"
                )
            return
        if (
            len(self.ranked_operations) != 1
            or not isinstance(self.ranked_operations[0], SetRankOperation)
        ):
            raise ValueError(
                "preferred exige ranked_operations [SET] con al menos una profesional"
            )


def _validate_status_or_fallback(
    change: object,
    value_type: type,
    field_name: str,
) -> None:
    if isinstance(change, Omitted):
        return
    if isinstance(change, Clear):
        raise TypeError(f"{field_name} no usa Clear")
    if not isinstance(change, SetValue):
        raise TypeError(f"{field_name} debe ser Omitted o SetValue")
    if not isinstance(change.value, value_type):
        raise TypeError(f"{field_name} debe envolver {value_type.__name__}")


def _is_exact_clear(operations: tuple[object, ...]) -> bool:
    return len(operations) == 1 and isinstance(operations[0], Clear)


@dataclass(frozen=True)
class AppointmentRequestPatch:
    """Cambios expresados en el turno actual."""

    service_operations: tuple[ServiceOperation, ...] = ()
    professional: ProfessionalPreferencePatch = field(
        default_factory=ProfessionalPreferencePatch
    )
    date: Omitted | SetValue[DatePreference] | Clear = field(
        default_factory=Omitted
    )
    time: Omitted | SetValue[TimePreference] | Clear = field(
        default_factory=Omitted
    )
    removal: Omitted | SetValue[RemovalPreference] | Clear = field(
        default_factory=Omitted
    )

    def __post_init__(self) -> None:
        _validate_operation_sequence(
            self.service_operations,
            set_type=SetServiceOperation,
            add_type=AddServiceOperation,
            remove_type=RemoveServiceOperation,
            identity=_service_identity,
            duplicate_message="la lista repite un servicio",
        )
        if not isinstance(self.professional, ProfessionalPreferencePatch):
            raise TypeError(
                "professional debe ser ProfessionalPreferencePatch"
            )
        _validate_block_change(self.date, DatePreference, DateStatus.UNSPECIFIED)
        _validate_block_change(self.time, TimePreference, TimeStatus.UNSPECIFIED)
        _validate_block_change(
            self.removal,
            RemovalPreference,
            RemovalStatus.UNSPECIFIED,
        )
        if not isinstance(self.removal, SetValue):
            return
        role = self.removal.value.role
        if role is RemovalRole.ONLY and not _is_exact_clear(
            self.service_operations
        ):
            raise ValueError(
                "un retiro only exige service_operations [CLEAR]"
            )
        if role is RemovalRole.ADDON and _is_exact_clear(
            self.service_operations
        ):
            raise ValueError("un retiro addon no puede vaciar los servicios")
