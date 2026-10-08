from datetime import date, datetime, time

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from cne_agent.appointments.request import (
    DateStatus,
    ProfessionalStatus,
    ServiceFamily,
)
from cne_agent.graph.nodes import success_response as success_response_module
from cne_agent.graph.workflow import create_conversation_graph
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedAmbiguity,
    InterpretedChange,
    TurnIntent,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    NormalizationIssueCode,
    NormalizationStatus,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)


SERVICE_CATALOG = (
    ServiceCatalogEntry("manicure", ServiceFamily.MANICURE, None, ("manicure",)),
    ServiceCatalogEntry("pedicure", ServiceFamily.PEDICURE, None, ("pedicure",)),
)
PROFESSIONAL_CATALOG = (
    ProfessionalCatalogEntry("laura", "Laura"),
    ProfessionalCatalogEntry("valentina", "Valentina"),
)


class FakeConversationChain:
    def invoke(self, _input_data):
        return "Respuesta simulada."


class InterpretationQueue:
    def __init__(self, *interpretations):
        self.interpretations = list(interpretations)

    def invoke(self, _value):
        return self.interpretations.pop(0)


def context():
    return {
        "current_date": "2026-10-05",
        "business_context": "Contexto.",
        "capabilities_context": "Sin capacidades operativas.",
        "service_catalog": SERVICE_CATALOG,
        "professional_catalog": PROFESSIONAL_CATALOG,
        "reference_at": datetime(2026, 10, 5, 10, tzinfo=BOGOTA),
    }


def graph_with(monkeypatch, *interpretations):
    monkeypatch.setattr(
        success_response_module,
        "create_conversation_chain",
        lambda: FakeConversationChain(),
    )
    queue = InterpretationQueue(*interpretations)
    return create_conversation_graph(
        turn_interpretation_chain=RunnableLambda(queue.invoke)
    )


def invoke_turn(graph, config, text):
    return graph.invoke(
        {"messages": [HumanMessage(content=text)]},
        config=config,
        context=context(),
    )


def change(field, operation, raw_text):
    return InterpretedChange(
        field=field,
        operation=operation,
        raw_text=raw_text,
    )


def test_accumulates_service_date_and_professional_across_turns(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure"),
                change(AppointmentField.DATE, ChangeOperation.SET, "mañana"),
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.PROFESSIONAL, ChangeOperation.SET, "Laura")
            ]
        ),
    )
    config = {"configurable": {"thread_id": "accumulation"}}

    invoke_turn(graph, config, "Quiero manicure mañana.")
    result = invoke_turn(graph, config, "Con Laura.")
    request = result["appointment_request"]

    assert [service.family for service in request.services] == [ServiceFamily.MANICURE]
    assert request.schedule.date.status is DateStatus.EXACT
    assert request.schedule.date.resolved_date == date(2026, 10, 6)
    assert request.professional.status is ProfessionalStatus.PREFERRED
    assert request.professional.ranked[0].canonical_id == "laura"


def test_replaces_professional_instead_of_accumulating_rank(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.PROFESSIONAL, ChangeOperation.SET, "Laura")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.PROFESSIONAL, ChangeOperation.SET, "Valentina")
            ]
        ),
    )
    config = {"configurable": {"thread_id": "replace-professional"}}

    invoke_turn(graph, config, "Con Laura.")
    result = invoke_turn(graph, config, "Mejor con Valentina.")

    assert [item.canonical_id for item in result["appointment_request"].professional.ranked] == ["valentina"]


def test_adds_and_then_removes_service_across_turns(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.ADD, "pedicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.REMOVE, "pedicure")
            ]
        ),
    )
    config = {"configurable": {"thread_id": "service-operations"}}

    invoke_turn(graph, config, "Quiero manicure.")
    added = invoke_turn(graph, config, "También pedicure.")
    assert [item.family for item in added["appointment_request"].services] == [
        ServiceFamily.MANICURE,
        ServiceFamily.PEDICURE,
    ]

    removed = invoke_turn(graph, config, "Ya no quiero pedicure.")
    assert [item.family for item in removed["appointment_request"].services] == [
        ServiceFamily.MANICURE
    ]


def test_clarification_does_not_mutate_accumulated_request(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.TIME, ChangeOperation.SET, "a las 3")
            ]
        ),
    )
    config = {"configurable": {"thread_id": "clarification"}}

    first = invoke_turn(graph, config, "Quiero manicure.")
    previous = first["appointment_request"]
    second = invoke_turn(graph, config, "A las 3.")

    assert second["normalization_result"].status is NormalizationStatus.NEEDS_CLARIFICATION
    assert second["appointment_request"] == previous


def test_invalid_turn_does_not_mutate_accumulated_request(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "pedicure"),
                InterpretedChange(
                    field=AppointmentField.SERVICES,
                    operation=ChangeOperation.CLEAR,
                ),
            ]
        ),
    )
    config = {"configurable": {"thread_id": "invalid"}}

    previous = invoke_turn(graph, config, "Quiero manicure.")["appointment_request"]
    result = invoke_turn(graph, config, "Cambio contradictorio.")

    assert result["normalization_result"].status is NormalizationStatus.INVALID
    assert result["appointment_request"] == previous


