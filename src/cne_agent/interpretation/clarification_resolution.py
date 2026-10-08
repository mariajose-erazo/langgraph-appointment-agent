"""Reconciliacion determinista de respuestas a aclaraciones pendientes."""

from __future__ import annotations

import re
import unicodedata

from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedChange,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    NormalizationIssueCode,
    NormalizationResult,
    NormalizationStatus,
)


def reconcile_clarification(
    previous_interpretation: TurnInterpretation | None,
    previous_result: NormalizationResult | None,
    current_interpretation: TurnInterpretation,
) -> TurnInterpretation:
    """Reintenta un turno bloqueado solo ante una respuesta inequivoca.

    V1 soporta exclusivamente una hora de 12 horas pendiente de manana/tarde.
    Cualquier consulta lateral, contradiccion o forma no reconocida conserva el
    delta actual sin reconstruir silenciosamente el turno anterior.
    """

    if not isinstance(current_interpretation, TurnInterpretation):
        raise TypeError("current_interpretation debe ser TurnInterpretation")
    if not isinstance(previous_interpretation, TurnInterpretation):
        return current_interpretation
    if (
        not isinstance(previous_result, NormalizationResult)
        or previous_result.status is not NormalizationStatus.NEEDS_CLARIFICATION
    ):
        return current_interpretation

    issues = previous_result.issues
    if (
        len(issues) != 1
        or issues[0].code is not NormalizationIssueCode.AMBIGUOUS_TIME
        or issues[0].field is not AppointmentField.TIME
    ):
        return current_interpretation
    if current_interpretation.ambiguities:
        return current_interpretation
    if current_interpretation.information_queries:
        return current_interpretation
    if len(current_interpretation.appointment_changes) != 1:
        return current_interpretation

    current_change = current_interpretation.appointment_changes[0]
    if (
        current_change.field is not AppointmentField.TIME
        or current_change.operation is not ChangeOperation.SET
        or current_change.raw_text is None
    ):
        return current_interpretation

    period = _period_qualifier(current_change.raw_text)
    previous_time = _single_previous_time_change(previous_interpretation)
    if period is None or previous_time is None or previous_time.raw_text is None:
        return current_interpretation
    if not _is_unqualified_hour(previous_time.raw_text):
        return current_interpretation

    resolved_time = previous_time.model_copy(
        update={"raw_text": f"{previous_time.raw_text.strip()} {period}"}
    )
    changes = [
        resolved_time if change is previous_time else change
        for change in previous_interpretation.appointment_changes
    ]
    return TurnInterpretation(
        intents=_unique(
            [*previous_interpretation.intents, *current_interpretation.intents]
        ),
        appointment_changes=changes,
        information_queries=[
            *previous_interpretation.information_queries,
            *current_interpretation.information_queries,
        ],
        ambiguities=[],
    )


def _single_previous_time_change(
    interpretation: TurnInterpretation,
) -> InterpretedChange | None:
    matches = [
        change
        for change in interpretation.appointment_changes
        if change.field is AppointmentField.TIME
        and change.operation is ChangeOperation.SET
    ]
    return matches[0] if len(matches) == 1 else None


def _period_qualifier(raw_text: str) -> str | None:
    normalized = _normalize(raw_text)
    if re.fullmatch(r"(?:de|por) la manana|manana|a m", normalized):
        return "de la manana"
    if re.fullmatch(r"(?:de|por) la tarde|tarde|p m", normalized):
        return "de la tarde"
    return None


def _is_unqualified_hour(raw_text: str) -> bool:
    normalized = _normalize(raw_text)
    return bool(re.fullmatch(r"(?:a las )?(?:[1-9]|1[0-2])", normalized))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.strip().lower())
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _unique(values):
    return list(dict.fromkeys(values))
