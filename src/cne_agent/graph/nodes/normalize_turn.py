"""Nodo de normalización y actualización atómica de la solicitud."""

from datetime import datetime

from langgraph.runtime import Runtime

from cne_agent.appointments.merge import merge_appointment_request
from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.state import ConversationContext, ConversationState
from cne_agent.interpretation.models import TurnInterpretation
from cne_agent.interpretation.normalizer import (
    NormalizationResult,
    NormalizationStatus,
    normalize_turn_interpretation,
)


def normalize_turn(
    state: ConversationState,
    runtime: Runtime[ConversationContext],
) -> dict[str, object]:
    """Normaliza el turno y aplica el patch solo tras un merge completo."""

    interpretation = state.get("turn_interpretation")
    if not isinstance(interpretation, TurnInterpretation):
        raise TypeError("turn_interpretation es obligatorio")

    current_request = state.get("appointment_request")
    if not isinstance(current_request, AppointmentRequest):
        raise TypeError("appointment_request debe estar inicializado")

    context = runtime.context
    for key in (
        "service_catalog",
        "professional_catalog",
        "reference_at",
    ):
        if key not in context:
            raise KeyError(f"falta el contexto obligatorio: {key}")

    reference_at = context["reference_at"]
    if (
        not isinstance(reference_at, datetime)
        or reference_at.tzinfo is None
        or reference_at.utcoffset() is None
    ):
        raise ValueError("reference_at debe incluir zona horaria")

    result = normalize_turn_interpretation(
        interpretation,
        current_request=current_request,
        service_catalog=context["service_catalog"],
        professional_catalog=context["professional_catalog"],
        reference_at=reference_at,
    )
    if not isinstance(result, NormalizationResult):
        raise TypeError("el normalizador no devolvió NormalizationResult")

    if result.status is not NormalizationStatus.SUCCESS:
        return {"normalization_result": result}

    if result.patch is None:
        raise RuntimeError("SUCCESS exige un patch")

    updated_request = merge_appointment_request(
        current_request,
        result.patch,
    )
    return {
        "normalization_result": result,
        "appointment_request": updated_request,
    }
