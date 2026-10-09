"""Strict translation of untrusted Cosmos documents into domain data."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from cne_agent.adapters.cosmos.config import CosmosDataError
from cne_agent.appointments.request import RemovalRole, RemovalStatus
from cne_agent.appointments.scheduling import (
    ExistingAppointment,
    ExistingAppointmentStatus,
    ScheduleBlock,
    ScheduleBlockKind,
)


BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


@dataclass(frozen=True)
class CosmosProfessional:
    professional_id: str
    display_name: str
    active: bool
    supported_service_ids: tuple[str, ...]


@dataclass(frozen=True)
class CosmosClosure:
    business_date: date
    active: bool
    closure_type: str


def parse_professional(document: Mapping[str, Any], *, business_id: str):
    _common(document, "professional", business_id)
    professional_id = _text(document, "professional_id")
    if _text(document, "id") != professional_id:
        raise CosmosDataError("id profesional inconsistente")
    services = _string_tuple(document, "supported_service_ids", allow_empty=True)
    _timestamp(document, "created_at")
    _timestamp(document, "updated_at")
    return CosmosProfessional(
        professional_id,
        _text(document, "display_name"),
        _bool(document, "active"),
        services,
    )


def parse_schedule_entry(
    document: Mapping[str, Any],
    *,
    business_id: str,
    business_date: date,
):
    if not isinstance(document, Mapping):
        raise CosmosDataError("documento Cosmos invalido")
    document_type = document.get("document_type")
    if document_type not in {"appointment", "schedule_block"}:
        raise CosmosDataError("document_type de agenda desconocido")
    _common(document, document_type, business_id)
    stored_date = _date(document, "business_date")
    if stored_date != business_date:
        raise CosmosDataError("business_date no coincide con la consulta")
    expected_key = f"{business_id}#{business_date.isoformat()}"
    if _text(document, "schedule_key") != expected_key:
        raise CosmosDataError("schedule_key inconsistente")
    if document_type == "appointment":
        return _parse_appointment(document, business_date)
    return _parse_block(document, business_date)


def parse_closure(
    document: Mapping[str, Any],
    *,
    business_id: str,
    business_date: date,
) -> CosmosClosure:
    _common(document, "business_closure", business_id)
    stored_date = _date(document, "business_date")
    if stored_date != business_date:
        raise CosmosDataError("fecha de cierre inconsistente")
    if _text(document, "id") != f"closure#{business_date.isoformat()}":
        raise CosmosDataError("id de cierre inconsistente")
    closure_type = _text(document, "closure_type")
    if closure_type not in {
        "holiday",
        "extraordinary_closure",
        "maintenance",
        "other",
    }:
        raise CosmosDataError("closure_type desconocido")
    _timestamp(document, "created_at")
    _timestamp(document, "updated_at")
    return CosmosClosure(stored_date, _bool(document, "active"), closure_type)


def _parse_appointment(document, business_date):
    if _text(document, "id") != _text(document, "appointment_id"):
        raise CosmosDataError("id de cita inconsistente")
    services = _string_tuple(document, "service_ids")
    starts_at = _timestamp(document, "starts_at")
    ends_at = _timestamp(document, "service_ends_at")
    _validate_local_date(starts_at, business_date)
    _validate_local_date(ends_at, business_date)
    try:
        status = ExistingAppointmentStatus(_text(document, "status"))
        RemovalStatus(_text(document, "removal_status"))
        RemovalRole(_text(document, "removal_role"))
    except ValueError as error:
        raise CosmosDataError("enum de cita desconocido") from error
    _timestamp(document, "created_at")
    _timestamp(document, "updated_at")
    if not services:
        raise CosmosDataError("la cita exige service_ids")
    try:
        return ExistingAppointment(
            _text(document, "professional_id"),
            starts_at.astimezone(BOGOTA),
            ends_at.astimezone(BOGOTA),
            status,
        )
    except (TypeError, ValueError) as error:
        raise CosmosDataError("intervalo de cita invalido") from error


def _parse_block(document, business_date):
    if _text(document, "id") != _text(document, "block_id"):
        raise CosmosDataError("id de bloqueo inconsistente")
    starts_at = _timestamp(document, "starts_at")
    ends_at = _timestamp(document, "ends_at")
    _validate_local_date(starts_at, business_date)
    _validate_local_date(ends_at, business_date)
    try:
        kind = ScheduleBlockKind(_text(document, "block_type"))
    except ValueError as error:
        raise CosmosDataError("block_type desconocido") from error
    _timestamp(document, "created_at")
    _timestamp(document, "updated_at")
    if not _bool(document, "active"):
        return None
    try:
        return ScheduleBlock(
            _text(document, "professional_id"),
            starts_at.astimezone(BOGOTA),
            ends_at.astimezone(BOGOTA),
            kind,
        )
    except (TypeError, ValueError) as error:
        raise CosmosDataError("intervalo de bloqueo invalido") from error


def _common(document, document_type, business_id):
    if not isinstance(document, Mapping):
        raise CosmosDataError("documento Cosmos invalido")
    if document.get("schema_version") != 1:
        raise CosmosDataError("schema_version no soportado")
    if document.get("document_type") != document_type:
        raise CosmosDataError("document_type inesperado")
    if _text(document, "business_id") != business_id:
        raise CosmosDataError("business_id inesperado")


def _text(document, field):
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CosmosDataError(f"{field} debe ser texto no vacio")
    return value


def _bool(document, field):
    value = document.get(field)
    if type(value) is not bool:
        raise CosmosDataError(f"{field} debe ser booleano")
    return value


def _string_tuple(document, field, *, allow_empty=False):
    value = document.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CosmosDataError(f"{field} debe ser una lista de IDs")
    if not allow_empty and not value:
        raise CosmosDataError(f"{field} no puede estar vacio")
    if len(set(value)) != len(value):
        raise CosmosDataError(f"{field} contiene duplicados")
    return tuple(value)


def _date(document, field):
    value = _text(document, field)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CosmosDataError(f"{field} no es una fecha ISO") from error


def _timestamp(document, field):
    value = _text(document, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CosmosDataError(f"{field} no es ISO 8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise CosmosDataError(f"{field} debe estar en UTC")
    return parsed


def _validate_local_date(value, expected):
    if value.astimezone(BOGOTA).date() != expected:
        raise CosmosDataError("timestamp no coincide con business_date")
