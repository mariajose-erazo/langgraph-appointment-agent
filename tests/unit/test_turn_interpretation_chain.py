from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
import pytest

from cne_agent.chains.turn_interpretation import (
    INTERPRETATION_HISTORY_MAX_TOKENS,
    create_turn_interpretation_chain,
)
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedAmbiguity,
    InterpretedChange,
    TurnIntent,
    TurnInterpretation,
)
from cne_agent.prompts.turn_interpretation import (
    TURN_INTERPRETATION_SYSTEM_MESSAGE,
)


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.schema = None
        self.method = None
        self.received_messages = None

    def with_structured_output(self, schema, method=None, **kwargs):
        self.schema = schema
        self.method = method

        def invoke(prompt_value):
            self.received_messages = prompt_value.to_messages()
            if self.error is not None:
                raise self.error
            return self.result

        return RunnableLambda(invoke)


def invoke_with(result, user_input="mensaje", history=()):
    llm = FakeLLM(result=result)
    response = create_turn_interpretation_chain(llm).invoke(
        {"history": history, "user_input": user_input}
    )
    return response, llm


def test_requests_turn_interpretation_with_native_json_schema():
    response, llm = invoke_with(TurnInterpretation())

    assert isinstance(response, TurnInterpretation)
    assert llm.schema is TurnInterpretation
    assert llm.method == "json_schema"


def test_valid_empty_interpretation_is_a_successful_result():
    response, _ = invoke_with(TurnInterpretation())

    assert response == TurnInterpretation()


@pytest.mark.parametrize(
    "interpretation",
    [
        TurnInterpretation(intents=[TurnIntent.BOOK_APPOINTMENT]),
        TurnInterpretation(
            intents=[TurnIntent.INFORMATION_QUERY, TurnIntent.CHECK_AVAILABILITY],
            information_queries=["¿Cuánto cuesta el manicure?"],
        ),
        TurnInterpretation(
            appointment_changes=[
                InterpretedChange(
                    field=AppointmentField.SERVICES,
                    operation=ChangeOperation.SET,
                    raw_text="manicure",
                )
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                InterpretedChange(
                    field=AppointmentField.SERVICES,
                    operation=ChangeOperation.SET,
                    raw_text="manicure y pedicure",
                    raw_values=["manicure", "pedicure"],
                )
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                InterpretedChange(
                    field=AppointmentField.PROFESSIONAL,
                    operation=ChangeOperation.SET,
                    raw_text="cualquiera",
                )
            ]
        ),
        TurnInterpretation(
            appointment_changes=[
                InterpretedChange(
                    field=AppointmentField.DATE,
                    operation=ChangeOperation.SET,
                    raw_text="mañana",
                ),
                InterpretedChange(
                    field=AppointmentField.TIME,
                    operation=ChangeOperation.SET,
                    raw_text="a las 3",
                ),
            ]
        ),
        TurnInterpretation(
            intents=[TurnIntent.INFORMATION_QUERY],
            information_queries=["¿Cuánto cuesta el manicure?"],
        ),
        TurnInterpretation(
            ambiguities=[
                InterpretedAmbiguity(
                    field=AppointmentField.DATE,
                    description="Puede ser viernes o sábado.",
                )
            ]
        ),
    ],
)
def test_returns_valid_structured_interpretations(interpretation):
    response, _ = invoke_with(interpretation)

    assert response is interpretation


@pytest.mark.parametrize(
    ("operation", "raw_text"),
    [
        (ChangeOperation.ADD, "pedicure"),
        (ChangeOperation.REMOVE, "pedicure"),
        (ChangeOperation.SET, "manicure"),
        (ChangeOperation.CLEAR, None),
    ],
)
def test_supports_each_service_operation(operation, raw_text):
    interpretation = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.SERVICES,
                operation=operation,
                raw_text=raw_text,
            )
        ]
    )

    response, _ = invoke_with(interpretation)

    assert response.appointment_changes[0].operation is operation


@pytest.mark.parametrize(
    "phrase",
    ["quiero agendar", "quiero reservar", "quiero una cita", "agéndame"],
)
def test_prompt_maps_explicit_booking_phrases_to_book_intent(phrase):
    assert phrase in TURN_INTERPRETATION_SYSTEM_MESSAGE
    assert "debe incluir\n  BOOK_APPOINTMENT" in TURN_INTERPRETATION_SYSTEM_MESSAGE


