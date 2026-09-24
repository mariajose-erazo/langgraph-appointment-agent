from datetime import date, datetime, time

import pytest

from cne_agent.appointments.request import (
    AddRankOperation,
    AddServiceOperation,
    AppointmentRequest,
    AppointmentRequestPatch,
    Clear,
    DatePreference,
    DateStatus,
    Omitted,
    ProfessionalFallback,
    ProfessionalMention,
    ProfessionalPreference,
    ProfessionalPreferencePatch,
    ProfessionalResolution,
    ProfessionalSelector,
    ProfessionalStatus,
    RemovalPreference,
    RemovalRole,
    RemovalStatus,
    RemoveRankOperation,
    RemoveServiceOperation,
    SchedulePreference,
    ServiceFamily,
    ServiceMention,
    ServiceSelector,
    SetRankOperation,
    SetServiceOperation,
    SetValue,
    TimePeriod,
    TimePreference,
    TimeStatus,
)


def manicure(variant: str | None = None, raw_text: str = "manicure") -> ServiceMention:
    return ServiceMention(raw_text, ServiceFamily.MANICURE, variant)


def pedicure(variant: str | None = None, raw_text: str = "pedicure") -> ServiceMention:
    return ServiceMention(raw_text, ServiceFamily.PEDICURE, variant)


def resolved(raw_text: str, canonical_id: str) -> ProfessionalMention:
    return ProfessionalMention(
        raw_text,
        canonical_id,
        ProfessionalResolution.RESOLVED,
    )


def unresolved(raw_text: str) -> ProfessionalMention:
    return ProfessionalMention(
        raw_text,
        None,
        ProfessionalResolution.UNRESOLVED,
    )


def preferred(*mentions: ProfessionalMention) -> ProfessionalPreference:
    return ProfessionalPreference(
        ProfessionalStatus.PREFERRED,
        mentions,
        ProfessionalFallback.NONE,
    )


def removal(status: RemovalStatus, role: RemovalRole = RemovalRole.UNSPECIFIED):
    return RemovalPreference(status, role)


def test_empty_appointment_request_uses_initial_states():
    request = AppointmentRequest()

    assert request.services == ()
    assert request.professional.status is ProfessionalStatus.UNSPECIFIED
    assert request.professional.ranked == ()
    assert request.professional.fallback is ProfessionalFallback.NONE
    assert request.schedule.date.status is DateStatus.UNSPECIFIED
    assert request.schedule.time.status is TimeStatus.UNSPECIFIED
    assert request.removal.status is RemovalStatus.UNSPECIFIED
    assert request.removal.role is RemovalRole.UNSPECIFIED


def test_service_mention_accepts_family_with_or_without_variant():
    assert manicure().variant_text is None
    assert manicure("semipermanente").variant_text == "semipermanente"
    assert ServiceMention(
        "acrílicas",
        ServiceFamily.UNRESOLVED,
    ).variant_text is None


@pytest.mark.parametrize(
    "mention",
    [
        lambda: ServiceMention("  ", ServiceFamily.MANICURE),
        lambda: ServiceMention("manicure", ServiceFamily.MANICURE, "  "),
        lambda: ServiceMention("acrílicas", ServiceFamily.UNRESOLVED, "largas"),
        lambda: ServiceMention("manicure", "manicure"),
    ],
)
def test_service_mention_rejects_invalid_values(mention):
    with pytest.raises((ValueError, TypeError)):
        mention()


def test_appointment_rejects_duplicate_service_identities():
    with pytest.raises(ValueError, match="servicios duplicados"):
        AppointmentRequest(services=(manicure(raw_text="mani"), manicure()))

    with pytest.raises(ValueError, match="servicios duplicados"):
        AppointmentRequest(
            services=(
                ServiceMention("acrílicas", ServiceFamily.UNRESOLVED),
                ServiceMention("acrílicas", ServiceFamily.UNRESOLVED),
            )
        )


def test_appointment_allows_distinct_service_identities():
    request = AppointmentRequest(
        services=(
            manicure("semipermanente"),
            manicure(),
            pedicure(),
            ServiceMention("acrílicas", ServiceFamily.UNRESOLVED),
            ServiceMention("polygel", ServiceFamily.UNRESOLVED),
        )
    )

    assert len(request.services) == 5


