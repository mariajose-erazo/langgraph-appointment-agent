import pickle

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.runnables import Runnable

from cne_agent.graph.nodes.conversation import conversation_node
from cne_agent.graph.nodes.initialize_appointment_request import (
    initialize_appointment_request,
)
from cne_agent.graph.nodes.interpret_turn import create_interpret_turn_node
from cne_agent.graph.nodes.normalize_turn import normalize_turn
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
    graph.add_node("conversation", conversation_node)

    graph.add_edge(
        START,
        "initialize_appointment_request",
    )
    graph.add_edge("initialize_appointment_request", "interpret_turn")
    graph.add_edge("interpret_turn", "normalize_turn")
    graph.add_edge("normalize_turn", "conversation")
    graph.add_edge("conversation", END)

    # Este checkpointer es local y efímero. Pickle preserva los dataclasses
    # inmutables del dominio, que JsonPlus reconstruye como None.
    memory = InMemorySaver(serde=pickle)

    return graph.compile(
        checkpointer=memory,
    )
