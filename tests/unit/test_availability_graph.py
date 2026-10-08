from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
import pytest

from cne_agent.appointments.in_memory_availability import InMemoryAvailabilityProvider
from cne_agent.appointments.readiness import AppointmentReadinessStatus
from cne_agent.appointments.scheduling import (
    AvailabilityStatus,
    ScheduleSnapshot,
    SchedulingPolicy,
    ServiceDefinition,
)
from cne_agent.appointments.request import ServiceFamily
from cne_agent.graph.nodes import success_response as response_module
from cne_agent.graph.workflow import create_conversation_graph
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedChange,
    TurnIntent,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)


SERVICES = (
    ServiceCatalogEntry("manicure", ServiceFamily.MANICURE, None, ("manicure",)),
)
PROFESSIONALS = (
    ProfessionalCatalogEntry("laura", "Laura"),
    ProfessionalCatalogEntry("valentina", "Valentina"),
)
POLICY = SchedulingPolicy(
    (ServiceDefinition("manicure", timedelta(minutes=60)),),
    timezone=BOGOTA,
)


class FakeResponseChain:
    def invoke(self, values):
        availability = values["availability_context"]
        if "disponibilidad confirmada" in availability:
            return "Laura está disponible. La cita aún no está reservada."
        return "Respuesta informativa autorizada."


class Queue:
    def __init__(self, *values):
        self.values = list(values)

    def invoke(self, _input):
        return self.values.pop(0)


def context():
    return {
        "current_date": "2026-10-07",
        "business_context": "Manicure.",
        "capabilities_context": "Consulta de disponibilidad habilitada.",
        "service_catalog": SERVICES,
        "professional_catalog": PROFESSIONALS,
        "reference_at": datetime(2026, 10, 7, 10, tzinfo=BOGOTA),
    }


def complete(intent=TurnIntent.CHECK_AVAILABILITY, *, information=False):
    intents = [intent]
    queries = []
    if information:
        intents.insert(0, TurnIntent.INFORMATION_QUERY)
        queries = ["¿Cuánto cuesta?"]
    return TurnInterpretation(
        intents=intents,
        information_queries=queries,
        appointment_changes=[
            InterpretedChange(field=AppointmentField.SERVICES, operation=ChangeOperation.SET, raw_text="manicure"),
            InterpretedChange(field=AppointmentField.DATE, operation=ChangeOperation.SET, raw_text="mañana"),
            InterpretedChange(field=AppointmentField.TIME, operation=ChangeOperation.SET, raw_text="15:00"),
            InterpretedChange(field=AppointmentField.PROFESSIONAL, operation=ChangeOperation.SET, raw_text="Laura"),
        ],
    )


def graph(monkeypatch, provider, *interpretations):
    monkeypatch.setattr(response_module, "create_conversation_chain", lambda: FakeResponseChain())
    queue = Queue(*interpretations)
    return create_conversation_graph(
        turn_interpretation_chain=RunnableLambda(queue.invoke),
        availability_provider=provider,
        scheduling_policy=POLICY,
    )


def invoke(compiled, thread, message="turno"):
    return compiled.invoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread}},
        context=context(),
    )


def test_complete_check_calls_provider_once_and_reports_available(monkeypatch):
    provider = InMemoryAvailabilityProvider(ScheduleSnapshot(("laura", "valentina")))
    result = invoke(graph(monkeypatch, provider, complete()), "check")
    assert provider.call_count == 1
    assert result["appointment_readiness"].status is AppointmentReadinessStatus.READY
    assert result["availability_result"].status is AvailabilityStatus.AVAILABLE
    assert "no está reservada" in result["messages"][-1].content


def test_incomplete_request_does_not_call_provider(monkeypatch):
    provider = InMemoryAvailabilityProvider(ScheduleSnapshot(("laura",)))
    interpretation = TurnInterpretation(
        intents=[TurnIntent.CHECK_AVAILABILITY],
        appointment_changes=[
            InterpretedChange(field=AppointmentField.SERVICES, operation=ChangeOperation.SET, raw_text="manicure"),
        ],
    )
    result = invoke(graph(monkeypatch, provider, interpretation), "incomplete")
    assert provider.call_count == 0
    assert result["availability_result"] is None
    assert "fecha" in result["messages"][-1].content


def test_book_only_reads_schedule_and_has_no_reservation_api(monkeypatch):
    provider = InMemoryAvailabilityProvider(ScheduleSnapshot(("laura", "valentina")))
    result = invoke(graph(monkeypatch, provider, complete(TurnIntent.BOOK_APPOINTMENT)), "book")
    assert provider.call_count == 1
    assert not hasattr(provider, "book")
    assert not hasattr(provider, "reserve")
    assert "no está reservada" in result["messages"][-1].content


def test_multi_intent_preserves_information_and_availability(monkeypatch):
    provider = InMemoryAvailabilityProvider(ScheduleSnapshot(("laura", "valentina")))
    result = invoke(graph(monkeypatch, provider, complete(information=True)), "multi")
    assert result["turn_interpretation"].information_queries == ["¿Cuánto cuesta?"]
    assert result["availability_result"].status is AvailabilityStatus.AVAILABLE


def test_provider_failure_propagates(monkeypatch):
    class BrokenProvider:
        def get_schedule(self, _query):
            raise ConnectionError("agenda unavailable")

    with pytest.raises(ConnectionError, match="agenda unavailable"):
        invoke(graph(monkeypatch, BrokenProvider(), complete()), "failure")


def test_missing_provider_is_a_technical_error(monkeypatch):
    with pytest.raises(RuntimeError, match="AvailabilityProvider"):
        invoke(graph(monkeypatch, None, complete()), "no-provider")


def test_new_turn_clears_derived_results_and_threads_are_isolated(monkeypatch):
    provider = InMemoryAvailabilityProvider(ScheduleSnapshot(("laura", "valentina")))
    compiled = graph(
        monkeypatch,
        provider,
        complete(),
        TurnInterpretation(intents=[TurnIntent.INFORMATION_QUERY], information_queries=["¿Precio?"]),
        TurnInterpretation(intents=[TurnIntent.INFORMATION_QUERY], information_queries=["¿Horario?"]),
    )
    first = invoke(compiled, "one")
    second = invoke(compiled, "one")
    other = invoke(compiled, "two")
    assert first["availability_result"] is not None
    assert second["availability_result"] is None
    assert second["appointment_readiness"] is None
    assert other["availability_result"] is None
    assert not other["appointment_request"].services
