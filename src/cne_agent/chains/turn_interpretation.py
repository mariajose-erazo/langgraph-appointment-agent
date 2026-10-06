"""Cadena independiente de texto a TurnInterpretation."""

from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda

from cne_agent.graph.history import trim_conversation_history
from cne_agent.interpretation.models import TurnInterpretation
from cne_agent.llm.client import create_llm
from cne_agent.prompts.turn_interpretation import (
    create_turn_interpretation_prompt,
)


# Limite inicial configurable para contexto de interpretacion. El recortador
# compartido conserva mensajes completos y no permite fragmentos parciales.
INTERPRETATION_HISTORY_MAX_TOKENS = 800


def create_turn_interpretation_chain(
    llm: BaseChatModel | None = None,
) -> Runnable:
    """Crea una cadena que devuelve TurnInterpretation o propaga el error."""

    model = llm if llm is not None else create_llm()
    structured_model = model.with_structured_output(
        TurnInterpretation,
        method="json_schema",
    )

    return (
        RunnableLambda(_prepare_input)
        | create_turn_interpretation_prompt()
        | structured_model
        | RunnableLambda(_require_turn_interpretation)
    )


def _prepare_input(value: Mapping[str, Any]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("la entrada debe ser un mapping")

    user_input = value.get("user_input")
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("user_input debe ser texto no vacio")

    history = value.get("history", ())
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise TypeError("history debe ser una secuencia de mensajes")
    if not all(isinstance(message, BaseMessage) for message in history):
        raise TypeError("history solo admite mensajes de LangChain")
    if history and not isinstance(history[-1], AIMessage):
        raise ValueError(
            "history debe contener intercambios completos y no incluir "
            "el turno actual"
        )

    trimmed_history = trim_conversation_history(
        history,
        max_tokens=INTERPRETATION_HISTORY_MAX_TOKENS,
    )
    return {"history": trimmed_history, "user_input": user_input}


def _require_turn_interpretation(value: object) -> TurnInterpretation:
    if not isinstance(value, TurnInterpretation):
        raise TypeError(
            "la salida estructurada no es una instancia de TurnInterpretation"
        )
    return value
