"""Normalización determinista de interpretaciones conversacionales.

El módulo no consulta disponibilidad ni fuentes externas. Los catálogos,
la solicitud vigente y el reloj de referencia son entradas explícitas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum
import re
import unicodedata

from cne_agent.appointments.merge import MergeError, merge_appointment_request
from cne_agent.appointments.request import (
    AddServiceOperation,
    AppointmentRequest,
    AppointmentRequestPatch,
    Clear,
    DatePreference,
    DateStatus,
    ProfessionalFallback,
    ProfessionalMention,
    ProfessionalPreferencePatch,
    ProfessionalResolution,
    ProfessionalStatus,
    RemovalPreference,
    RemovalRole,
    RemovalStatus,
    RemoveServiceOperation,
    ServiceFamily,
    ServiceMention,
    ServiceSelector,
    SetRankOperation,
    SetServiceOperation,
    SetValue,
    TimePeriod,
    TimePreference,
    TimeStatus,
)
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedChange,
    TurnInterpretation,
)


BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


@dataclass(frozen=True)
class ServiceCatalogEntry:
    canonical_id: str
    family: ServiceFamily
    variant_text: str | None
    names: tuple[str, ...]


@dataclass(frozen=True)
class ProfessionalCatalogEntry:
    canonical_id: str
    display_name: str
    aliases: tuple[str, ...] = ()


class NormalizationStatus(StrEnum):
    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID = "invalid"


class NormalizationIssueKind(StrEnum):
    CLARIFICATION = "clarification"
    CONFIGURATION = "configuration"
    CONFLICT = "conflict"
    INVALID = "invalid"


class NormalizationIssueCode(StrEnum):
    INVALID_SERVICE_CATALOG = "invalid_service_catalog"
    INVALID_PROFESSIONAL_CATALOG = "invalid_professional_catalog"
    INVALID_REFERENCE_TIME = "invalid_reference_time"
    INPUT_AMBIGUITY = "input_ambiguity"
    INCOHERENT_SERVICE_VALUES = "incoherent_service_values"
    UNKNOWN_SERVICE = "unknown_service"
    AMBIGUOUS_SERVICE = "ambiguous_service"
    UNKNOWN_PROFESSIONAL = "unknown_professional"
    AMBIGUOUS_PROFESSIONAL = "ambiguous_professional"
    AMBIGUOUS_DATE = "ambiguous_date"
    UNSUPPORTED_DATE = "unsupported_date"
    AMBIGUOUS_TIME = "ambiguous_time"
    UNSUPPORTED_TIME = "unsupported_time"
    UNSUPPORTED_REMOVAL = "unsupported_removal"
    CONFLICTING_CHANGES = "conflicting_changes"
    INCOMPATIBLE_WITH_CURRENT_REQUEST = "incompatible_with_current_request"


class NormalizationNoticeCode(StrEnum):
    DISCARDED_SUGGESTED_ID = "discarded_suggested_id"


@dataclass(frozen=True)
class NormalizationIssue:
    code: NormalizationIssueCode
    kind: NormalizationIssueKind
    field: AppointmentField | None
    description: str
    raw_text: str | None = None
    candidate_ids: tuple[str, ...] = ()
    source_change_index: int | None = None


@dataclass(frozen=True)
class NormalizationNotice:
    code: NormalizationNoticeCode
    field: AppointmentField
    description: str
    raw_text: str | None = None
    discarded_suggested_id: str | None = None
    source_change_index: int | None = None


@dataclass(frozen=True)
class NormalizationResult:
    status: NormalizationStatus
    patch: AppointmentRequestPatch | None
    issues: tuple[NormalizationIssue, ...] = ()
    notices: tuple[NormalizationNotice, ...] = ()

    def __post_init__(self) -> None:
        if self.status is NormalizationStatus.SUCCESS:
            if self.patch is None or self.issues:
                raise ValueError("SUCCESS exige patch y no admite issues")
            return
        if self.patch is not None or not self.issues:
            raise ValueError(
                "un resultado bloqueante exige patch=None y al menos un issue"
            )


@dataclass(frozen=True)
class _Catalogs:
    services_by_name: dict[str, ServiceCatalogEntry]
    services_by_id: dict[str, ServiceCatalogEntry]
    professionals_by_name: dict[str, ProfessionalCatalogEntry]
    professionals_by_id: dict[str, ProfessionalCatalogEntry]


def normalize_turn_interpretation(
    interpretation: TurnInterpretation,
    *,
    current_request: AppointmentRequest,
    service_catalog: tuple[ServiceCatalogEntry, ...],
    professional_catalog: tuple[ProfessionalCatalogEntry, ...],
    reference_at: datetime,
) -> NormalizationResult:
    """Construye un parche completo o devuelve problemas sin parche."""

    configuration_issues, catalogs = _validate_inputs(
        current_request,
        service_catalog,
        professional_catalog,
        reference_at,
    )
    if configuration_issues:
        return _blocked(configuration_issues)
    assert catalogs is not None

    issues = [
        NormalizationIssue(
            code=NormalizationIssueCode.INPUT_AMBIGUITY,
            kind=NormalizationIssueKind.CLARIFICATION,
            field=ambiguity.field,
            description=ambiguity.description,
        )
        for ambiguity in interpretation.ambiguities
    ]
    issues.extend(_find_change_conflicts(interpretation.appointment_changes))
    if issues:
        return _blocked(issues)

    service_operations: list[object] = []
    professional_patch = ProfessionalPreferencePatch()
    date_change: object = None
    time_change: object = None
    removal_change: object = None
    notices: list[NormalizationNotice] = []

    for index, change in enumerate(interpretation.appointment_changes):
        if change.field is AppointmentField.SERVICES:
            operations, found = _normalize_services(
                change,
                index,
                catalogs.services_by_name,
            )
            service_operations.extend(operations)
        elif change.field is AppointmentField.PROFESSIONAL:
            professional_patch, found, new_notices = _normalize_professional(
                change,
                index,
                catalogs.professionals_by_name,
                catalogs.professionals_by_id,
            )
            notices.extend(new_notices)
        elif change.field is AppointmentField.DATE:
            date_change, found = _normalize_date(
                change,
                index,
                reference_at.astimezone(BOGOTA),
            )
        elif change.field is AppointmentField.TIME:
            time_change, found = _normalize_time(change, index)
        else:
            removal_change, found = _normalize_removal(change, index)
        issues.extend(found)

    issues.extend(_find_service_operation_conflicts(service_operations))
    if issues:
        return _blocked(issues, notices)

    if isinstance(removal_change, SetValue):
        role = removal_change.value.role
        if role is RemovalRole.ONLY:
            if service_operations and not _is_service_clear(service_operations):
                return _blocked(
                    [
                        _conflict(
                            AppointmentField.REMOVAL,
                            "retiro only contradice los cambios de servicios",
                        )
                    ],
                    notices,
                )
            service_operations = [Clear()]

    patch_kwargs: dict[str, object] = {
        "service_operations": tuple(service_operations),
        "professional": professional_patch,
    }
    if date_change is not None:
        patch_kwargs["date"] = date_change
    if time_change is not None:
        patch_kwargs["time"] = time_change
    if removal_change is not None:
        patch_kwargs["removal"] = removal_change

    try:
        patch = AppointmentRequestPatch(**patch_kwargs)
        merge_appointment_request(current_request, patch)
    except (MergeError, TypeError, ValueError) as error:
        return _blocked(
            [
                NormalizationIssue(
                    code=NormalizationIssueCode.INCOMPATIBLE_WITH_CURRENT_REQUEST,
                    kind=NormalizationIssueKind.INVALID,
                    field=None,
                    description=str(error),
                )
            ],
            notices,
        )

    return NormalizationResult(
        status=NormalizationStatus.SUCCESS,
        patch=patch,
        notices=tuple(notices),
    )


def _validate_inputs(
    current_request: object,
    services: object,
    professionals: object,
    reference_at: object,
) -> tuple[list[NormalizationIssue], _Catalogs | None]:
    issues: list[NormalizationIssue] = []
    if not isinstance(current_request, AppointmentRequest):
        issues.append(
            _configuration_issue(
                AppointmentField.SERVICES,
                NormalizationIssueCode.INCOMPATIBLE_WITH_CURRENT_REQUEST,
                "current_request debe ser AppointmentRequest",
            )
        )
    if (
        not isinstance(reference_at, datetime)
        or reference_at.tzinfo is None
        or reference_at.utcoffset() is None
    ):
        issues.append(
            _configuration_issue(
                AppointmentField.DATE,
                NormalizationIssueCode.INVALID_REFERENCE_TIME,
                "reference_at debe incluir zona horaria",
            )
        )

    service_map, service_ids, service_errors = _validate_service_catalog(
        services
    )
    professional_map, professional_ids, professional_errors = (
        _validate_professional_catalog(professionals)
    )
    issues.extend(service_errors)
    issues.extend(professional_errors)
    if issues:
        return issues, None
    return issues, _Catalogs(
        service_map,
        service_ids,
        professional_map,
        professional_ids,
    )


def _validate_service_catalog(catalog: object):
    by_name: dict[str, ServiceCatalogEntry] = {}
    by_id: dict[str, ServiceCatalogEntry] = {}
    identities: set[tuple[ServiceFamily, str | None]] = set()
    errors: list[NormalizationIssue] = []
    if not isinstance(catalog, tuple):
        return {}, {}, [
            _catalog_error(
                AppointmentField.SERVICES,
                "el catálogo debe ser una tupla",
            )
        ]
    for entry in catalog:
        valid = isinstance(entry, ServiceCatalogEntry)
        valid = valid and _valid_identifier(entry.canonical_id)
        valid = valid and entry.family in (
            ServiceFamily.MANICURE,
            ServiceFamily.PEDICURE,
        )
        valid = valid and isinstance(entry.names, tuple) and bool(entry.names)
        valid = valid and all(_valid_text(name) for name in entry.names)
        valid = valid and (
            entry.variant_text is None or _valid_text(entry.variant_text)
        )
        if not valid:
            errors.append(
                _catalog_error(
                    AppointmentField.SERVICES,
                    "entrada de servicio inválida",
                )
            )
            continue
        if entry.canonical_id in by_id:
            errors.append(
                _catalog_error(
                    AppointmentField.SERVICES,
                    f"ID de servicio duplicado: {entry.canonical_id}",
                )
            )
        identity = (entry.family, entry.variant_text)
        if identity in identities:
            errors.append(
                _catalog_error(
                    AppointmentField.SERVICES,
                    "identidad de servicio duplicada",
                )
            )
        identities.add(identity)
        by_id[entry.canonical_id] = entry
        for name in entry.names:
            key = _normalize_text(name)
            if key in by_name and by_name[key].canonical_id != entry.canonical_id:
                errors.append(
                    _catalog_error(
                        AppointmentField.SERVICES,
                        f"alias de servicio conflictivo: {name}",
                    )
                )
            by_name[key] = entry
    return by_name, by_id, errors


def _validate_professional_catalog(catalog: object):
    by_name: dict[str, ProfessionalCatalogEntry] = {}
    by_id: dict[str, ProfessionalCatalogEntry] = {}
    errors: list[NormalizationIssue] = []
    if not isinstance(catalog, tuple):
        return {}, {}, [
            _catalog_error(
                AppointmentField.PROFESSIONAL,
                "el catálogo debe ser una tupla",
            )
        ]
    for entry in catalog:
        valid = isinstance(entry, ProfessionalCatalogEntry)
        valid = valid and _valid_identifier(entry.canonical_id)
        valid = valid and _valid_text(entry.display_name)
        valid = valid and isinstance(entry.aliases, tuple)
        valid = valid and all(_valid_text(alias) for alias in entry.aliases)
        if not valid:
            errors.append(
                _catalog_error(
                    AppointmentField.PROFESSIONAL,
                    "entrada de profesional inválida",
                )
            )
            continue
        if entry.canonical_id in by_id:
            errors.append(
                _catalog_error(
                    AppointmentField.PROFESSIONAL,
                    f"ID profesional duplicado: {entry.canonical_id}",
                )
            )
        by_id[entry.canonical_id] = entry
        for name in (entry.display_name, *entry.aliases):
            key = _normalize_text(name)
            if key in by_name and by_name[key].canonical_id != entry.canonical_id:
                errors.append(
                    _catalog_error(
                        AppointmentField.PROFESSIONAL,
                        f"alias profesional conflictivo: {name}",
                    )
                )
            by_name[key] = entry
    return by_name, by_id, errors


def _find_change_conflicts(changes: list[InterpretedChange]):
    issues: list[NormalizationIssue] = []
    for field in (
        AppointmentField.PROFESSIONAL,
        AppointmentField.DATE,
        AppointmentField.TIME,
        AppointmentField.REMOVAL,
    ):
        matches = [change for change in changes if change.field is field]
        if len(matches) > 1:
            issues.append(
                _conflict(field, "hay varios cambios para el mismo campo")
            )
    service_changes = [
        change
        for change in changes
        if change.field is AppointmentField.SERVICES
    ]
    if len(service_changes) > 1 and any(
        change.operation in {ChangeOperation.SET, ChangeOperation.CLEAR}
        for change in service_changes
    ):
        issues.append(
            _conflict(
                AppointmentField.SERVICES,
                "SET o CLEAR no puede combinarse con otros cambios de servicios",
            )
        )
    return issues


def _normalize_services(change, index, by_name):
    if change.operation is ChangeOperation.CLEAR:
        return [Clear()], []
    raw_values = change.raw_values or [change.raw_text]
    assert change.raw_text is not None
    coherence_issue = _check_service_coherence(
        change.raw_text,
        raw_values,
        by_name,
        index,
    )
    if coherence_issue:
        return [], [coherence_issue]
    resolved: list[tuple[str, ServiceCatalogEntry]] = []
    issues: list[NormalizationIssue] = []
    for raw_value in raw_values:
        candidates = _catalog_candidates(raw_value, by_name)
        if not candidates:
            issues.append(
                _clarification(
                    NormalizationIssueCode.UNKNOWN_SERVICE,
                    AppointmentField.SERVICES,
                    "el servicio no existe en el catálogo",
                    raw_value,
                    index,
                )
            )
        elif len(candidates) > 1:
            issues.append(
                _clarification(
                    NormalizationIssueCode.AMBIGUOUS_SERVICE,
                    AppointmentField.SERVICES,
                    "la referencia coincide con varios servicios",
                    raw_value,
                    index,
                    tuple(candidates),
                )
            )
        else:
            resolved.append((raw_value, next(iter(candidates.values()))))
    if issues:
        return [], issues
    identities = [(entry.family, entry.variant_text) for _, entry in resolved]
    if len(set(identities)) != len(identities):
        return [], [
            _conflict(
                AppointmentField.SERVICES,
                "el cambio repite el mismo servicio",
                change.raw_text,
                index,
            )
        ]
    mentions = tuple(
        ServiceMention(
            raw,
            entry.family,
            entry.variant_text,
            canonical_id=entry.canonical_id,
        )
        for raw, entry in resolved
    )
    if change.operation is ChangeOperation.SET:
        return [SetServiceOperation(mentions)], []
    if change.operation is ChangeOperation.ADD:
        return [AddServiceOperation(mentions[0])], []
    raw, entry = resolved[0]
    return [
        RemoveServiceOperation(
            ServiceSelector(entry.family, entry.variant_text)
        )
    ], []


def _check_service_coherence(raw_text, raw_values, by_name, index):
    normalized_text = _normalize_text(raw_text)
    normalized_values = [_normalize_text(value) for value in raw_values]
    if len(set(normalized_values)) != len(normalized_values):
        return _conflict(
            AppointmentField.SERVICES,
            "raw_values repite una mención",
            raw_text,
            index,
        )
    if any(
        not _contains_phrase(normalized_text, value)
        for value in normalized_values
    ):
        return _clarification(
            NormalizationIssueCode.INCOHERENT_SERVICE_VALUES,
            AppointmentField.SERVICES,
            "raw_values no coincide con raw_text",
            raw_text,
            index,
        )
    represented: set[str] = set()
    for value in raw_values:
        represented.update(_catalog_candidates(value, by_name))
    mentioned = set(_catalog_candidates(raw_text, by_name))
    if not mentioned.issubset(represented):
        return _clarification(
            NormalizationIssueCode.INCOHERENT_SERVICE_VALUES,
            AppointmentField.SERVICES,
            "raw_values omite un servicio reconocible de raw_text",
            raw_text,
            index,
        )
    return None


def _normalize_professional(change, index, by_name, by_id):
    if change.operation is ChangeOperation.CLEAR:
        return _empty_professional(ProfessionalStatus.UNSPECIFIED), [], []
    assert change.raw_text is not None
    normalized = _normalize_text(change.raw_text)
    if _contains_phrase(normalized, "cualquiera") or _contains_phrase(
        normalized,
        "cualquier profesional",
    ):
        notices = _suggestion_notice(change, index, None)
        return _empty_professional(ProfessionalStatus.ANY), [], notices
    candidates = _catalog_candidates(change.raw_text, by_name)
    if not candidates:
        return ProfessionalPreferencePatch(), [
            _clarification(
                NormalizationIssueCode.UNKNOWN_PROFESSIONAL,
                AppointmentField.PROFESSIONAL,
                "la profesional no existe en el catálogo",
                change.raw_text,
                index,
            )
        ], []
    if len(candidates) > 1:
        return ProfessionalPreferencePatch(), [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_PROFESSIONAL,
                AppointmentField.PROFESSIONAL,
                "la referencia coincide con varias profesionales",
                change.raw_text,
                index,
                tuple(candidates),
            )
        ], []
    entry = next(iter(candidates.values()))
    notices = _suggestion_notice(change, index, entry.canonical_id)
    mention = ProfessionalMention(
        change.raw_text,
        entry.canonical_id,
        ProfessionalResolution.RESOLVED,
    )
    patch = ProfessionalPreferencePatch(
        status=SetValue(ProfessionalStatus.PREFERRED),
        ranked_operations=(SetRankOperation((mention,)),),
        fallback=SetValue(ProfessionalFallback.NONE),
    )
    return patch, [], notices


def _suggestion_notice(change, index, resolved_id):
    if change.suggested_id is None or change.suggested_id == resolved_id:
        return []
    return [
        NormalizationNotice(
            code=NormalizationNoticeCode.DISCARDED_SUGGESTED_ID,
            field=AppointmentField.PROFESSIONAL,
            description=(
                "suggested_id fue descartado porque no verifica raw_text"
            ),
            raw_text=change.raw_text,
            discarded_suggested_id=change.suggested_id,
            source_change_index=index,
        )
    ]


def _empty_professional(status):
    return ProfessionalPreferencePatch(
        status=SetValue(status),
        ranked_operations=(Clear(),),
        fallback=SetValue(ProfessionalFallback.NONE),
    )


def _normalize_date(change, index, reference_at):
    if change.operation is ChangeOperation.CLEAR:
        return Clear(), []
    raw = change.raw_text
    assert raw is not None
    text = _normalize_text(raw)
    relatives = []
    has_day_after_tomorrow = _contains_phrase(text, "pasado manana")
    if has_day_after_tomorrow:
        relatives.append(2)
    elif _contains_phrase(text, "manana"):
        relatives.append(1)
    if _contains_phrase(text, "hoy"):
        relatives.append(0)
    if len(relatives) == 1:
        resolved = reference_at.date() + timedelta(days=relatives[0])
        return SetValue(DatePreference(DateStatus.EXACT, raw, resolved)), []
    if len(relatives) > 1:
        return None, [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_DATE,
                AppointmentField.DATE,
                "la expresión contiene varias fechas",
                raw,
                index,
            )
        ]
    iso_matches = re.findall(
        r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)",
        text,
    )
    if len(iso_matches) > 1:
        return None, [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_DATE,
                AppointmentField.DATE,
                "la expresión contiene varias fechas",
                raw,
                index,
            )
        ]
    if iso_matches:
        try:
            resolved = date(*(int(value) for value in iso_matches[0]))
        except ValueError:
            return None, [
                _clarification(
                    NormalizationIssueCode.UNSUPPORTED_DATE,
                    AppointmentField.DATE,
                    "la fecha no es válida",
                    raw,
                    index,
                )
            ]
        return SetValue(DatePreference(DateStatus.EXACT, raw, resolved)), []
    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    month_names = "|".join(months)
    explicit = re.search(
        rf"(?<!\d)(\d{{1,2}}) de ({month_names}) "
        rf"de (\d{{4}})(?!\d)",
        text,
    )
    if explicit:
        try:
            resolved = date(
                int(explicit.group(3)),
                months[explicit.group(2)],
                int(explicit.group(1)),
            )
        except ValueError:
            return None, [
                _clarification(
                    NormalizationIssueCode.UNSUPPORTED_DATE,
                    AppointmentField.DATE,
                    "la fecha no es válida",
                    raw,
                    index,
                )
            ]
        return SetValue(DatePreference(DateStatus.EXACT, raw, resolved)), []
    weekdays = (
        "lunes",
        "martes",
        "miercoles",
        "jueves",
        "viernes",
        "sabado",
        "domingo",
    )
    if re.search(
        rf"\d{{1,2}} de ({month_names})(?! de \d{{4}})",
        text,
    ) or any(day in text.split() for day in weekdays):
        return None, [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_DATE,
                AppointmentField.DATE,
                "la fecha necesita año o una referencia más precisa",
                raw,
                index,
            )
        ]
    return None, [
        _clarification(
            NormalizationIssueCode.UNSUPPORTED_DATE,
            AppointmentField.DATE,
            "expresión de fecha no soportada",
            raw,
            index,
        )
    ]


def _normalize_time(change, index):
    if change.operation is ChangeOperation.CLEAR:
        return Clear(), []
    raw = change.raw_text
    assert raw is not None
    text = _normalize_text(raw)
    if re.search(r"\bentre\s+\d{1,2}\s+y\s+\d{1,2}\b", text):
        return None, [
            _clarification(
                NormalizationIssueCode.UNSUPPORTED_TIME,
                AppointmentField.TIME,
                "los rangos de hora no están soportados",
                raw,
                index,
            )
        ]
    qualified = re.search(
        r"(?:a las )?(\d{1,2})(?::(\d{2}))?\s+"
        r"(?:(?:de la )?(manana|tarde|noche)|(a m|p m))",
        text,
    )
    if qualified:
        hour = int(qualified.group(1))
        minute = int(qualified.group(2) or 0)
        period = qualified.group(3) or qualified.group(4)
        if (
            not 1 <= hour <= 12
            or minute > 59
            or (
                period == "noche"
                and hour not in {7, 8, 9, 10, 11, 12}
            )
        ):
            return None, [
                _clarification(
                    NormalizationIssueCode.AMBIGUOUS_TIME,
                    AppointmentField.TIME,
                    "la hora no tiene una interpretación inequívoca",
                    raw,
                    index,
                )
            ]
        if period in {"manana", "a m"}:
            hour = 0 if hour == 12 else hour
        elif period in {"tarde", "p m"}:
            hour = hour if hour == 12 else hour + 12
        else:
            hour = 0 if hour == 12 else hour + 12
        return SetValue(
            TimePreference(
                TimeStatus.EXACT,
                raw,
                time(hour, minute),
            )
        ), []
    exact_matches = re.findall(
        r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)",
        text,
    )
    if len(exact_matches) > 1:
        return None, [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_TIME,
                AppointmentField.TIME,
                "la expresión contiene varias horas",
                raw,
                index,
            )
        ]
    if exact_matches:
        hour, minute = exact_matches[0]
        return SetValue(
            TimePreference(
                TimeStatus.EXACT,
                raw,
                time(int(hour), int(minute)),
            )
        ), []
    period_matches = [
        value
        for phrase, value in (
            ("por la manana", TimePeriod.MORNING),
            ("por la tarde", TimePeriod.AFTERNOON),
            ("por la noche", TimePeriod.EVENING),
        )
        if _contains_phrase(text, phrase)
    ]
    if len(period_matches) == 1:
        return SetValue(
            TimePreference(
                TimeStatus.PERIOD,
                raw,
                period=period_matches[0],
            )
        ), []
    if re.search(r"(?:a las )?\d{1,2}(?![:\d])", text):
        return None, [
            _clarification(
                NormalizationIssueCode.AMBIGUOUS_TIME,
                AppointmentField.TIME,
                "la hora no indica mañana, tarde o formato de 24 horas",
                raw,
                index,
            )
        ]
    return None, [
        _clarification(
            NormalizationIssueCode.UNSUPPORTED_TIME,
            AppointmentField.TIME,
            "expresión de hora no soportada",
            raw,
            index,
        )
    ]


def _normalize_removal(change, index):
    if change.operation is ChangeOperation.CLEAR:
        return Clear(), []
    raw = change.raw_text
    assert raw is not None
    text = _normalize_text(raw)
    if _contains_phrase(text, "solo quiero retiro") or _contains_phrase(
        text,
        "solo retiro",
    ):
        return SetValue(
            RemovalPreference(
                RemovalStatus.REQUIRED,
                RemovalRole.ONLY,
            )
        ), []
    if any(
        _contains_phrase(text, phrase)
        for phrase in (
            "ya no necesito retiro",
            "no necesito retiro",
            "sin retiro",
        )
    ):
        return SetValue(RemovalPreference(RemovalStatus.NOT_REQUIRED)), []
    if any(
        _contains_phrase(text, phrase)
        for phrase in (
            "tambien necesito retiro",
            "necesito retiro",
            "con retiro",
        )
    ):
        return SetValue(
            RemovalPreference(
                RemovalStatus.REQUIRED,
                RemovalRole.ADDON,
            )
        ), []
    return None, [
        _clarification(
            NormalizationIssueCode.UNSUPPORTED_REMOVAL,
            AppointmentField.REMOVAL,
            "expresión de retiro no soportada",
            raw,
            index,
        )
    ]


def _find_service_operation_conflicts(operations):
    adds: set[tuple[object, ...]] = set()
    removes: set[tuple[object, ...]] = set()
    for operation in operations:
        if isinstance(operation, AddServiceOperation):
            adds.add((operation.mention.family, operation.mention.variant_text))
        elif isinstance(operation, RemoveServiceOperation):
            removes.add(
                (
                    operation.selector.family,
                    operation.selector.variant_text,
                )
            )
    if adds & removes:
        return [
            _conflict(
                AppointmentField.SERVICES,
                "el turno agrega y elimina el mismo servicio",
            )
        ]
    return []


def _catalog_candidates(raw_text, by_name):
    normalized = _normalize_text(raw_text)
    exact = by_name.get(normalized)
    if exact is not None:
        return {exact.canonical_id: exact}
    matching_aliases = [
        alias
        for alias in by_name
        if _contains_phrase(normalized, alias)
    ]
    maximal_aliases = [
        alias
        for alias in matching_aliases
        if not any(
            alias != other and _contains_phrase(other, alias)
            for other in matching_aliases
        )
    ]
    return {
        by_name[alias].canonical_id: by_name[alias]
        for alias in maximal_aliases
    }


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
    )
    comparable = re.sub(
        r"[^a-z0-9:-]+",
        " ",
        without_accents.casefold(),
    )
    return " ".join(comparable.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?:^|\s){re.escape(phrase)}(?:$|\s)", text) is not None


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_identifier(value: object) -> bool:
    return _valid_text(value) and value == value.strip()


def _is_service_clear(operations):
    return len(operations) == 1 and isinstance(operations[0], Clear)


def _blocked(issues, notices=()):
    invalid_kinds = {
        NormalizationIssueKind.CONFIGURATION,
        NormalizationIssueKind.CONFLICT,
        NormalizationIssueKind.INVALID,
    }
    status = (
        NormalizationStatus.INVALID
        if any(issue.kind in invalid_kinds for issue in issues)
        else NormalizationStatus.NEEDS_CLARIFICATION
    )
    return NormalizationResult(status, None, tuple(issues), tuple(notices))


def _clarification(
    code,
    field,
    description,
    raw_text,
    index,
    candidate_ids=(),
):
    return NormalizationIssue(
        code,
        NormalizationIssueKind.CLARIFICATION,
        field,
        description,
        raw_text,
        tuple(candidate_ids),
        index,
    )


def _conflict(field, description, raw_text=None, index=None):
    return NormalizationIssue(
        NormalizationIssueCode.CONFLICTING_CHANGES,
        NormalizationIssueKind.CONFLICT,
        field,
        description,
        raw_text,
        source_change_index=index,
    )


def _configuration_issue(field, code, description):
    return NormalizationIssue(
        code,
        NormalizationIssueKind.CONFIGURATION,
        field,
        description,
    )


def _catalog_error(field, description):
    code = (
        NormalizationIssueCode.INVALID_SERVICE_CATALOG
        if field is AppointmentField.SERVICES
        else NormalizationIssueCode.INVALID_PROFESSIONAL_CATALOG
    )
    return _configuration_issue(field, code, description)