def test_professional_mention_keeps_resolution_and_canonical_id_apart():
    assert resolved("Laura", "laura").canonical_id == "laura"
    assert unresolved("Carolina").canonical_id is None

    with pytest.raises(ValueError, match="obligatorio"):
        ProfessionalMention("Laura", None, ProfessionalResolution.RESOLVED)

    with pytest.raises(ValueError, match="vacío"):
        ProfessionalMention("Carolina", "carolina", ProfessionalResolution.UNRESOLVED)

    with pytest.raises(ValueError):
        ProfessionalMention("Laura", "   ", ProfessionalResolution.RESOLVED)


def test_professional_preference_accepts_unspecified_any_and_preferred():
    assert ProfessionalPreference().ranked == ()
    assert ProfessionalPreference(ProfessionalStatus.ANY).fallback is (
        ProfessionalFallback.NONE
    )
    preference = ProfessionalPreference(
        ProfessionalStatus.PREFERRED,
        (resolved("Laura", "laura"), unresolved("Valentina")),
        ProfessionalFallback.ANY,
    )

    assert preference.ranked[0].canonical_id == "laura"
    assert preference.fallback is ProfessionalFallback.ANY


@pytest.mark.parametrize(
    "preference",
    [
        lambda: ProfessionalPreference(
            ProfessionalStatus.UNSPECIFIED,
            (resolved("Laura", "laura"),),
        ),
        lambda: ProfessionalPreference(
            ProfessionalStatus.ANY,
            fallback=ProfessionalFallback.ANY,
        ),
        lambda: ProfessionalPreference(ProfessionalStatus.PREFERRED),
        lambda: ProfessionalPreference(
            ProfessionalStatus.PREFERRED,
            (resolved("Laura", "laura"), resolved("Lau", "laura")),
        ),
        lambda: ProfessionalPreference(
            ProfessionalStatus.PREFERRED,
            (unresolved("Valentina"), unresolved("Valentina")),
        ),
    ],
)
def test_professional_preference_rejects_invalid_states(preference):
    with pytest.raises(ValueError):
        preference()


def test_same_words_are_not_duplicates_when_resolution_differs():
    preference = preferred(
        resolved("Laura", "laura"),
        unresolved("Laura"),
    )

    assert len(preference.ranked) == 2


def test_date_preference_accepts_each_real_status():
    assert DatePreference().expression is None
    assert DatePreference(
        DateStatus.UNKNOWN,
        expression="no sé qué día",
    ).resolved_date is None
    exact = DatePreference(
        DateStatus.EXACT,
        expression="mañana",
        resolved_date=date(2026, 9, 23),
    )
    ambiguous = DatePreference(
        DateStatus.AMBIGUOUS,
        alternatives=(date(2026, 9, 25), date(2026, 9, 26)),
    )

    assert exact.resolved_date == date(2026, 9, 23)
    assert len(ambiguous.alternatives) == 2


@pytest.mark.parametrize(
    "preference",
    [
        lambda: DatePreference(DateStatus.UNSPECIFIED, expression="mañana"),
        lambda: DatePreference(DateStatus.EXACT),
        lambda: DatePreference(
            DateStatus.EXACT,
            resolved_date=date(2026, 9, 23),
            alternatives=(date(2026, 9, 24), date(2026, 9, 25)),
        ),
        lambda: DatePreference(DateStatus.UNKNOWN, resolved_date=date(2026, 9, 23)),
        lambda: DatePreference(
            DateStatus.AMBIGUOUS,
            alternatives=(date(2026, 9, 25),),
        ),
        lambda: DatePreference(
            DateStatus.AMBIGUOUS,
            alternatives=(date(2026, 9, 25), date(2026, 9, 25)),
        ),
        lambda: DatePreference(
            DateStatus.AMBIGUOUS,
            resolved_date=date(2026, 9, 25),
            alternatives=(date(2026, 9, 25), date(2026, 9, 26)),
        ),
        lambda: DatePreference(DateStatus.EXACT, resolved_date=datetime(2026, 9, 23)),
    ],
)
def test_date_preference_rejects_invalid_states(preference):
    with pytest.raises((ValueError, TypeError)):
        preference()


