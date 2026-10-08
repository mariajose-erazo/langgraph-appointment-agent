from datetime import datetime, timedelta, timezone

import pytest

from cne_agent.appointments.merge import merge_appointment_request
from cne_agent.appointments.request import (
    AppointmentRequest,
    AppointmentRequestPatch,
    Clear,
    DateStatus,
    ProfessionalStatus,
    RemovalPreference,
    RemovalRole,
    RemovalStatus,
    ServiceFamily,
    ServiceMention,
    SetServiceOperation,
    TimePeriod,
    TimeStatus,
)
from cne_agent.interpretation.models import (
    AppointmentField,
    ChangeOperation,
    InterpretedAmbiguity,
    InterpretedChange,
    TurnInterpretation,
)
from cne_agent.interpretation.normalizer import (
    NormalizationIssueCode,
    NormalizationNoticeCode,
    NormalizationResult,
    NormalizationStatus,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
    normalize_turn_interpretation,
)


BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
REFERENCE = datetime(2026, 10, 4, 10, 30, tzinfo=BOGOTA)


@pytest.fixture
def service_catalog():
    return (
        ServiceCatalogEntry(
            "manicure",
            ServiceFamily.MANICURE,
            None,
            ("manicure", "mani"),
        ),
        ServiceCatalogEntry(
            "pedicure",
            ServiceFamily.PEDICURE,
            None,
            ("pedicure", "pedi"),
        ),
        ServiceCatalogEntry(
            "manicure-semi",
            ServiceFamily.MANICURE,
            "semipermanente",
            ("manicure semipermanente",),
        ),
    )


@pytest.fixture
def professional_catalog():
    return (
        ProfessionalCatalogEntry("laura", "Laura", ("Lau",)),
        ProfessionalCatalogEntry("valentina", "Valentina", ("Vale",)),
    )


def normalize(
    *changes,
    current=None,
    services=None,
    professionals=None,
    ambiguities=(),
    reference_at=REFERENCE,
):
    if services is None:
        services = (
            ServiceCatalogEntry(
                "manicure",
                ServiceFamily.MANICURE,
                None,
                ("manicure", "mani"),
            ),
            ServiceCatalogEntry(
                "pedicure",
                ServiceFamily.PEDICURE,
                None,
                ("pedicure", "pedi"),
            ),
            ServiceCatalogEntry(
                "manicure-semi",
                ServiceFamily.MANICURE,
                "semipermanente",
                ("manicure semipermanente",),
            ),
        )
    if professionals is None:
        professionals = (
            ProfessionalCatalogEntry("laura", "Laura", ("Lau",)),
            ProfessionalCatalogEntry("valentina", "Valentina", ("Vale",)),
        )
    interpretation = TurnInterpretation(
        appointment_changes=list(changes),
        ambiguities=list(ambiguities),
    )
    return normalize_turn_interpretation(
        interpretation,
        current_request=current or AppointmentRequest(),
        service_catalog=services,
        professional_catalog=professionals,
        reference_at=reference_at,
    )


def change(field, operation, raw_text=None, **values):
    return InterpretedChange(
        field=field,
        operation=operation,
        raw_text=raw_text,
        **values,
    )


def assert_blocked(result, status, code):
    assert result.status is status
    assert result.patch is None
    assert code in {issue.code for issue in result.issues}


def test_empty_interpretation_produces_an_empty_valid_patch():
    result = normalize()

    assert result.status is NormalizationStatus.SUCCESS
    assert result.patch is not None
    assert result.issues == ()


def test_set_resolves_multiple_services_without_splitting_raw_text():
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.SET,
            "manicure y pedicure",
            raw_values=["manicure", "pedicure"],
        )
    )

    assert result.status is NormalizationStatus.SUCCESS
    operation = result.patch.service_operations[0]
    assert isinstance(operation, SetServiceOperation)
    assert tuple(item.raw_text for item in operation.mentions) == (
        "manicure",
        "pedicure",
    )


def test_service_matching_ignores_case_spaces_and_accents(service_catalog):
    accented = ServiceCatalogEntry(
        "semi",
        ServiceFamily.MANICURE,
        "semipermanente",
        ("Manicúre   Semipermanente",),
    )
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.SET,
            "MANICURE semipermanente",
        ),
        services=(accented,),
    )

    mention = result.patch.service_operations[0].mentions[0]
    assert mention.raw_text == "MANICURE semipermanente"
    assert mention.variant_text == "semipermanente"


