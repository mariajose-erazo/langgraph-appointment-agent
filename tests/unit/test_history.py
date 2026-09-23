from langchain_core.messages import AIMessage, HumanMessage

from cne_agent.graph.history import trim_conversation_history


def test_trim_history_preserves_messages_when_under_limit():
    messages = [
        HumanMessage(content="Hola."),
        AIMessage(content="Hola, ¿en qué puedo ayudarte?"),
    ]

    trimmed = trim_conversation_history(
        messages,
        max_tokens=100,
    )

    assert len(trimmed) == 2

    assert isinstance(trimmed[0], HumanMessage)
    assert trimmed[0].content == "Hola."

    assert isinstance(trimmed[1], AIMessage)
    assert trimmed[1].content == "Hola, ¿en qué puedo ayudarte?"

def test_trim_history_removes_old_messages_when_over_limit():
    messages = [
        HumanMessage(
            content="Mensaje antiguo del cliente. " * 30
        ),
        AIMessage(
            content="Respuesta antigua del asistente. " * 30
        ),
        HumanMessage(
            content="Mensaje intermedio del cliente. " * 30
        ),
        AIMessage(
            content="Respuesta intermedia del asistente. " * 30
        ),
        HumanMessage(
            content="Mensaje reciente del cliente."
        ),
        AIMessage(
            content="Respuesta reciente del asistente."
        ),
    ]

    trimmed = trim_conversation_history(
        messages,
        max_tokens=100,
    )

    assert len(trimmed) < len(messages)

    assert trimmed[-2].content == "Mensaje reciente del cliente."
    assert trimmed[-1].content == "Respuesta reciente del asistente." 


def test_trim_history_keeps_valid_conversation_boundaries():
    messages = [
        HumanMessage(
            content="Mensaje antiguo. " * 40
        ),
        AIMessage(
            content="Respuesta antigua. " * 40
        ),
        HumanMessage(
            content="Pregunta reciente."
        ),
        AIMessage(
            content="Respuesta reciente."
        ),
    ]

    trimmed = trim_conversation_history(
        messages,
        max_tokens=80,
    )

    assert trimmed

    assert isinstance(
        trimmed[0],
        HumanMessage,
    )

    assert isinstance(
        trimmed[-1],
        AIMessage,
    )       