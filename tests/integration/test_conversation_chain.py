import os

import pytest

from cne_agent.chains.conversation import create_conversation_chain


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Los tests de integración con servicios externos están desactivados.",
)
def test_conversation_chain_returns_string():
    chain = create_conversation_chain()

    response = chain.invoke(
        {
            "current_date": "2026-09-17",
            "business_context": """
Servicios ofrecidos por Cne By Nails:
- Manicure semipermanente
""",
            "history": [],
            "user_input": "Hola, que servicios ofrecen?",
        }
    )

    assert isinstance(response, str)
    assert response.strip()