def test_simple_service_change_remains_compatible_without_raw_values():
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.ADD,
            "También quiero pedicure",
        )
    )

    assert result.status is NormalizationStatus.SUCCESS
    assert result.patch.service_operations[0].mention.raw_text == (
        "También quiero pedicure"
    )


@pytest.mark.parametrize(
    ("raw_text", "raw_values"),
    [
        ("manicure", ["pedicure"]),
        ("manicure y pedicure", ["manicure"]),
    ],
)
def test_incoherent_service_values_require_clarification(
    raw_text, raw_values
):
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.SET,
            raw_text,
            raw_values=raw_values,
        )
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.INCOHERENT_SERVICE_VALUES,
    )


def test_unknown_service_does_not_create_a_patch():
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.ADD,
            "uñas acrílicas",
        )
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.UNKNOWN_SERVICE,
    )
    assert result.issues[0].source_change_index == 0


@pytest.mark.parametrize(
    "catalog",
    [
        (
            ServiceCatalogEntry(
                "same", ServiceFamily.MANICURE, None, ("manicure",)
            ),
            ServiceCatalogEntry(
                "same", ServiceFamily.PEDICURE, None, ("pedicure",)
            ),
        ),
        (
            ServiceCatalogEntry(
                "one", ServiceFamily.MANICURE, None, ("servicio",)
            ),
            ServiceCatalogEntry(
                "two", ServiceFamily.PEDICURE, None, ("servicio",)
            ),
        ),
        (
            ServiceCatalogEntry(
                "one", ServiceFamily.UNRESOLVED, None, ("servicio",)
            ),
        ),
        (
            ServiceCatalogEntry(
                "one", ServiceFamily.MANICURE, None, ("uno",)
            ),
            ServiceCatalogEntry(
                "two", ServiceFamily.MANICURE, None, ("dos",)
            ),
        ),
    ],
)
def test_invalid_service_catalog_is_a_configuration_error(catalog):
    result = normalize(services=catalog)

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.INVALID_SERVICE_CATALOG,
    )


@pytest.mark.parametrize(
    "catalog",
    [
        (
            ProfessionalCatalogEntry("same", "Laura"),
            ProfessionalCatalogEntry("same", "Valentina"),
        ),
        (
            ProfessionalCatalogEntry("laura", "Laura", ("Lau",)),
            ProfessionalCatalogEntry("laura-2", "Laura Sofía", ("Lau",)),
        ),
        (ProfessionalCatalogEntry("", "Laura"),),
        (ProfessionalCatalogEntry("laura", " "),),
    ],
)
def test_invalid_professional_catalog_is_a_configuration_error(catalog):
    result = normalize(professionals=catalog)

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.INVALID_PROFESSIONAL_CATALOG,
    )


def test_specific_professional_uses_exactly_one_verified_catalog_entry():
    result = normalize(
        change(
            AppointmentField.PROFESSIONAL,
            ChangeOperation.SET,
            "Con Lau",
            suggested_id="laura",
        )
    )

    assert result.status is NormalizationStatus.SUCCESS
    professional = result.patch.professional
    assert professional.status.value is ProfessionalStatus.PREFERRED
    assert len(professional.ranked_operations[0].mentions) == 1
    assert professional.ranked_operations[0].mentions[0].canonical_id == "laura"
    assert result.notices == ()


def test_contradictory_suggested_id_is_discarded_not_trusted():
    result = normalize(
        change(
            AppointmentField.PROFESSIONAL,
            ChangeOperation.SET,
            "Laura",
            suggested_id="valentina",
        )
    )

    mention = result.patch.professional.ranked_operations[0].mentions[0]
    assert mention.canonical_id == "laura"
    assert result.notices[0].code is (
        NormalizationNoticeCode.DISCARDED_SUGGESTED_ID
    )
    assert result.notices[0].discarded_suggested_id == "valentina"


def test_suggested_id_cannot_resolve_unknown_professional():
    result = normalize(
        change(
            AppointmentField.PROFESSIONAL,
            ChangeOperation.SET,
            "Lina",
            suggested_id="laura",
        )
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.UNKNOWN_PROFESSIONAL,
    )


def test_any_professional_uses_no_ranking_and_discards_suggestion():
    result = normalize(
        change(
            AppointmentField.PROFESSIONAL,
            ChangeOperation.SET,
            "Puede ser cualquiera",
            suggested_id="laura",
        )
    )

    assert result.patch.professional.status.value is ProfessionalStatus.ANY
    assert isinstance(result.patch.professional.ranked_operations[0], Clear)
    assert result.notices[0].discarded_suggested_id == "laura"