@pytest.mark.parametrize(
    ("example", "operation"),
    [
        ("quiero manicure", "SET"),
        ("quiero manicure y pedicure", "SET"),
        ("también quiero pedicure", "ADD"),
        ("agrégame pedicure", "ADD"),
        ("ya no quiero pedicure", "REMOVE"),
        ("mejor solo manicure", "SET"),
    ],
)
def test_prompt_defines_service_operation_semantics(example, operation):
    assert example in TURN_INTERPRETATION_SYSTEM_MESSAGE
    example_position = TURN_INTERPRETATION_SYSTEM_MESSAGE.index(example)
    nearby_instruction = TURN_INTERPRETATION_SYSTEM_MESSAGE[
        max(0, example_position - 120) : example_position + len(example) + 120
    ]
    assert operation in nearby_instruction


def test_service_delta_adds_only_the_current_service():
    history = [
        HumanMessage(content="Quiero manicure."),
        AIMessage(content="¿Deseas agregar algo más?"),
    ]
    expected = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.SERVICES,
                operation=ChangeOperation.ADD,
                raw_text="pedicure",
            )
        ]
    )

    response, _ = invoke_with(expected, "También quiero pedicure.", history)

    assert response.appointment_changes == expected.appointment_changes
    assert len(response.appointment_changes) == 1
    assert response.appointment_changes[0].raw_text == "pedicure"


def test_preserves_delta_when_current_turn_adds_professional():
    history = [
        HumanMessage(content="Quiero manicure mañana."),
        AIMessage(content="¿Con qué profesional?"),
    ]
    expected = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.PROFESSIONAL,
                operation=ChangeOperation.SET,
                raw_text="Laura",
            )
        ]
    )

    response, llm = invoke_with(expected, "Con Laura.", history)

    assert response.appointment_changes == expected.appointment_changes
    assert len(response.appointment_changes) == 1
    assert llm.received_messages[-1].content == "Con Laura."
    assert sum(message.content == "Con Laura." for message in llm.received_messages) == 1


def test_preserves_delta_when_current_turn_corrects_professional():
    history = [
        HumanMessage(content="Quiero con Laura."),
        AIMessage(content="Entendido."),
    ]
    expected = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.PROFESSIONAL,
                operation=ChangeOperation.SET,
                raw_text="Valentina",
            )
        ]
    )

    response, _ = invoke_with(expected, "Mejor con Valentina.", history)

    assert response.appointment_changes == expected.appointment_changes
    assert len(response.appointment_changes) == 1


def test_any_professional_phrase_is_set_and_preserved_literally():
    raw_text = "ya no importa con quién"
    expected = TurnInterpretation(
        appointment_changes=[
            InterpretedChange(
                field=AppointmentField.PROFESSIONAL,
                operation=ChangeOperation.SET,
                raw_text=raw_text,
            )
        ]
    )

    response, _ = invoke_with(expected, raw_text)

    assert response.appointment_changes[0].raw_text == raw_text
    assert response.appointment_changes[0].operation is ChangeOperation.SET


def test_llm_exception_is_propagated_and_not_converted_to_empty_result():
    llm = FakeLLM(error=TimeoutError("Gemini timeout"))

    with pytest.raises(TimeoutError, match="Gemini timeout"):
        create_turn_interpretation_chain(llm).invoke(
            {"history": [], "user_input": "Quiero manicure"}
        )


def test_invalid_structured_result_is_rejected():
    llm = FakeLLM(result={"intents": []})

    with pytest.raises(TypeError, match="TurnInterpretation"):
        create_turn_interpretation_chain(llm).invoke(
            {"history": [], "user_input": "Hola"}
        )


def test_history_must_be_complete_and_cannot_include_current_turn():
    llm = FakeLLM(result=TurnInterpretation())

    with pytest.raises(ValueError, match="intercambios completos"):
        create_turn_interpretation_chain(llm).invoke(
            {
                "history": [HumanMessage(content="Con Laura.")],
                "user_input": "Con Laura.",
            }
        )


def test_history_limit_is_an_explicit_initial_configuration():
    assert INTERPRETATION_HISTORY_MAX_TOKENS == 800


def test_history_trimming_preserves_complete_exchanges():
    history = []
    for index in range(20):
        history.extend(
            [
                HumanMessage(content=f"Pregunta {index}. " * 30),
                AIMessage(content=f"Respuesta {index}. " * 30),
            ]
        )

    _, llm = invoke_with(TurnInterpretation(), "Turno actual.", history)
    contextual_messages = llm.received_messages[1:-1]

    assert len(contextual_messages) < len(history)
    assert len(contextual_messages) % 2 == 0
    assert isinstance(contextual_messages[0], HumanMessage)
    assert isinstance(contextual_messages[-1], AIMessage)
    assert llm.received_messages[-1].content == "Turno actual."


def test_chain_does_not_import_normalizer_or_merge():
    import cne_agent.chains.turn_interpretation as module

    source_names = set(module.__dict__)
    assert "normalize_turn_interpretation" not in source_names
    assert "merge_appointment_request" not in source_names
