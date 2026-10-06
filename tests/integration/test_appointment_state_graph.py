import os
from datetime import date, datetime

from langchain_core.messages import HumanMessage
import pytest

from cne_agent.appointments.request import (
    ProfessionalStatus,
    ServiceFamily,
)
from cne_agent.graph.nodes import conversation as conversation_module
from cne_agent.graph.workflow import create_conversation_graph
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)


class FakeConversationChain:
    def invoke(self, _input_data):
        return "Respuesta simulada."


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Los tests de integración con servicios externos están desactivados.",
)
def test_real_gemini_graph_accumulates_request_across_turns(monkeypatch):
    monkeypatch.setattr(
        conversation_module,
        "create_conversation_chain",
        lambda: FakeConversationChain(),
    )
    graph = create_conversation_graph()
    config = {"configurable": {"thread_id": "real-appointment-state"}}
    context = {
        "current_date": "2026-10-05",
        "business_context": "Servicios: manicure. Profesional: Laura.",
        "capabilities_context": "No hay capacidades operativas habilitadas.",
        "service_catalog": (
            ServiceCatalogEntry(
                "manicure",
                ServiceFamily.MANICURE,
                None,
                ("manicure",),
            ),
        ),
        "professional_catalog": (
            ProfessionalCatalogEntry("laura", "Laura"),
        ),
        "reference_at": datetime(2026, 10, 5, 10, tzinfo=BOGOTA),
    }

    graph.invoke(
        {"messages": [HumanMessage(content="Quiero manicure mañana.")]},
        config=config,
        context=context,
    )
    result = graph.invoke(
        {"messages": [HumanMessage(content="Con Laura.")]},
        config=config,
        context=context,
    )

    request = result["appointment_request"]
    assert request.services[0].family is ServiceFamily.MANICURE
    assert request.schedule.date.resolved_date == date(2026, 10, 6)
    assert request.professional.status is ProfessionalStatus.PREFERRED
    assert request.professional.ranked[0].canonical_id == "laura"