def test_clear_professional_resets_selection_without_ordered_preferences():
    result = normalize(
        change(
            AppointmentField.PROFESSIONAL,
            ChangeOperation.CLEAR,
        )
    )

    assert result.patch.professional.status.value is (
        ProfessionalStatus.UNSPECIFIED
    )
    assert isinstance(result.patch.professional.ranked_operations[0], Clear)


def test_tomorrow_uses_explicit_bogota_reference():
    reference = datetime(2026, 12, 31, 23, 30, tzinfo=BOGOTA)
    result = normalize(
        change(AppointmentField.DATE, ChangeOperation.SET, "mañana"),
        reference_at=reference,
    )

    preference = result.patch.date.value
    assert preference.status is DateStatus.EXACT
    assert preference.resolved_date.isoformat() == "2027-01-01"
    assert preference.expression == "mañana"


def test_day_after_tomorrow_is_not_confused_with_tomorrow():
    result = normalize(
        change(
            AppointmentField.DATE,
            ChangeOperation.SET,
            "pasado mañana",
        )
    )

    assert result.patch.date.value.resolved_date.isoformat() == "2026-10-06"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2026-10-15", "2026-10-15"),
        ("el 15 de octubre de 2026", "2026-10-15"),
    ],
)
def test_explicit_dates_are_resolved(expression, expected):
    result = normalize(
        change(AppointmentField.DATE, ChangeOperation.SET, expression)
    )

    assert result.patch.date.value.resolved_date.isoformat() == expected


@pytest.mark.parametrize(
    "expression", ["el 15 de octubre", "el próximo viernes"]
)
def test_ambiguous_dates_require_clarification(expression):
    result = normalize(
        change(AppointmentField.DATE, ChangeOperation.SET, expression)
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.AMBIGUOUS_DATE,
    )


def test_naive_reference_time_is_a_configuration_error():
    result = normalize(reference_at=datetime(2026, 10, 4, 10, 30))

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.INVALID_REFERENCE_TIME,
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("a las 15:00", "15:00:00"),
        ("a las 3 de la tarde", "15:00:00"),
        ("a las 3:30 de la tarde", "15:30:00"),
        ("3:30 p. m.", "15:30:00"),
    ],
)
def test_exact_times_are_resolved(expression, expected):
    result = normalize(
        change(AppointmentField.TIME, ChangeOperation.SET, expression)
    )

    preference = result.patch.time.value
    assert preference.status is TimeStatus.EXACT
    assert preference.resolved_time.isoformat() == expected
    assert preference.expression == expression


def test_period_is_preserved_without_inventing_an_exact_time():
    result = normalize(
        change(AppointmentField.TIME, ChangeOperation.SET, "por la tarde")
    )

    preference = result.patch.time.value
    assert preference.status is TimeStatus.PERIOD
    assert preference.period is TimePeriod.AFTERNOON
    assert preference.resolved_time is None


def test_unqualified_hour_is_ambiguous():
    result = normalize(
        change(AppointmentField.TIME, ChangeOperation.SET, "a las 3")
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.AMBIGUOUS_TIME,
    )


@pytest.mark.parametrize("expression", ["entre 3 y 5", "temprano"])
def test_unsupported_time_expression_is_not_interpreted(expression):
    result = normalize(
        change(AppointmentField.TIME, ChangeOperation.SET, expression)
    )

    assert result.patch is None
    assert result.status is NormalizationStatus.NEEDS_CLARIFICATION


def test_longer_service_alias_wins_over_contained_generic_alias():
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.ADD,
            "quiero manicure semipermanente",
        )
    )

    mention = result.patch.service_operations[0].mention
    assert mention.family is ServiceFamily.MANICURE
    assert mention.variant_text == "semipermanente"
    assert mention.canonical_id == "manicure-semi"


def test_removal_addon_is_valid_when_a_service_is_added():
    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.ADD,
            "manicure",
        ),
        change(
            AppointmentField.REMOVAL,
            ChangeOperation.SET,
            "también necesito retiro",
        ),
    )

    assert result.patch.removal.value.role is RemovalRole.ADDON


def test_no_removal_is_not_treated_as_clear():
    result = normalize(
        change(
            AppointmentField.REMOVAL,
            ChangeOperation.SET,
            "ya no necesito retiro",
        )
    )

    assert result.patch.removal.value.status is RemovalStatus.NOT_REQUIRED


