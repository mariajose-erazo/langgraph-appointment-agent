from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import Runtime
import pytest

from cne_agent.appointments.request import AppointmentRequest
from cne_agent.graph.nodes.initialize_appointment_request import (
    initialize_appointment_request,
)
from cne_agent.graph.nodes.interpret_turn import create_interpret_turn_node
from cne_agent.graph.nodes import normalize_turn as normalize_module
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedAmbiguity,
    InterpretedChange,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    NormalizationStatus,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)
from cne_agent.appointments.request import ServiceFamily


SERVICE_CATALOG = (
    ServiceCatalogEntry("manicure", ServiceFamily.MANICURE, None, ("manicure",)),
)
PROFESSIONAL_CATALOG = (
    ProfessionalCatalogEntry("laura", "Laura"),
)
REFERENCE_AT = datetime(2026, 10, 5, 10, tzinfo=BOGOTA)


def runtime_context(**overrides):
    context = {
        "current_date": "2026-10-05",
        "business_context": "Contexto.",
        "capabilities_context": "Sin capacidades operativas.",
        "service_catalog": SERVICE_CATALOG,
        "professional_catalog": PROFESSIONAL_CATALOG,
        "reference_at": REFERENCE_AT,
    }
    context.update(overrides)
    return Runtime(context=context)


def test_initializer_creates_request_once_and_never_replaces_it():
    assert initialize_appointment_request({"messages": []}) == {
        "appointment_request": AppointmentRequest(),
        "appointment_readiness": None,
        "availability_result": None,
    }

    existing = AppointmentRequest()
    assert initialize_appointment_request(
        {"messages": [], "appointment_request": existing}
    ) == {
        "appointment_readiness": None,
        "availability_result": None,
    }


def test_interpret_node_separates_current_turn_from_history():
    received = {}
    interpretation = TurnInterpretation()

    def invoke(value):
        received.update(value)
        return interpretation

    node = create_interpret_turn_node(RunnableLambda(invoke))
    result = node(
        {
            "messages": [
                HumanMessage(content="Anterior."),
                AIMessage(content="Respuesta."),
                HumanMessage(content="Actual."),
            ]
        }
    )

    assert result == {"turn_interpretation": interpretation}
    assert [message.content for message in received["history"]] == [
        "Anterior.",
        "Respuesta.",
    ]
    assert received["user_input"] == "Actual."


def test_interpreter_technical_error_is_propagated():
    def fail(_value):
        raise TimeoutError("falló Gemini")

    node = create_interpret_turn_node(RunnableLambda(fail))

    with pytest.raises(TimeoutError, match="falló Gemini"):
        node({"messages": [HumanMessage(content="Actual.")]})


def test_clarification_is_saved_without_request_update():
    current = AppointmentRequest()
    interpretation = TurnInterpretation(
        ambiguities=[
            InterpretedAmbiguity(
                field=AppointmentField.TIME,
                description="No se indicó mañana o tarde.",
            )
        ]
    )

    result = normalize_module.normalize_turn(
        {
            "messages": [],
            "appointment_request": current,
            "turn_interpretation": interpretation,
        },
        runtime_context(),
    )

    assert result["normalization_result"].status is NormalizationStatus.NEEDS_CLARIFICATION
    assert "appointment_request" not in result


def test_invalid_turn_is_saved_without_request_update():
    current = AppointmentRequest()
    interpretation = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.SERVICES,
                operation=ChangeOperation.SET,
                raw_text="manicure",
            ),
            InterpretedChange(
                field=AppointmentField.SERVICES,
                operation=ChangeOperation.CLEAR,
            ),
        ]
    )

    result = normalize_module.normalize_turn(
        {
            "messages": [],
            "appointment_request": current,
            "turn_interpretation": interpretation,
        },
        runtime_context(),
    )

    assert result["normalization_result"].status is NormalizationStatus.INVALID
    assert "appointment_request" not in result


@pytest.mark.parametrize(
    "missing_key",
    ["service_catalog", "professional_catalog", "reference_at"],
)
def test_normalizer_requires_each_context_input(missing_key):
    runtime = runtime_context()
    del runtime.context[missing_key]

    with pytest.raises(KeyError, match=missing_key):
        normalize_module.normalize_turn(
            {
                "messages": [],
                "appointment_request": AppointmentRequest(),
                "turn_interpretation": TurnInterpretation(),
            },
            runtime,
        )


def test_normalizer_rejects_naive_reference_as_technical_error():
    with pytest.raises(ValueError, match="zona horaria"):
        normalize_module.normalize_turn(
            {
                "messages": [],
                "appointment_request": AppointmentRequest(),
                "turn_interpretation": TurnInterpretation(),
            },
            runtime_context(reference_at=datetime(2026, 10, 5, 10)),
        )


def test_merge_error_is_propagated_without_returning_partial_update(monkeypatch):
    interpretation = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.SERVICES,
                operation=ChangeOperation.SET,
                raw_text="manicure",
            )
        ]
    )

    def fail_merge(_current, _patch):
        raise RuntimeError("falló merge")

    monkeypatch.setattr(normalize_module, "merge_appointment_request", fail_merge)

    with pytest.raises(RuntimeError, match="falló merge"):
        normalize_module.normalize_turn(
            {
                "messages": [],
                "appointment_request": AppointmentRequest(),
                "turn_interpretation": interpretation,
            },
            runtime_context(),
        )
