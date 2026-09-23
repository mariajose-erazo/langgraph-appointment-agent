from collections.abc import Sequence

from langchain_core.messages import BaseMessage, trim_messages


MAX_HISTORY_TOKENS = 2000


def trim_conversation_history(
    messages: Sequence[BaseMessage],
    max_tokens: int = MAX_HISTORY_TOKENS,
) -> list[BaseMessage]:
    return trim_messages(
        messages,
        max_tokens=max_tokens,
        token_counter="approximate",
        strategy="last",
        start_on="human",
        end_on="ai",
        include_system=False,
        allow_partial=False,
    )