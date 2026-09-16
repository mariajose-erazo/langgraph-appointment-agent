import os

import pytest

from cne_agent.llm.client import create_llm


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Los tests de integración con servicios externos están desactivados.",
)
def test_gemini_connection():
    llm = create_llm()

    response = llm.invoke(
        "Responde únicamente con: OK"
    )

    assert response.content
    print(f"Gemini respondió: {response.content}")