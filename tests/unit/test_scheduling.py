from datetime import date, datetime, time, timedelta

import pytest

from cne_agent.appointments.request import RemovalRole, RemovalStatus
from cne_agent.appointments.scheduling import (
    AvailabilityStatus,
    ExistingAppointment,
    ExistingAppointmentStatus,
    ProfessionalScope,
    ProfessionalScopeKind,
    ScheduleBlock,
    ScheduleQuery,
    ScheduleSnapshot,
    SchedulingPolicy,
    ServiceDefinition,
    UnavailabilityReason,
    calculate_service_duration,
    evaluate_availability,
)
from cne_agent.interpretation.normalizer import BOGOTA


DAY = date(2026, 10, 8)


def at(hour, minute=0):
    return datetime(2026, 10, 8, hour, minute, tzinfo=BOGOTA)


def policy():
    return SchedulingPolicy(
        (
            ServiceDefinition("manicure", timedelta(minutes=60)),
            ServiceDefinition("pedicure", timedelta(minutes=45)),
            ServiceDefinition("removal-independent", timedelta(minutes=30)),
        ),
        timezone=BOGOTA,
    )


def query(hour=15, minute=0, ids=("laura",), services=("manicure",), role=RemovalRole.UNSPECIFIED):
    return ScheduleQuery(
        services,
        DAY,
        time(hour, minute),
        ProfessionalScope(
            ProfessionalScopeKind.SPECIFIC if len(ids) == 1 else ProfessionalScopeKind.ANY,
            ids,
        ),
        RemovalStatus.UNSPECIFIED if role is RemovalRole.UNSPECIFIED else RemovalStatus.REQUIRED,
        role,
    )


def snapshot(*, appointments=(), lunches=(), ids=("laura",), closed=frozenset()):
    return ScheduleSnapshot(ids, appointments, lunches, closed)


def test_free_professional_is_available_with_one_final_buffer():
    result = evaluate_availability(query(), snapshot(), policy())
    assert result.status is AvailabilityStatus.AVAILABLE
    option = result.available_options[0]
    assert option.service_ends_at == at(16)
    assert option.occupied_until == at(16, 10)


@pytest.mark.parametrize(
    "existing",
    [
        ExistingAppointment("laura", at(14, 30), at(15, 30)),
        ExistingAppointment("laura", at(15, 15), at(15, 45)),
        ExistingAppointment("laura", at(14), at(17)),
    ],
)
def test_real_interval_intersections_block(existing):
    result = evaluate_availability(query(), snapshot(appointments=(existing,)), policy())
    assert result.status is AvailabilityStatus.UNAVAILABLE
    assert result.reason is UnavailabilityReason.APPOINTMENT_CONFLICT


def test_existing_appointment_buffer_blocks_requested_start():
    existing = ExistingAppointment("laura", at(14), at(14, 55))
    assert evaluate_availability(query(), snapshot(appointments=(existing,)), policy()).status is AvailabilityStatus.UNAVAILABLE


def test_requested_buffer_blocks_later_appointment():
    existing = ExistingAppointment("laura", at(16, 5), at(17))
    assert evaluate_availability(query(), snapshot(appointments=(existing,)), policy()).status is AvailabilityStatus.UNAVAILABLE


def test_lunch_blocks_requested_interval():
    lunch = ScheduleBlock("laura", at(15, 30), at(16, 30))
    result = evaluate_availability(query(), snapshot(lunches=(lunch,)), policy())
    assert result.reason is UnavailabilityReason.LUNCH_BLOCK


@pytest.mark.parametrize("value", [query(7, 59), query(18), query(17, 30)])
def test_business_hours_are_enforced(value):
    result = evaluate_availability(value, snapshot(), policy())
    assert result.reason is UnavailabilityReason.OUTSIDE_BUSINESS_HOURS


def test_sunday_and_injected_closure_are_closed():
    sunday = ScheduleQuery(("manicure",), date(2026, 10, 11), time(10), query().professional_scope, RemovalStatus.UNSPECIFIED, RemovalRole.UNSPECIFIED)
    assert evaluate_availability(sunday, snapshot(), policy()).reason is UnavailabilityReason.CLOSED_DAY
    assert evaluate_availability(query(), snapshot(closed=frozenset({DAY})), policy()).reason is UnavailabilityReason.CLOSED_DAY


def test_cancelled_does_not_block_but_completed_does():
    cancelled = ExistingAppointment("laura", at(15), at(16), ExistingAppointmentStatus.CANCELLED)
    completed = ExistingAppointment("laura", at(15), at(16), ExistingAppointmentStatus.COMPLETED)
    assert evaluate_availability(query(), snapshot(appointments=(cancelled,)), policy()).status is AvailabilityStatus.AVAILABLE
    assert evaluate_availability(query(), snapshot(appointments=(completed,)), policy()).status is AvailabilityStatus.UNAVAILABLE


def test_addon_and_multiple_services_change_duration_once():
    value = query(services=("manicure", "pedicure"), role=RemovalRole.ADDON)
    assert calculate_service_duration(value, policy()) == timedelta(minutes=120)
    result = evaluate_availability(value, snapshot(), policy())
    assert result.available_options[0].occupied_until - result.requested_start == timedelta(minutes=130)


def test_independent_removal_uses_its_operational_definition():
    value = query(services=(), role=RemovalRole.ONLY)
    assert calculate_service_duration(value, policy()) == timedelta(minutes=30)


def test_any_returns_all_free_professionals_in_stable_order():
    value = query(ids=("valentina", "laura"))
    result = evaluate_availability(value, snapshot(ids=("valentina", "laura")), policy())
    assert [item.professional_id for item in result.available_options] == ["laura", "valentina"]


def test_specific_does_not_fall_back_and_any_can_find_another():
    busy = ExistingAppointment("laura", at(15), at(16))
    specific = evaluate_availability(query(), snapshot(appointments=(busy,), ids=("laura", "valentina")), policy())
    any_result = evaluate_availability(query(ids=("laura", "valentina")), snapshot(appointments=(busy,), ids=("laura", "valentina")), policy())
    assert specific.status is AvailabilityStatus.UNAVAILABLE
    assert [item.professional_id for item in any_result.available_options] == ["valentina"]


def test_any_with_every_professional_busy_is_unavailable():
    appointments = (
        ExistingAppointment("laura", at(15), at(16)),
        ExistingAppointment("valentina", at(15), at(16)),
    )
    result = evaluate_availability(
        query(ids=("laura", "valentina")),
        snapshot(appointments=appointments, ids=("laura", "valentina")),
        policy(),
    )
    assert result.status is AvailabilityStatus.UNAVAILABLE
    assert result.available_options == ()


def test_lunch_block_must_last_exactly_one_hour():
    with pytest.raises(ValueError, match="60 minutos"):
        ScheduleBlock("laura", at(12), at(12, 30))
