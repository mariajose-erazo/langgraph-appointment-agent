"""Nodo de interpretación estructurada del último turno."""

from collections.abc import Callable

from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable

from cne_agent.chains.turn_interpretation import (
    create_turn_interpretation_chain,
)
from cne_agent.graph.state import ConversationState
from cne_agent.interpretation.models import TurnInterpretation


InterpretTurnNode = Callable[
    [ConversationState],
    dict[str, TurnInterpretation],
]


def create_interpret_turn_node(
    chain: Runnable | None = None,
) -> InterpretTurnNode:
    """Crea el nodo, permitiendo inyectar una cadena determinista."""

    def interpret_turn(
        state: ConversationState,
    ) -> dict[str, TurnInterpretation]:
        messages = state.get("messages", [])
        if not messages or not isinstance(messages[-1], HumanMessage):
            raise ValueError(
                "el último mensaje debe ser un HumanMessage"
            )

        interpretation_chain = (
            chain if chain is not None else create_turn_interpretation_chain()
        )
        interpretation = interpretation_chain.invoke(
            {
                "history": messages[:-1],
                "user_input": messages[-1].content,
            }
        )
        if not isinstance(interpretation, TurnInterpretation):
            raise TypeError(
                "la cadena no devolvió una instancia de TurnInterpretation"
            )
        return {"turn_interpretation": interpretation}

    return interpret_turn