def test_multiple_changes_are_atomic_when_professional_is_unknown(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.ADD, "pedicure"),
                change(AppointmentField.PROFESSIONAL, ChangeOperation.SET, "Inexistente"),
            ]
        ),
    )
    config = {"configurable": {"thread_id": "atomic"}}

    previous = invoke_turn(graph, config, "Quiero manicure.")["appointment_request"]
    result = invoke_turn(graph, config, "También pedicure con Inexistente.")

    assert result["normalization_result"].status is NormalizationStatus.NEEDS_CLARIFICATION
    assert result["normalization_result"].issues[0].code is NormalizationIssueCode.UNKNOWN_PROFESSIONAL
    assert result["appointment_request"] == previous


def test_multi_intent_is_preserved_while_request_is_updated(monkeypatch):
    interpretation = TurnInterpretation(
        intents=[TurnIntent.INFORMATION_QUERY, TurnIntent.BOOK_APPOINTMENT],
        information_queries=["¿Cuánto cuesta el manicure?"],
        appointment_changes=[
            change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure"),
            change(AppointmentField.DATE, ChangeOperation.SET, "mañana"),
        ],
    )
    graph = graph_with(monkeypatch, interpretation)

    result = invoke_turn(
        graph,
        {"configurable": {"thread_id": "multi-intent"}},
        "¿Cuánto cuesta el manicure y quiero agendar mañana?",
    )

    assert result["turn_interpretation"] == interpretation
    assert result["turn_interpretation"].information_queries == [
        "¿Cuánto cuesta el manicure?"
    ]
    assert result["appointment_request"].services


def test_threads_keep_independent_appointment_requests(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure")
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "pedicure")
            ]
        ),
    )

    first = invoke_turn(
        graph,
        {"configurable": {"thread_id": "client-one"}},
        "Quiero manicure.",
    )
    second = invoke_turn(
        graph,
        {"configurable": {"thread_id": "client-two"}},
        "Quiero pedicure.",
    )

    assert first["appointment_request"].services[0].family is ServiceFamily.MANICURE
    assert second["appointment_request"].services[0].family is ServiceFamily.PEDICURE


def test_time_clarification_retries_the_blocked_turn_atomically(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            intents=[TurnIntent.BOOK_APPOINTMENT],
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure"),
                change(AppointmentField.TIME, ChangeOperation.SET, "a las 3"),
            ],
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.TIME, ChangeOperation.SET, "De la tarde")
            ]
        ),
    )
    config = {"configurable": {"thread_id": "time-clarification"}}

    first = invoke_turn(graph, config, "Quiero manicure a las 3.")
    assert first["normalization_result"].status is NormalizationStatus.NEEDS_CLARIFICATION
    assert not first["appointment_request"].services

    second = invoke_turn(graph, config, "De la tarde.")
    request = second["appointment_request"]
    assert second["normalization_result"].status is NormalizationStatus.SUCCESS
    assert len(request.services) == 1
    assert request.services[0].family is ServiceFamily.MANICURE
    assert request.schedule.time.resolved_time == time(15, 0)


def test_pending_clarification_does_not_rebuild_for_side_question(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure"),
                change(AppointmentField.TIME, ChangeOperation.SET, "a las 3"),
            ]
        ),
        TurnInterpretation(
            intents=[TurnIntent.INFORMATION_QUERY],
            information_queries=["¿Cuánto cuesta el pedicure?"],
        ),
    )
    config = {"configurable": {"thread_id": "side-question"}}
    invoke_turn(graph, config, "Quiero manicure a las 3.")

    result = invoke_turn(graph, config, "¿Cuánto cuesta el pedicure?")
    assert result["normalization_result"].status is NormalizationStatus.SUCCESS
    assert not result["appointment_request"].services
    assert result["turn_interpretation"].information_queries == [
        "¿Cuánto cuesta el pedicure?"
    ]


def test_pending_clarification_is_isolated_by_thread(monkeypatch):
    graph = graph_with(
        monkeypatch,
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.SERVICES, ChangeOperation.SET, "manicure"),
                change(AppointmentField.TIME, ChangeOperation.SET, "a las 3"),
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                change(AppointmentField.TIME, ChangeOperation.SET, "De la tarde")
            ]
        ),
    )
    invoke_turn(
        graph,
        {"configurable": {"thread_id": "pending-one"}},
        "Quiero manicure a las 3.",
    )
    other = invoke_turn(
        graph,
        {"configurable": {"thread_id": "clean-two"}},
        "De la tarde.",
    )
    assert not other["appointment_request"].services
    assert (
        other["normalization_result"].status
        is NormalizationStatus.NEEDS_CLARIFICATION
    )
