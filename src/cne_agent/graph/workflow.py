import pickle

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.runnables import Runnable

from cne_agent.graph.nodes.clarify_turn import clarify_turn
from cne_agent.graph.nodes.initialize_appointment_request import (
    initialize_appointment_request,
)
from cne_agent.graph.nodes.interpret_turn import create_interpret_turn_node
from cne_agent.graph.nodes.invalid_turn import invalid_turn
from cne_agent.graph.nodes.normalize_turn import normalize_turn
from cne_agent.graph.nodes.success_response import success_response
from cne_agent.graph.routing import route_after_normalization
from cne_agent.graph.state import ConversationContext, ConversationState


def create_conversation_graph(
    *,
    turn_interpretation_chain: Runnable | None = None,
):
    graph = StateGraph(
        state_schema=ConversationState,
        context_schema=ConversationContext,
        input_schema=MessagesState,
        output_schema=ConversationState,
    )

    graph.add_node("initialize_appointment_request", initialize_appointment_request)
    graph.add_node(
        "interpret_turn",
        create_interpret_turn_node(turn_interpretation_chain),
    )
    graph.add_node("normalize_turn", normalize_turn)
    graph.add_node("clarify_turn", clarify_turn)
    graph.add_node("invalid_turn", invalid_turn)
    graph.add_node("success_response", success_response)

    graph.add_edge(
        START,
        "initialize_appointment_request",
    )
    graph.add_edge("initialize_appointment_request", "interpret_turn")
    graph.add_edge("interpret_turn", "normalize_turn")
    graph.add_conditional_edges(
        "normalize_turn",
        route_after_normalization,
        {
            "clarification": "clarify_turn",
            "invalid": "invalid_turn",
            "success_information": "success_response",
            "success_conversation": "success_response",
        },
    )
    graph.add_edge("clarify_turn", END)
    graph.add_edge("invalid_turn", END)
    graph.add_edge("success_response", END)

    # Este checkpointer es local y efímero. Pickle preserva los dataclasses
    # inmutables del dominio, que JsonPlus reconstruye como None.
    memory = InMemorySaver(serde=pickle)

    return graph.compile(
        checkpointer=memory,
    )
