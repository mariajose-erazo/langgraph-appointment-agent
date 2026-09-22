from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from cne_agent.graph.nodes.conversation import conversation_node
from cne_agent.graph.state import ConversationContext, ConversationState


def create_conversation_graph():
    graph = StateGraph(
        state_schema=ConversationState,
        context_schema=ConversationContext,
    )

    graph.add_node(
        "conversation",
        conversation_node,
    )

    graph.add_edge(
        START,
        "conversation",
    )

    graph.add_edge(
        "conversation",
        END,
    )

    memory = InMemorySaver()

    return graph.compile(
        checkpointer=memory,
    )