import pytest
from pydantic import ValidationError

from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedAmbiguity,
    InterpretedChange,
    TurnIntent,
    TurnInterpretation,
)


def test_turn_supports_multiple_intents():
    interpretation = TurnInterpretation(
        intents=[
            TurnIntent.INFORMATION_QUERY,
            TurnIntent.CHECK_AVAILABILITY,
            TurnIntent.BOOK_APPOINTMENT,
        ],
        information_queries=["precio del manicure"],
    )

    assert interpretation.intents == [
        TurnIntent.INFORMATION_QUERY,
        TurnIntent.CHECK_AVAILABILITY,
        TurnIntent.BOOK_APPOINTMENT,
    ]


@pytest.mark.parametrize("expression", ["mañana", "el próximo viernes"])
def test_temporal_expressions_are_preserved(expression):
    change = InterpretedChange(
        field=AppointmentField.DATE,
        operation=ChangeOperation.SET,
        raw_text=expression,
    )

    assert change.raw_text == expression


def test_clear_accepts_no_raw_text():
    change = InterpretedChange(
        field=AppointmentField.TIME,
        operation=ChangeOperation.CLEAR,
    )

    assert change.raw_text is None
    assert change.suggested_id is None


@pytest.mark.parametrize(
    "operation",
    [ChangeOperation.SET, ChangeOperation.ADD, ChangeOperation.REMOVE],
)
@pytest.mark.parametrize("raw_text", [None, "", "   "])
def test_non_clear_operations_require_non_empty_raw_text(
    operation, raw_text
):
    with pytest.raises(ValidationError, match="requieren raw_text"):
        InterpretedChange(
            field=AppointmentField.SERVICES,
            operation=operation,
            raw_text=raw_text,
        )


def test_professional_can_have_a_suggested_identifier():
    change = InterpretedChange(
        field=AppointmentField.PROFESSIONAL,
        operation=ChangeOperation.SET,
        raw_text="Lau",
        suggested_id="laura",
    )

    assert change.raw_text == "Lau"
    assert change.suggested_id == "laura"


@pytest.mark.parametrize(
    "operation",
    [
        ChangeOperation.ADD,
        ChangeOperation.REMOVE,
        ChangeOperation.SET,
        ChangeOperation.CLEAR,
    ],
)
def test_services_accept_all_change_operations(operation):
    change = InterpretedChange(
        field=AppointmentField.SERVICES,
        operation=operation,
        raw_text=None if operation is ChangeOperation.CLEAR else "manicure",
    )

    assert change.operation is operation


def test_service_set_accepts_multiple_raw_values():
    change = InterpretedChange(
        field=AppointmentField.SERVICES,
        operation=ChangeOperation.SET,
        raw_text="manicure y pedicure",
        raw_values=["manicure", "pedicure"],
    )

    assert change.raw_values == ["manicure", "pedicure"]


@pytest.mark.parametrize(
    "operation", [ChangeOperation.ADD, ChangeOperation.REMOVE]
)
def test_incremental_service_change_rejects_multiple_raw_values(operation):
    with pytest.raises(ValidationError, match="como máximo un raw_value"):
        InterpretedChange(
            field=AppointmentField.SERVICES,
            operation=operation,
            raw_text="manicure y pedicure",
            raw_values=["manicure", "pedicure"],
        )


@pytest.mark.parametrize("raw_value", ["", "   "])
def test_service_raw_values_reject_blank_items(raw_value):
    with pytest.raises(ValidationError, match="valores vacíos"):
        InterpretedChange(
            field=AppointmentField.SERVICES,
            operation=ChangeOperation.SET,
            raw_text="manicure",
            raw_values=[raw_value],
        )


@pytest.mark.parametrize(
    "field",
    [
        AppointmentField.DATE,
        AppointmentField.TIME,
        AppointmentField.REMOVAL,
    ],
)
@pytest.mark.parametrize(
    "operation", [ChangeOperation.SET, ChangeOperation.CLEAR]
)
def test_scalar_fields_accept_set_and_clear(field, operation):
    change = InterpretedChange(
        field=field,
        operation=operation,
        raw_text=None if operation is ChangeOperation.CLEAR else "original",
    )

    assert change.operation is operation


@pytest.mark.parametrize(
    "field",
    [
        AppointmentField.DATE,
        AppointmentField.TIME,
        AppointmentField.REMOVAL,
    ],
)
@pytest.mark.parametrize(
    "operation", [ChangeOperation.ADD, ChangeOperation.REMOVE]
)
def test_scalar_fields_reject_incremental_operations(field, operation):
    with pytest.raises(ValidationError, match="no es compatible"):
        InterpretedChange(
            field=field,
            operation=operation,
            raw_text="original",
        )