def test_time_preference_accepts_each_real_status():
    assert TimePreference().resolved_time is None
    assert TimePreference(TimeStatus.UNKNOWN, expression="no sé").period is None
    exact = TimePreference(
        TimeStatus.EXACT,
        expression="a las 4",
        resolved_time=time(16, 0),
    )
    period = TimePreference(TimeStatus.PERIOD, period=TimePeriod.AFTERNOON)

    assert exact.resolved_time == time(16, 0)
    assert exact.period is None
    assert period.period is TimePeriod.AFTERNOON
    assert period.resolved_time is None


@pytest.mark.parametrize(
    "preference",
    [
        lambda: TimePreference(TimeStatus.UNSPECIFIED, expression="a las 3"),
        lambda: TimePreference(TimeStatus.EXACT),
        lambda: TimePreference(
            TimeStatus.EXACT,
            resolved_time=time(15, 0),
            period=TimePeriod.AFTERNOON,
        ),
        lambda: TimePreference(TimeStatus.PERIOD),
        lambda: TimePreference(
            TimeStatus.PERIOD,
            resolved_time=time(15, 0),
            period=TimePeriod.AFTERNOON,
        ),
        lambda: TimePreference(TimeStatus.UNKNOWN, period=TimePeriod.MORNING),
    ],
)
def test_time_preference_rejects_invalid_states(preference):
    with pytest.raises((ValueError, TypeError)):
        preference()


def test_removal_preference_restricts_addon_and_only_to_required():
    assert removal(RemovalStatus.REQUIRED, RemovalRole.ADDON).role is RemovalRole.ADDON
    assert removal(RemovalStatus.REQUIRED, RemovalRole.ONLY).role is RemovalRole.ONLY
    assert removal(RemovalStatus.REQUIRED).role is RemovalRole.UNSPECIFIED
    assert removal(RemovalStatus.NOT_REQUIRED).role is RemovalRole.UNSPECIFIED

    with pytest.raises(ValueError, match="addon y only"):
        removal(RemovalStatus.NOT_REQUIRED, RemovalRole.ADDON)

    with pytest.raises(ValueError, match="addon y only"):
        removal(RemovalStatus.UNKNOWN, RemovalRole.ONLY)


def test_appointment_request_enforces_removal_and_service_combinations():
    addon = removal(RemovalStatus.REQUIRED, RemovalRole.ADDON)
    only = removal(RemovalStatus.REQUIRED, RemovalRole.ONLY)

    assert AppointmentRequest(services=(manicure(),), removal=addon).services
    assert AppointmentRequest(removal=only).services == ()
    assert AppointmentRequest(services=(manicure(),)).removal.role is (
        RemovalRole.UNSPECIFIED
    )
    assert AppointmentRequest().removal.role is RemovalRole.UNSPECIFIED

    with pytest.raises(ValueError, match="only"):
        AppointmentRequest(services=(manicure(),), removal=only)

    with pytest.raises(ValueError, match="addon"):
        AppointmentRequest(removal=addon)


def test_omitted_set_value_and_clear_are_distinct():
    assert Omitted() == Omitted()
    assert Clear() == Clear()
    assert Omitted() != Clear()
    assert SetValue(time(16, 0)) == SetValue(time(16, 0))
    assert SetValue(time(16, 0)) != SetValue(time(15, 0))

    with pytest.raises(ValueError, match="None"):
        SetValue(None)


def test_service_selector_uses_one_identity():
    classified = ServiceSelector(ServiceFamily.MANICURE, None)
    semipermanent = ServiceSelector(ServiceFamily.MANICURE, "semipermanente")
    unresolved_service = ServiceSelector(raw_text="acrílicas")

    assert classified.family is ServiceFamily.MANICURE
    assert classified.variant_text is None
    assert classified.raw_text is None
    assert semipermanent.variant_text == "semipermanente"
    assert unresolved_service.raw_text == "acrílicas"
    assert unresolved_service.family is None

    with pytest.raises(ValueError, match="mezclar"):
        ServiceSelector(ServiceFamily.MANICURE, raw_text="mani")

    with pytest.raises(ValueError, match="unresolved"):
        ServiceSelector(ServiceFamily.UNRESOLVED, raw_text="acrílicas")

    with pytest.raises(ValueError, match="identidad"):
        ServiceSelector()


