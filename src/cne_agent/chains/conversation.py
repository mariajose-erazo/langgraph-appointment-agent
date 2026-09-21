from langchain_core.output_parsers import StrOutputParser

from cne_agent.llm.client import create_llm
from cne_agent.prompts.conversation import create_conversation_prompt


def create_conversation_chain():
    prompt = create_conversation_prompt()
    llm = create_llm()
    parser = StrOutputParser()

    return prompt | llm | parser