@pytest.mark.parametrize(
    "field",
    [
        AppointmentField.PROFESSIONAL,
        AppointmentField.DATE,
        AppointmentField.TIME,
        AppointmentField.REMOVAL,
    ],
)
def test_raw_values_are_exclusive_to_services(field):
    with pytest.raises(ValidationError, match="solo puede usarse"):
        InterpretedChange(
            field=field,
            operation=ChangeOperation.SET,
            raw_text="original",
            raw_values=["valor"],
        )


@pytest.mark.parametrize("raw_text", ["Lau", "cualquiera"])
def test_professional_accepts_specific_or_any_selection(raw_text):
    change = InterpretedChange(
        field=AppointmentField.PROFESSIONAL,
        operation=ChangeOperation.SET,
        raw_text=raw_text,
    )

    assert change.raw_text == raw_text


def test_professional_selection_can_be_cleared():
    change = InterpretedChange(
        field=AppointmentField.PROFESSIONAL,
        operation=ChangeOperation.CLEAR,
    )

    assert change.operation is ChangeOperation.CLEAR


@pytest.mark.parametrize(
    "operation", [ChangeOperation.ADD, ChangeOperation.REMOVE]
)
def test_professional_rejects_ranked_or_alternative_operations(operation):
    with pytest.raises(ValidationError, match="no es compatible"):
        InterpretedChange(
            field=AppointmentField.PROFESSIONAL,
            operation=operation,
            raw_text="Lau",
        )


@pytest.mark.parametrize(
    "field",
    [
        AppointmentField.SERVICES,
        AppointmentField.DATE,
        AppointmentField.TIME,
        AppointmentField.REMOVAL,
    ],
)
def test_suggested_identifier_is_rejected_for_other_fields(field):
    with pytest.raises(ValidationError, match="solo puede usarse"):
        InterpretedChange(
            field=field,
            operation=ChangeOperation.SET,
            raw_text="texto original",
            suggested_id="candidate-id",
        )


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        TurnInterpretation(unexpected="value")

    with pytest.raises(ValidationError, match="Extra inputs"):
        InterpretedChange(
            field=AppointmentField.DATE,
            operation=ChangeOperation.SET,
            raw_text="mañana",
            unexpected="value",
        )

    with pytest.raises(ValidationError, match="Extra inputs"):
        InterpretedAmbiguity(
            field=AppointmentField.TIME,
            description="no especificó si era a. m. o p. m.",
            unexpected="value",
        )


@pytest.mark.parametrize(
    ("field", "operation"),
    [("location", "set"), ("date", "replace")],
)
def test_invalid_enum_values_are_rejected(field, operation):
    with pytest.raises(ValidationError):
        InterpretedChange(
            field=field,
            operation=operation,
            raw_text="texto original",
        )

    with pytest.raises(ValidationError):
        TurnInterpretation(intents=["request_refund"])


@pytest.mark.parametrize("suggested_id", ["", "   "])
def test_suggested_identifier_must_not_be_blank(suggested_id):
    with pytest.raises(ValidationError, match="no puede estar vacío"):
        InterpretedChange(
            field=AppointmentField.PROFESSIONAL,
            operation=ChangeOperation.SET,
            raw_text="Lau",
            suggested_id=suggested_id,
        )


def test_ambiguity_preserves_affected_field_and_original_description():
    description = "Dijo «a las cuatro», sin indicar a. m. o p. m."
    ambiguity = InterpretedAmbiguity(
        field=AppointmentField.TIME,
        description=description,
    )
    interpretation = TurnInterpretation(ambiguities=[ambiguity])

    assert interpretation.ambiguities[0].field is AppointmentField.TIME
    assert interpretation.ambiguities[0].description == description


@pytest.mark.parametrize("description", ["", "   "])
def test_ambiguity_description_must_not_be_blank(description):
    with pytest.raises(ValidationError, match="no puede estar vacía"):
        InterpretedAmbiguity(
            field=AppointmentField.DATE,
            description=description,
        )


def test_plain_text_is_not_a_structured_ambiguity():
    with pytest.raises(ValidationError):
        TurnInterpretation(ambiguities=["puede referirse a dos fechas"])


@pytest.mark.parametrize(
    ("raw_text", "raw_values", "suggested_id"),
    [
        ("mañana", [], None),
        (None, [], "laura"),
        ("", [], None),
        (None, ["manicure"], None),
    ],
)
def test_clear_rejects_raw_text_and_suggested_identifier(
    raw_text, raw_values, suggested_id
):
    with pytest.raises(ValidationError, match="CLEAR no admite"):
        InterpretedChange(
            field=AppointmentField.SERVICES,
            operation=ChangeOperation.CLEAR,
            raw_text=raw_text,
            raw_values=raw_values,
            suggested_id=suggested_id,
        )


def test_list_defaults_are_independent():
    first = TurnInterpretation()
    second = TurnInterpretation()

    first.intents.append(TurnIntent.CANCEL_APPOINTMENT)

    assert second.intents == []
