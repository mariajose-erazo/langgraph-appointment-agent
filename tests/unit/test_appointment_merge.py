from datetime import date, time

import pytest

from cne_agent.appointments.merge import MergeError, merge_appointment_request
from cne_agent.appointments.request import (
    AddRankOperation,
    AddServiceOperation,
    AppointmentRequest,
    AppointmentRequestPatch,
    Clear,
    DatePreference,
    DateStatus,
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


def manicure(variant=None, raw_text="manicure"):
    return ServiceMention(raw_text, ServiceFamily.MANICURE, variant)


def pedicure(variant=None, raw_text="pedicure"):
    return ServiceMention(raw_text, ServiceFamily.PEDICURE, variant)


def resolved(raw_text, canonical_id):
    return ProfessionalMention(
        raw_text,
        canonical_id,
        ProfessionalResolution.RESOLVED,
    )


def unresolved(raw_text):
    return ProfessionalMention(raw_text, None, ProfessionalResolution.UNRESOLVED)


def preferred(*mentions, fallback=ProfessionalFallback.NONE):
    return ProfessionalPreference(
        ProfessionalStatus.PREFERRED,
        mentions,
        fallback,
    )


def removal(role):
    return RemovalPreference(RemovalStatus.REQUIRED, role)


def request_with(**changes):
    return AppointmentRequest(**changes)


def merge(current, **changes):
    return merge_appointment_request(
        current,
        AppointmentRequestPatch(**changes),
    )


def test_empty_patch_returns_the_same_request():
    current = request_with(services=(manicure(),))

    assert merge_appointment_request(current, AppointmentRequestPatch()) is current


def test_add_new_service_appends_it():
    current = request_with(services=(manicure(),))

    result = merge(
        current,
        service_operations=(AddServiceOperation(pedicure()),),
    )

    assert result.services == (manicure(), pedicure())
    assert current.services == (manicure(),)


def test_add_existing_service_identity_fails():
    current = request_with(services=(manicure(raw_text="mani"),))

    with pytest.raises(MergeError, match="servicio"):
        merge(current, service_operations=(AddServiceOperation(manicure()),))


def test_add_different_variant_of_the_same_family_is_valid():
    current = request_with(services=(manicure("semipermanente"),))

    result = merge(
        current,
        service_operations=(AddServiceOperation(manicure()),),
    )

    assert result.services == (manicure("semipermanente"), manicure())


def test_remove_existing_service():
    current = request_with(services=(manicure(), pedicure()))

    result = merge(
        current,
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
        ),
    )

    assert result.services == (manicure(),)


def test_remove_missing_service_is_a_no_op():
    current = request_with(services=(manicure(),))

    result = merge(
        current,
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
        ),
    )

    assert result.services == (manicure(),)


def test_remove_exact_variant_does_not_remove_another():
    current = request_with(services=(pedicure("semipermanente"),))

    result = merge(
        current,
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
        ),
    )

    assert result.services == (pedicure("semipermanente"),)


def test_remove_then_add_same_service_moves_it_to_the_end():
    current = request_with(services=(manicure(), pedicure()))

    result = merge(
        current,
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.MANICURE)),
            AddServiceOperation(manicure()),
        ),
    )

    assert result.services == (pedicure(), manicure())


def test_set_services_replaces_the_whole_list():
    current = request_with(services=(manicure(), pedicure()))

    result = merge(
        current,
        service_operations=(SetServiceOperation((pedicure(),)),),
    )

    assert result.services == (pedicure(),)


def test_clear_services_empties_the_list():
    current = request_with(services=(manicure(), pedicure()))

    result = merge(current, service_operations=(Clear(),))

    assert result.services == ()


def test_add_new_professional_appends_her():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(AddRankOperation(resolved("Valentina", "valentina")),)
        ),
    )

    assert result.professional.ranked == (
        resolved("Laura", "laura"),
        resolved("Valentina", "valentina"),
    )


def test_add_existing_professional_identity_fails():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    with pytest.raises(MergeError, match="profesional"):
        merge(
            current,
            professional=ProfessionalPreferencePatch(
                ranked_operations=(
                    AddRankOperation(resolved("Lau", "laura")),
                )
            ),
        )


def test_remove_existing_professional():
    current = request_with(
        professional=preferred(
            resolved("Laura", "laura"),
            resolved("Valentina", "valentina"),
        )
    )

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(
                RemoveRankOperation(ProfessionalSelector(canonical_id="laura")),
            )
        ),
    )

    assert result.professional.ranked == (resolved("Valentina", "valentina"),)


def test_remove_missing_professional_is_a_no_op():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(
                RemoveRankOperation(
                    ProfessionalSelector(canonical_id="valentina")
                ),
            )
        ),
    )

    assert result.professional == current.professional


def test_two_identical_removes_are_valid():
    current = request_with(
        professional=preferred(
            resolved("Laura", "laura"),
            resolved("Valentina", "valentina"),
        )
    )
    remove_laura = RemoveRankOperation(
        ProfessionalSelector(canonical_id="laura")
    )

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(remove_laura, remove_laura)
        ),
    )

    assert result.professional.ranked == (resolved("Valentina", "valentina"),)


def test_removing_the_last_preferred_professional_fails():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    with pytest.raises(MergeError, match="preferred"):
        merge(
            current,
            professional=ProfessionalPreferencePatch(
                ranked_operations=(
                    RemoveRankOperation(
                        ProfessionalSelector(canonical_id="laura")
                    ),
                )
            ),
        )