def test_professional_selector_uses_one_identity():
    by_id = ProfessionalSelector(canonical_id="laura")
    by_text = ProfessionalSelector(raw_text="Carolina")

    assert by_id.canonical_id == "laura"
    assert by_id.raw_text is None
    assert by_text.raw_text == "Carolina"
    assert by_text.canonical_id is None

    with pytest.raises(ValueError, match="una sola identidad"):
        ProfessionalSelector(canonical_id="laura", raw_text="Laura")

    with pytest.raises(ValueError, match="una sola identidad"):
        ProfessionalSelector()


def test_service_operations_accept_empty_replacement_and_incremental_changes():
    assert AppointmentRequestPatch().service_operations == ()
    replacement = AppointmentRequestPatch(
        service_operations=(SetServiceOperation((manicure(), pedicure())),)
    )
    cleared = AppointmentRequestPatch(service_operations=(Clear(),))
    incremental = AppointmentRequestPatch(
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE, None)),
            AddServiceOperation(manicure()),
        )
    )

    assert isinstance(replacement.service_operations[0], SetServiceOperation)
    assert isinstance(cleared.service_operations[0], Clear)
    assert [type(operation) for operation in incremental.service_operations] == [
        RemoveServiceOperation,
        AddServiceOperation,
    ]


@pytest.mark.parametrize(
    "operations",
    [
        lambda: (Clear(), AddServiceOperation(manicure())),
        lambda: (
            SetServiceOperation((manicure(),)),
            AddServiceOperation(pedicure()),
        ),
        lambda: (SetServiceOperation((manicure(),)), Clear()),
        lambda: (Clear(), Clear()),
        lambda: (AddServiceOperation(manicure()), AddServiceOperation(manicure())),
    ],
)
def test_service_operations_reject_invalid_combinations(operations):
    with pytest.raises(ValueError):
        AppointmentRequestPatch(service_operations=operations())


def test_service_set_rejects_empty_and_duplicate_payloads():
    with pytest.raises(ValueError, match="al menos un servicio"):
        SetServiceOperation(())

    with pytest.raises(ValueError, match="duplicados"):
        SetServiceOperation((manicure("semi", "manicure"), manicure("semi", "mani")))


def test_ranked_operations_follow_the_service_rules():
    laura = resolved("Laura", "laura")
    valentina = resolved("Valentina", "valentina")
    patch = ProfessionalPreferencePatch(
        ranked_operations=(
            RemoveRankOperation(ProfessionalSelector(canonical_id="laura")),
            AddRankOperation(valentina),
        )
    )
    replacement = ProfessionalPreferencePatch(
        ranked_operations=(SetRankOperation((valentina,)),)
    )

    assert len(patch.ranked_operations) == 2
    assert isinstance(replacement.ranked_operations[0], SetRankOperation)

    with pytest.raises(ValueError, match="única operación"):
        ProfessionalPreferencePatch(
            ranked_operations=(Clear(), AddRankOperation(valentina))
        )

    with pytest.raises(ValueError, match="repite"):
        ProfessionalPreferencePatch(
            ranked_operations=(AddRankOperation(laura), AddRankOperation(laura))
        )

    with pytest.raises(ValueError, match="al menos una profesional"):
        SetRankOperation(())


def test_professional_patch_resets_any_and_unspecified_explicitly():
    for status in (ProfessionalStatus.ANY, ProfessionalStatus.UNSPECIFIED):
        patch = ProfessionalPreferencePatch(
            status=SetValue(status),
            ranked_operations=(Clear(),),
            fallback=SetValue(ProfessionalFallback.NONE),
        )
        assert patch.status == SetValue(status)

    with pytest.raises(ValueError, match="ranked_operations"):
        ProfessionalPreferencePatch(
            status=SetValue(ProfessionalStatus.ANY),
            fallback=SetValue(ProfessionalFallback.NONE),
        )

    with pytest.raises(ValueError, match="fallback"):
        ProfessionalPreferencePatch(
            status=SetValue(ProfessionalStatus.UNSPECIFIED),
            ranked_operations=(Clear(),),
        )


