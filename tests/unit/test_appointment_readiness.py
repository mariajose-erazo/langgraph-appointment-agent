from datetime import date, time
from datetime import timedelta

import pytest

from cne_agent.appointments.readiness import (
    AppointmentReadinessStatus,
    MissingAppointmentField,
    evaluate_appointment_readiness,
)
from cne_agent.appointments.request import (
    AppointmentRequest,
    DatePreference,
    DateStatus,
    ProfessionalMention,
    ProfessionalPreference,
    ProfessionalResolution,
    ProfessionalStatus,
    RemovalPreference,
    SchedulePreference,
    ServiceFamily,
    ServiceMention,
    TimePeriod,
    TimePreference,
    TimeStatus,
)
from cne_agent.appointments.scheduling import ServiceDefinition


DEFINITIONS = (
    ServiceDefinition("manicure", timedelta(minutes=60)),
    ServiceDefinition("removal-independent", timedelta(minutes=30)),
)


def readiness(value):
    return evaluate_appointment_readiness(
        value,
        service_definitions=DEFINITIONS,
    )


def request(*, services=True, selected=True, any_professional=False, selected_time=True):
    professional = ProfessionalPreference()
    if any_professional:
        professional = ProfessionalPreference(ProfessionalStatus.ANY)
    elif selected:
        professional = ProfessionalPreference(
            ProfessionalStatus.PREFERRED,
            (
                ProfessionalMention(
                    "Laura", "laura", ProfessionalResolution.RESOLVED
                ),
            ),
        )
    timing = (
        TimePreference(TimeStatus.EXACT, "15:00", time(15))
        if selected_time is True
        else selected_time
        if selected_time
        else TimePreference()
    )
    return AppointmentRequest(
        services=(
            ServiceMention("manicure", ServiceFamily.MANICURE, canonical_id="manicure"),
        ) if services else (),
        professional=professional,
        schedule=SchedulePreference(
            DatePreference(DateStatus.EXACT, "mañana", date(2026, 10, 8)),
            timing,
        ),
        removal=RemovalPreference(),
    )


def test_complete_specific_and_unspecified_removal_are_ready():
    result = readiness(request())
    assert result.status is AppointmentReadinessStatus.READY


def test_any_professional_is_ready():
    assert readiness(request(any_professional=True)).status is AppointmentReadinessStatus.READY


@pytest.mark.parametrize(
    ("value", "field"),
    [
        (request(services=False), MissingAppointmentField.SERVICES),
        (request(selected_time=False), MissingAppointmentField.TIME),
        (request(selected=False), MissingAppointmentField.PROFESSIONAL),
    ],
)
def test_reports_missing_information(value, field):
    result = readiness(value)
    assert result.status is AppointmentReadinessStatus.MISSING_INFORMATION
    assert field in result.missing_fields


def test_missing_date_is_reported():
    value = request()
    value = AppointmentRequest(
        value.services,
        value.professional,
        SchedulePreference(DatePreference(), value.schedule.time),
        value.removal,
    )
    assert readiness(value).missing_fields == (MissingAppointmentField.DATE,)


def test_period_is_missing_exact_time():
    value = request(selected_time=TimePreference(TimeStatus.PERIOD, "tarde", period=TimePeriod.AFTERNOON))
    assert readiness(value).missing_fields == (MissingAppointmentField.TIME,)


def test_unresolved_service_after_success_is_a_contract_error():
    value = request()
    value = AppointmentRequest(
        (ServiceMention("manicure", ServiceFamily.MANICURE),),
        value.professional,
        value.schedule,
    )
    with pytest.raises(RuntimeError, match="no resuelto"):
        readiness(value)


def test_missing_operational_definition_is_a_configuration_error():
    with pytest.raises(RuntimeError, match="definicion operacional"):
        evaluate_appointment_readiness(request(), service_definitions=())
