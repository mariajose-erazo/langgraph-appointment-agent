from cne_agent.interpretation.clarification_resolution import (
    reconcile_clarification,
)
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedChange,
    TurnIntent,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    NormalizationIssue,
    NormalizationIssueCode,
    NormalizationIssueKind,
    NormalizationResult,
    NormalizationStatus,
)


def change(field, raw_text):
    return InterpretedChange(
        field=field,
        operation=ChangeOperation.SET,
        raw_text=raw_text,
    )


def previous_turn():
    return TurnInterpretation(
        intents=[TurnIntent.BOOK_APPOINTMENT],
        appointment_changes=[
            change(AppointmentField.SERVICES, "manicure"),
            change(AppointmentField.TIME, "a las 3"),
        ],
    )


def pending_result():
    return NormalizationResult(
        NormalizationStatus.NEEDS_CLARIFICATION,
        None,
        (
            NormalizationIssue(
                NormalizationIssueCode.AMBIGUOUS_TIME,
                NormalizationIssueKind.CLARIFICATION,
                AppointmentField.TIME,
                "falta periodo",
                "a las 3",
            ),
        ),
    )


def test_reconciles_period_with_blocked_turn_atomically():
    current = TurnInterpretation(
        appointment_changes=[change(AppointmentField.TIME, "De la tarde")]
    )
    result = reconcile_clarification(previous_turn(), pending_result(), current)

    assert result.intents == [TurnIntent.BOOK_APPOINTMENT]
    assert [item.field for item in result.appointment_changes] == [
        AppointmentField.SERVICES,
        AppointmentField.TIME,
    ]
    assert result.appointment_changes[1].raw_text == "a las 3 de la tarde"


def test_does_not_reconcile_a_side_information_query():
    current = TurnInterpretation(
        intents=[TurnIntent.INFORMATION_QUERY],
        information_queries=["¿Cuánto cuesta el pedicure?"],
    )
    assert reconcile_clarification(previous_turn(), pending_result(), current) is current


def test_does_not_combine_a_contradictory_new_time():
    current = TurnInterpretation(
        appointment_changes=[change(AppointmentField.TIME, "a las 4 de la tarde")]
    )
    assert reconcile_clarification(previous_turn(), pending_result(), current) is current
