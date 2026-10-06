import os
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from cne_agent.graph.workflow import create_conversation_graph
from cne_agent.graph.nodes import conversation as conversation_module
from cne_agent.appointments.request import ServiceFamily
from cne_agent.interpretation.models import TurnInterpretation
from cne_agent.interpretation.normalizer import (
    BOGOTA,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)


SERVICE_CATALOG = (
    ServiceCatalogEntry(
        "manicure-semipermanente",
        ServiceFamily.MANICURE,
        "semipermanente",
        ("manicure semipermanente",),
    ),
    ServiceCatalogEntry("pedicure", ServiceFamily.PEDICURE, None, ("pedicure",)),
)
PROFESSIONAL_CATALOG = (
    ProfessionalCatalogEntry("laura", "Laura"),
)

class FakeConversationChain:
    def invoke(self, input_data):
        return "Respuesta simulada."


class FakeInterpretationChain:
    def invoke(self, input_data):
        return TurnInterpretation()


def graph_context():
    return {
        "current_date": "2026-09-22",
        "business_context": "Servicios de prueba.",
        "capabilities_context": "No hay capacidades operativas habilitadas.",
        "service_catalog": SERVICE_CATALOG,
        "professional_catalog": PROFESSIONAL_CATALOG,
        "reference_at": datetime(2026, 9, 22, 10, tzinfo=BOGOTA),
    }

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Los tests de integración con servicios externos están desactivados.",
)
def test_graph_preserves_conversation_history():
    graph = create_conversation_graph()

    config = {
        "configurable": {
            "thread_id": "test-client-001"
        }
    }

    context = graph_context()

    graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Quiero manicure semipermanente."
                )
            ]
        },
        config=config,
        context=context,
    )

    state = graph.get_state(config)

    messages = state.values["messages"]

    assert len(messages) == 2

    assert isinstance(
        messages[0],
        HumanMessage,
    )

    assert (
        messages[0].content
        == "Quiero manicure semipermanente."
    )

    assert isinstance(
        messages[1],
        AIMessage,
    )

    assert messages[1].content.strip()    

@pytest.mark.integration
def test_graph_keeps_threads_isolated(monkeypatch):
    fake_chain = FakeConversationChain()

    monkeypatch.setattr(
        conversation_module,
        "create_conversation_chain",
        lambda: fake_chain,
    )

    graph = create_conversation_graph(
        turn_interpretation_chain=FakeInterpretationChain()
    )

    context = graph_context()

    config_client_1 = {
        "configurable": {
            "thread_id": "test-client-001"
        }
    }

    config_client_2 = {
        "configurable": {
            "thread_id": "test-client-002"
        }
    }

    graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Quiero manicure semipermanente."
                )
            ]
        },
        config=config_client_1,
        context=context,
    )

    graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Hola."
                )
            ]
        },
        config=config_client_2,
        context=context,
    )

    state_client_1 = graph.get_state(
        config_client_1
    )

    state_client_2 = graph.get_state(
        config_client_2
    )

    messages_client_1 = (
        state_client_1.values["messages"]
    )

    messages_client_2 = (
        state_client_2.values["messages"]
    )

    assert len(messages_client_1) == 2
    assert len(messages_client_2) == 2

    assert (
        messages_client_1[0].content
        == "Quiero manicure semipermanente."
    )

    assert (
        messages_client_2[0].content
        == "Hola."
    )

    assert (
        messages_client_1[1].content
        == "Respuesta simulada."
    )

    assert (
        messages_client_2[1].content
        == "Respuesta simulada."
    )

    assert all(
        message.content
        != "Quiero manicure semipermanente."
        for message in messages_client_2
    )

@pytest.mark.integration
def test_graph_preserves_full_state_across_turns(monkeypatch):
    fake_chain = FakeConversationChain()

    monkeypatch.setattr(
        conversation_module,
        "create_conversation_chain",
        lambda: fake_chain,
    )

    graph = create_conversation_graph(
        turn_interpretation_chain=FakeInterpretationChain()
    )

    config = {
        "configurable": {
            "thread_id": "test-full-history"
        }
    }

    context = graph_context()

    user_messages = [
        "Primer mensaje.",
        "Segundo mensaje.",
        "Tercer mensaje.",
    ]

    for content in user_messages:
        graph.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=content
                    )
                ]
            },
            config=config,
            context=context,
        )

    state = graph.get_state(config)

    messages = state.values["messages"]

    assert len(messages) == 6

    assert messages[0].content == "Primer mensaje."
    assert messages[1].content == "Respuesta simulada."

    assert messages[2].content == "Segundo mensaje."
    assert messages[3].content == "Respuesta simulada."

    assert messages[4].content == "Tercer mensaje."    
    assert messages[5].content == "Respuesta simulada."
