from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from cne_agent.chains.conversation import create_conversation_chain
from cne_agent.graph.state import ConversationContext, ConversationState


def conversation_node(
    state: ConversationState,
    runtime: Runtime[ConversationContext],
) -> dict:
    conversation_chain = create_conversation_chain()

    messages = state["messages"]

    history = messages[:-1]
    current_message = messages[-1]

    response = conversation_chain.invoke(
        {
            "current_date": runtime.context["current_date"],
            "business_context": runtime.context["business_context"],
            "capabilities_context": runtime.context["capabilities_context"],
            "history": history,
            "user_input": current_message.content,
        }
    )

    return {
        "messages": [
            AIMessage(content=response)
        ]
    }