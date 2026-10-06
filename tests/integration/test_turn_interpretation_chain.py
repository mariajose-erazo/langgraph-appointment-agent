import os

import pytest

from cne_agent.chains.turn_interpretation import (
    create_turn_interpretation_chain,
)
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    TurnIntent,
    TurnInterpretation,
)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Los tests de integración con servicios externos están desactivados.",
)
def test_real_gemini_returns_structured_turn_interpretation():
    chain = create_turn_interpretation_chain()

    response = chain.invoke(
        {
            "history": [],
            "user_input": "Quiero agendar manicure mañana.",
        }
    )

    assert isinstance(response, TurnInterpretation)
    assert TurnIntent.BOOK_APPOINTMENT in response.intents
    changes = {change.field: change for change in response.appointment_changes}
    assert changes[AppointmentField.SERVICES].raw_text == "manicure"
    assert changes[AppointmentField.SERVICES].operation is ChangeOperation.SET
    assert changes[AppointmentField.DATE].raw_text == "mañana"
    assert changes[AppointmentField.DATE].operation is ChangeOperation.SET