def test_professional_patch_preferred_requires_a_single_set():
    patch = ProfessionalPreferencePatch(
        status=SetValue(ProfessionalStatus.PREFERRED),
        ranked_operations=(SetRankOperation((resolved("Laura", "laura"),)),),
        fallback=SetValue(ProfessionalFallback.ANY),
    )

    assert patch.fallback == SetValue(ProfessionalFallback.ANY)

    with pytest.raises(ValueError, match="preferred"):
        ProfessionalPreferencePatch(
            status=SetValue(ProfessionalStatus.PREFERRED),
            ranked_operations=(
                AddRankOperation(resolved("Laura", "laura")),
            ),
        )


def test_professional_patch_rejects_clear_on_status_and_fallback():
    with pytest.raises(TypeError):
        ProfessionalPreferencePatch(status=Clear())

    with pytest.raises(TypeError):
        ProfessionalPreferencePatch(fallback=Clear())


def test_empty_patch_is_valid_and_changes_nothing_by_itself():
    patch = AppointmentRequestPatch()

    assert patch == AppointmentRequestPatch(
        service_operations=(),
        professional=ProfessionalPreferencePatch(),
        date=Omitted(),
        time=Omitted(),
        removal=Omitted(),
    )
    assert patch.professional.ranked_operations == ()
    assert isinstance(patch.professional.status, Omitted)
    assert isinstance(patch.professional.fallback, Omitted)


def test_clear_is_the_only_reset_for_date_time_and_removal():
    patch = AppointmentRequestPatch(
        date=Clear(),
        time=Clear(),
        removal=Clear(),
    )

    assert isinstance(patch.date, Clear)
    assert isinstance(patch.time, Clear)
    assert isinstance(patch.removal, Clear)

    with pytest.raises(ValueError, match="unspecified"):
        AppointmentRequestPatch(date=SetValue(DatePreference()))

    with pytest.raises(ValueError, match="unspecified"):
        AppointmentRequestPatch(time=SetValue(TimePreference()))

    with pytest.raises(ValueError, match="unspecified"):
        AppointmentRequestPatch(removal=SetValue(RemovalPreference()))


def test_patch_accepts_real_date_time_and_removal_values():
    patch = AppointmentRequestPatch(
        date=SetValue(
            DatePreference(DateStatus.EXACT, resolved_date=date(2026, 9, 23))
        ),
        time=SetValue(TimePreference(TimeStatus.EXACT, resolved_time=time(16, 0))),
        removal=SetValue(removal(RemovalStatus.NOT_REQUIRED)),
    )

    assert patch.date.value.resolved_date == date(2026, 9, 23)
    assert patch.time.value.resolved_time == time(16, 0)
    assert patch.removal.value.status is RemovalStatus.NOT_REQUIRED


def test_removal_only_patch_requires_clear_and_addon_rejects_it():
    only = removal(RemovalStatus.REQUIRED, RemovalRole.ONLY)
    addon = removal(RemovalStatus.REQUIRED, RemovalRole.ADDON)

    only_patch = AppointmentRequestPatch(
        service_operations=(Clear(),),
        removal=SetValue(only),
    )
    addon_without_known_services = AppointmentRequestPatch(removal=SetValue(addon))
    addon_with_replacement = AppointmentRequestPatch(
        service_operations=(SetServiceOperation((manicure(),)),),
        removal=SetValue(addon),
    )

    assert isinstance(only_patch.service_operations[0], Clear)
    assert isinstance(addon_without_known_services.removal, SetValue)
    assert isinstance(addon_with_replacement.service_operations[0], SetServiceOperation)

    with pytest.raises(ValueError, match="only"):
        AppointmentRequestPatch(removal=SetValue(only))

    with pytest.raises(ValueError, match="addon"):
        AppointmentRequestPatch(
            service_operations=(Clear(),),
            removal=SetValue(addon),
        )


def test_patch_rejects_none_as_a_block_change():
    with pytest.raises(TypeError):
        AppointmentRequestPatch(date=None)


def test_schedule_groups_the_current_date_and_time():
    schedule = SchedulePreference(
        date=DatePreference(DateStatus.UNKNOWN),
        time=TimePreference(TimeStatus.PERIOD, period=TimePeriod.EVENING),
    )
    request = AppointmentRequest(schedule=schedule)

    assert request.schedule.date.status is DateStatus.UNKNOWN
    assert request.schedule.time.period is TimePeriod.EVENING
