from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from cne_agent.appointments.request import AppointmentRequest, AppointmentRequestPatch
from cne_agent.graph.nodes.clarify_turn import clarify_turn
from cne_agent.graph.nodes.invalid_turn import invalid_turn
from cne_agent.graph.nodes import success_response as success_module
from cne_agent.interpretation.models import AppointmentField, TurnInterpretation
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    NormalizationIssue,
    NormalizationIssueCode,
    NormalizationIssueKind,
    NormalizationResult,
    NormalizationStatus,
    ProfessionalCatalogEntry,
)


def test_clarification_uses_authorized_candidate_names_without_ids():
    result = NormalizationResult(
        NormalizationStatus.NEEDS_CLARIFICATION,
        None,
        (
            NormalizationIssue(
                NormalizationIssueCode.AMBIGUOUS_PROFESSIONAL,
                NormalizationIssueKind.CLARIFICATION,
                AppointmentField.PROFESSIONAL,
                "varias coincidencias",
                "Lau",
                ("laura-one", "laura-two"),
            ),
        ),
    )
    runtime = Runtime(
        context={
            "professional_catalog": (
                ProfessionalCatalogEntry("laura-one", "Laura Gómez"),
                ProfessionalCatalogEntry("laura-two", "Laura Pérez"),
            ),
            "service_catalog": (),
        }
    )
    response = clarify_turn(
        {"messages": [], "normalization_result": result}, runtime
    )["messages"][0].content
    assert "Laura Gómez" in response and "Laura Pérez" in response
    assert "laura-one" not in response and "laura-two" not in response


def test_invalid_response_does_not_expose_internal_description():
    result = NormalizationResult(
        NormalizationStatus.INVALID,
        None,
        (
            NormalizationIssue(
                NormalizationIssueCode.INCOMPATIBLE_WITH_CURRENT_REQUEST,
                NormalizationIssueKind.INVALID,
                None,
                "AppointmentRequest raised ValueError",
            ),
        ),
    )
    response = invalid_turn(
        {"messages": [], "normalization_result": result}
    )["messages"][0].content
    assert "AppointmentRequest" not in response
    assert "ValueError" not in response


def test_success_response_receives_explicit_structured_context(monkeypatch):
    received = {}

    class FakeChain:
        def invoke(self, value):
            received.update(value)
            return "Tengo tus preferencias; aún no hay una reserva confirmada."

    monkeypatch.setattr(success_module, "create_conversation_chain", FakeChain)
    state = {
        "messages": [HumanMessage(content="Quiero manicure")],
        "appointment_request": AppointmentRequest(),
        "turn_interpretation": TurnInterpretation(),
        "normalization_result": NormalizationResult(
            NormalizationStatus.SUCCESS,
            AppointmentRequestPatch(),
        ),
    }
    runtime = Runtime(
        context={
            "current_date": "2026-10-06",
            "business_context": "Contexto autorizado.",
            "capabilities_context": "Sin operaciones.",
            "reference_at": datetime(2026, 10, 6, tzinfo=BOGOTA),
        }
    )
    result = success_module.success_response(state, runtime)
    assert isinstance(result["messages"][0], AIMessage)
    assert "appointment_context" in received
    assert "interpretation_context" in received
    assert "information_queries" in received