def test_only_removal_synthesizes_service_clear():
    original_service = ServiceMention(
        "manicure",
        ServiceFamily.MANICURE,
    )
    current = AppointmentRequest(
        services=(original_service,)
    )
    original_services = current.services
    result = normalize(
        change(
            AppointmentField.REMOVAL,
            ChangeOperation.SET,
            "solo quiero retiro",
        ),
        current=current,
    )

    assert result.status is NormalizationStatus.SUCCESS
    assert isinstance(result.patch.service_operations[0], Clear)
    assert result.patch.removal.value.role is RemovalRole.ONLY
    merged = merge_appointment_request(current, result.patch)
    assert merged.services == ()
    assert merged.removal.role is RemovalRole.ONLY
    assert current.services is original_services
    assert current.services == (original_service,)


def test_only_removal_rejects_service_addition_without_partial_patch():
    original_service = ServiceMention(
        "pedicure",
        ServiceFamily.PEDICURE,
    )
    current = AppointmentRequest(services=(original_service,))
    original_services = current.services

    result = normalize(
        change(
            AppointmentField.SERVICES,
            ChangeOperation.ADD,
            "manicure",
        ),
        change(
            AppointmentField.REMOVAL,
            ChangeOperation.SET,
            "solo quiero retiro",
        ),
        current=current,
    )

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.CONFLICTING_CHANGES,
    )
    assert result.patch is None
    assert current.services is original_services
    assert current.services == (original_service,)


def test_clear_removal_has_field_specific_clear_semantics():
    result = normalize(
        change(AppointmentField.REMOVAL, ChangeOperation.CLEAR)
    )

    assert isinstance(result.patch.removal, Clear)


def test_contradictory_changes_are_invalid_and_have_no_patch():
    result = normalize(
        change(AppointmentField.TIME, ChangeOperation.SET, "15:00"),
        change(AppointmentField.TIME, ChangeOperation.CLEAR),
    )

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.CONFLICTING_CHANGES,
    )


def test_add_and_remove_same_service_are_invalid():
    result = normalize(
        change(AppointmentField.SERVICES, ChangeOperation.ADD, "manicure"),
        change(AppointmentField.SERVICES, ChangeOperation.REMOVE, "manicure"),
    )

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.CONFLICTING_CHANGES,
    )


def test_existing_interpretation_ambiguity_blocks_the_whole_patch():
    result = normalize(
        change(AppointmentField.SERVICES, ChangeOperation.ADD, "manicure"),
        ambiguities=(
            InterpretedAmbiguity(
                field=AppointmentField.DATE,
                description="viernes puede referirse a dos fechas",
            ),
        ),
    )

    assert_blocked(
        result,
        NormalizationStatus.NEEDS_CLARIFICATION,
        NormalizationIssueCode.INPUT_AMBIGUITY,
    )


def test_dry_run_rejects_patch_incompatible_with_current_request():
    current = AppointmentRequest(
        removal=RemovalPreference(
            RemovalStatus.REQUIRED,
            RemovalRole.ONLY,
        )
    )
    result = normalize(
        change(AppointmentField.SERVICES, ChangeOperation.ADD, "manicure"),
        current=current,
    )

    assert_blocked(
        result,
        NormalizationStatus.INVALID,
        NormalizationIssueCode.INCOMPATIBLE_WITH_CURRENT_REQUEST,
    )
    assert result.issues[0].field is None


def test_blocked_result_does_not_mutate_current_request():
    service = ServiceMention("manicure", ServiceFamily.MANICURE)
    current = AppointmentRequest(services=(service,))
    original_services = current.services
    result = normalize(
        change(AppointmentField.DATE, ChangeOperation.SET, "el viernes"),
        current=current,
    )

    assert result.patch is None
    assert current.services is original_services
    assert current.services == (service,)


def test_successful_dry_run_does_not_mutate_current_request():
    current = AppointmentRequest()
    result = normalize(
        change(AppointmentField.SERVICES, ChangeOperation.ADD, "manicure"),
        current=current,
    )

    merged = merge_appointment_request(current, result.patch)
    assert current.services == ()
    assert len(merged.services) == 1


def test_normalization_result_enforces_all_or_nothing_invariants():
    with pytest.raises(ValueError, match="SUCCESS exige patch"):
        NormalizationResult(NormalizationStatus.SUCCESS, None)

    with pytest.raises(ValueError, match="resultado bloqueante"):
        NormalizationResult(
            NormalizationStatus.NEEDS_CLARIFICATION,
            AppointmentRequestPatch(),
        )
