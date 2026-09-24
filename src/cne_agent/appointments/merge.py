"""Fusión determinista de una solicitud vigente con el parche de un turno.

No resuelve nombres, expresiones temporales ni disponibilidad. Si el
resultado no cumple las invariantes de la solicitud, la fusión falla
entera y las entradas permanecen intactas.
"""

from __future__ import annotations

from cne_agent.appointments.request import (
    AddRankOperation,
    AddServiceOperation,
    AppointmentRequest,
    AppointmentRequestPatch,
    Clear,
    DatePreference,
    Omitted,
    ProfessionalMention,
    ProfessionalPreference,
    ProfessionalPreferencePatch,
    ProfessionalResolution,
    ProfessionalSelector,
    RemovalPreference,
    RemoveRankOperation,
    RemoveServiceOperation,
    SchedulePreference,
    ServiceFamily,
    ServiceMention,
    ServiceSelector,
    SetRankOperation,
    SetServiceOperation,
    SetValue,
    TimePreference,
)


class MergeError(ValueError):
    """El patch no pudo aplicarse a la solicitud vigente."""


def merge_appointment_request(
    current: AppointmentRequest,
    patch: AppointmentRequestPatch,
) -> AppointmentRequest:
    """Devuelve una foto nueva con el parche aplicado.

    Un parche vacío devuelve la misma instancia. Cualquier conflicto o
    foto final inválida lanza MergeError sin modificar las entradas.
    """

    if _is_empty_patch(patch):
        return current
    services = _apply_service_operations(
        current.services,
        patch.service_operations,
    )
    professional = _merge_professional(
        current.professional,
        patch.professional,
    )
    schedule = SchedulePreference(
        date=_apply_block(current.schedule.date, patch.date, DatePreference),
        time=_apply_block(current.schedule.time, patch.time, TimePreference),
    )
    removal = _apply_block(current.removal, patch.removal, RemovalPreference)
    try:
        return AppointmentRequest(
            services=services,
            professional=professional,
            schedule=schedule,
            removal=removal,
        )
    except (TypeError, ValueError) as error:
        raise MergeError(str(error)) from error


def _is_empty_patch(patch: AppointmentRequestPatch) -> bool:
    professional = patch.professional
    return (
        not patch.service_operations
        and isinstance(professional.status, Omitted)
        and not professional.ranked_operations
        and isinstance(professional.fallback, Omitted)
        and isinstance(patch.date, Omitted)
        and isinstance(patch.time, Omitted)
        and isinstance(patch.removal, Omitted)
    )


def _apply_block(current, change, initial_factory):
    if isinstance(change, Omitted):
        return current
    if isinstance(change, Clear):
        return initial_factory()
    if isinstance(change, SetValue):
        return change.value
    raise MergeError("el cambio de bloque no es Omitted, SetValue ni Clear")


def _apply_service_operations(services, operations):
    merged = list(services)
    for operation in operations:
        if isinstance(operation, Clear):
            merged = []
        elif isinstance(operation, SetServiceOperation):
            merged = list(operation.mentions)
        elif isinstance(operation, AddServiceOperation):
            if _contains_service(merged, operation.mention):
                raise MergeError("el servicio ya está en la solicitud")
            merged.append(operation.mention)
        elif isinstance(operation, RemoveServiceOperation):
            merged = [
                mention
                for mention in merged
                if not _service_selector_matches(operation.selector, mention)
            ]
        else:
            raise MergeError("operación de servicio desconocida")
    return tuple(merged)


def _merge_professional(current, patch: ProfessionalPreferencePatch):
    # El ranking se transforma entero antes de construir la preferencia.
    # Así un CLEAR intermedio no se valida mientras el estado sigue siendo preferred.
    ranked = _apply_rank_operations(current.ranked, patch.ranked_operations)
    status = (
        patch.status.value
        if isinstance(patch.status, SetValue)
        else current.status
    )
    fallback = (
        patch.fallback.value
        if isinstance(patch.fallback, SetValue)
        else current.fallback
    )
    try:
        return ProfessionalPreference(
            status=status,
            ranked=ranked,
            fallback=fallback,
        )
    except (TypeError, ValueError) as error:
        raise MergeError(str(error)) from error


def _apply_rank_operations(ranked, operations):
    merged = list(ranked)
    for operation in operations:
        if isinstance(operation, Clear):
            merged = []
        elif isinstance(operation, SetRankOperation):
            merged = list(operation.mentions)
        elif isinstance(operation, AddRankOperation):
            if _contains_professional(merged, operation.mention):
                raise MergeError("la profesional ya está en el ranking")
            merged.append(operation.mention)
        elif isinstance(operation, RemoveRankOperation):
            merged = [
                mention
                for mention in merged
                if not _professional_selector_matches(
                    operation.selector,
                    mention,
                )
            ]
        else:
            raise MergeError("operación de ranking desconocida")
    return tuple(merged)


def _service_identity(mention: ServiceMention) -> tuple[object, ...]:
    if mention.family is ServiceFamily.UNRESOLVED:
        return ("raw_text", mention.raw_text)
    return ("family", mention.family, mention.variant_text)


def _contains_service(
    mentions: list[ServiceMention],
    candidate: ServiceMention,
) -> bool:
    identity = _service_identity(candidate)
    return any(_service_identity(mention) == identity for mention in mentions)


def _service_selector_matches(
    selector: ServiceSelector,
    mention: ServiceMention,
) -> bool:
    if selector.raw_text is not None:
        return (
            mention.family is ServiceFamily.UNRESOLVED
            and mention.raw_text == selector.raw_text
        )
    return (
        mention.family is selector.family
        and mention.variant_text == selector.variant_text
    )


def _professional_identity(
    mention: ProfessionalMention,
) -> tuple[object, ...]:
    if mention.resolution_status is ProfessionalResolution.RESOLVED:
        return ("canonical_id", mention.canonical_id)
    return ("raw_text", mention.raw_text)


def _contains_professional(
    mentions: list[ProfessionalMention],
    candidate: ProfessionalMention,
) -> bool:
    identity = _professional_identity(candidate)
    return any(
        _professional_identity(mention) == identity for mention in mentions
    )


def _professional_selector_matches(
    selector: ProfessionalSelector,
    mention: ProfessionalMention,
) -> bool:
    if selector.canonical_id is not None:
        return (
            mention.resolution_status is ProfessionalResolution.RESOLVED
            and mention.canonical_id == selector.canonical_id
        )
    return (
        mention.resolution_status is ProfessionalResolution.UNRESOLVED
        and mention.raw_text == selector.raw_text
    )
