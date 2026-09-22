from typing import TypedDict

from langgraph.graph import MessagesState


class ConversationState(MessagesState):
    pass


class ConversationContext(TypedDict):
    current_date: str
    business_context: str
    capabilities_context: str