def test_explicit_change_from_preferred_to_any():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            status=SetValue(ProfessionalStatus.ANY),
            ranked_operations=(Clear(),),
            fallback=SetValue(ProfessionalFallback.NONE),
        ),
    )

    assert result.professional.status is ProfessionalStatus.ANY
    assert result.professional.ranked == ()
    assert result.professional.fallback is ProfessionalFallback.NONE


def test_remove_then_add_same_professional_moves_her_to_the_end():
    current = request_with(
        professional=preferred(
            resolved("Laura", "laura"),
            resolved("Valentina", "valentina"),
        )
    )

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(
                RemoveRankOperation(ProfessionalSelector(canonical_id="laura")),
                AddRankOperation(resolved("Laura", "laura")),
            )
        ),
    )

    assert result.professional.ranked == (
        resolved("Valentina", "valentina"),
        resolved("Laura", "laura"),
    )


def test_resolved_and_unresolved_with_the_same_text_stay_distinct():
    current = request_with(professional=preferred(resolved("Laura", "laura")))

    result = merge(
        current,
        professional=ProfessionalPreferencePatch(
            ranked_operations=(AddRankOperation(unresolved("Laura")),)
        ),
    )

    assert result.professional.ranked == (
        resolved("Laura", "laura"),
        unresolved("Laura"),
    )


def test_clear_date_resets_only_the_date():
    current = request_with(
        schedule=SchedulePreference(
            date=DatePreference(
                DateStatus.EXACT,
                expression="mañana",
                resolved_date=date(2026, 9, 23),
            ),
            time=TimePreference(TimeStatus.EXACT, resolved_time=time(16, 0)),
        )
    )

    result = merge(current, date=Clear())

    assert result.schedule.date == DatePreference()
    assert result.schedule.time == current.schedule.time


def test_set_value_replaces_the_whole_date():
    current = request_with(
        schedule=SchedulePreference(
            date=DatePreference(
                DateStatus.EXACT,
                expression="mañana",
                resolved_date=date(2026, 9, 23),
            )
        )
    )
    replacement = DatePreference(
        DateStatus.EXACT,
        resolved_date=date(2026, 9, 25),
    )

    result = merge(current, date=SetValue(replacement))

    assert result.schedule.date == replacement
    assert result.schedule.date.expression is None


def test_clear_time_resets_only_the_time():
    current = request_with(
        schedule=SchedulePreference(
            date=DatePreference(DateStatus.UNKNOWN, expression="no sé"),
            time=TimePreference(
                TimeStatus.PERIOD,
                expression="en la tarde",
                period=TimePeriod.AFTERNOON,
            ),
        )
    )

    result = merge(current, time=Clear())

    assert result.schedule.time == TimePreference()
    assert result.schedule.date == current.schedule.date


def test_set_value_replaces_the_whole_time():
    current = request_with(
        schedule=SchedulePreference(
            time=TimePreference(
                TimeStatus.EXACT,
                expression="a las 4",
                resolved_time=time(16, 0),
            )
        )
    )
    replacement = TimePreference(TimeStatus.EXACT, resolved_time=time(17, 0))

    result = merge(current, time=SetValue(replacement))

    assert result.schedule.time == replacement
    assert result.schedule.time.expression is None


def test_clear_removal_resets_only_the_removal():
    current = request_with(
        services=(pedicure(),),
        removal=removal(RemovalRole.ADDON),
    )

    result = merge(current, removal=Clear())

    assert result.removal == RemovalPreference()
    assert result.services == (pedicure(),)


def test_set_value_replaces_the_whole_removal():
    current = request_with(
        services=(pedicure(),),
        removal=removal(RemovalRole.ADDON),
    )
    replacement = RemovalPreference(RemovalStatus.NOT_REQUIRED)

    result = merge(current, removal=SetValue(replacement))

    assert result.removal == replacement
    assert result.services == (pedicure(),)


def test_addon_without_services_after_merge_fails():
    current = request_with(
        services=(pedicure(),),
        removal=removal(RemovalRole.ADDON),
    )

    with pytest.raises(MergeError, match="addon"):
        merge(
            current,
            service_operations=(
                RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
            ),
        )


def test_only_removal_rejects_an_added_service():
    current = request_with(removal=removal(RemovalRole.ONLY))

    with pytest.raises(MergeError, match="only"):
        merge(current, service_operations=(AddServiceOperation(manicure()),))


def test_failed_operation_does_not_change_current():
    current = request_with(services=(manicure(),))
    services = current.services

    with pytest.raises(MergeError):
        merge(current, service_operations=(AddServiceOperation(manicure()),))

    assert current.services is services


def test_late_failure_does_not_leave_partial_changes():
    current = request_with(
        services=(manicure(), pedicure()),
        removal=removal(RemovalRole.ADDON),
    )
    services = current.services

    with pytest.raises(MergeError, match="addon"):
        merge(
            current,
            service_operations=(
                RemoveServiceOperation(ServiceSelector(ServiceFamily.MANICURE)),
                RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
            ),
        )

    assert current.services is services


def test_operations_apply_in_order():
    current = request_with(services=(manicure(), pedicure()))

    result = merge(
        current,
        service_operations=(
            RemoveServiceOperation(ServiceSelector(ServiceFamily.PEDICURE)),
            AddServiceOperation(pedicure()),
        ),
    )

    assert result.services == (manicure(), pedicure())
