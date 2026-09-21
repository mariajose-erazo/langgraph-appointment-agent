from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from cne_agent.prompts.conversation import create_conversation_prompt


def test_conversation_prompt_formats_expected_messages():
    prompt = create_conversation_prompt()

    history = [
        HumanMessage(
            content="Quiero manicure semipermanente el viernes a las 3."
        ),
        AIMessage(
            content="La solicitud sigue pendiente de confirmacion."
        ),
    ]

    messages = prompt.format_messages(
        current_date="2026-09-17",
        business_context="""
Servicios ofrecidos:
- Manicure semipermanente
""",
        history=history,
        user_input="Se puede pagar en cuotas?",
    )

    # SystemMessage principal
    assert isinstance(messages[0], SystemMessage)
    assert "2026-09-17" in messages[0].content

    # Contexto autorizado
    assert isinstance(messages[1], SystemMessage)
    assert "Manicure semipermanente" in messages[1].content

    # Instrucción que identifica el few-shot como ficticio
    assert isinstance(messages[2], SystemMessage)
    assert "ejemplos ficticios" in messages[2].content.lower()

    # El few-shot debe estar presente
    assert any(
        "Quiero reservar un servicio para el viernes a las 3."
        in message.content
        for message in messages
    )

    # MessagesPlaceholder debe insertar el historial real
    assert isinstance(messages[-3], HumanMessage)
    assert (
        messages[-3].content
        == "Quiero manicure semipermanente el viernes a las 3."
    )

    assert isinstance(messages[-2], AIMessage)
    assert (
        messages[-2].content
        == "La solicitud sigue pendiente de confirmacion."
    )

    # El mensaje actual siempre debe quedar al final
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == "Se puede pagar en cuotas?"


def test_conversation_prompt_works_without_history():
    prompt = create_conversation_prompt()

    messages = prompt.format_messages(
        current_date="2026-09-17",
        business_context="""
Servicios ofrecidos:
- Manicure semipermanente
""",
        user_input="Hola, quiero informacion sobre manicure semipermanente.",
    )

    assert isinstance(messages[0], SystemMessage)
    assert "2026-09-17" in messages[0].content

    assert isinstance(messages[1], SystemMessage)
    assert "Manicure semipermanente" in messages[1].content

    assert isinstance(messages[-1], HumanMessage)
    assert (
        messages[-1].content
        == "Hola, quiero informacion sobre manicure semipermanente."
    )    