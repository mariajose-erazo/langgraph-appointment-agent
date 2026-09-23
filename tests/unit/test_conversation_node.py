from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from cne_agent.graph.nodes import conversation as conversation_module


class FakeConversationChain:
    def __init__(self):
        self.received_input = None

    def invoke(self, input_data):
        self.received_input = input_data
        return "Respuesta simulada."


def test_conversation_node_uses_trimmed_history(monkeypatch):
    fake_chain = FakeConversationChain()

    monkeypatch.setattr(
        conversation_module,
        "create_conversation_chain",
        lambda: fake_chain,
    )

    received_by_trimmer = {}

    def fake_trim_conversation_history(messages):
        received_by_trimmer["messages"] = messages

        return messages[-2:]

    monkeypatch.setattr(
        conversation_module,
        "trim_conversation_history",
        fake_trim_conversation_history,
    )

    state = {
        "messages": [
            HumanMessage(
                content="Mensaje antiguo del cliente."
            ),
            AIMessage(
                content="Respuesta antigua del asistente."
            ),
            HumanMessage(
                content="Mensaje reciente del cliente."
            ),
            AIMessage(
                content="Respuesta reciente del asistente."
            ),
            HumanMessage(
                content="Mensaje actual."
            ),
        ]
    }

    runtime = Runtime(
        context={
            "current_date": "2026-09-22",
            "business_context": "Contexto de prueba.",
            "capabilities_context": (
                "No hay capacidades operativas habilitadas."
            ),
        }
    )

    result = conversation_module.conversation_node(
        state,
        runtime,
    )

    received_history = fake_chain.received_input["history"]

    assert len(received_by_trimmer["messages"]) == 4

    assert received_by_trimmer["messages"][0].content == (
        "Mensaje antiguo del cliente."
    )

    assert len(received_history) == 2

    assert received_history[0].content == (
        "Mensaje reciente del cliente."
    )

    assert received_history[1].content == (
        "Respuesta reciente del asistente."
    )

    assert (
        fake_chain.received_input["user_input"]
        == "Mensaje actual."
    )

    assert isinstance(
        result["messages"][0],
        AIMessage,
    )

    assert (
        result["messages"][0].content
        == "Respuesta simulada."
    )