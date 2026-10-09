from datetime import date

import pytest

from cne_agent.adapters.cosmos.config import CosmosDataError
from cne_agent.adapters.cosmos.documents import (
    parse_closure,
    parse_professional,
    parse_schedule_entry,
)
from cne_agent.appointments.scheduling import (
    ExistingAppointmentStatus,
    ScheduleBlockKind,
)


DAY = date(2026, 10, 9)


def professional(**changes):
    value = {
        "id": "laura",
        "document_type": "professional",
        "business_id": "cne-dev",
        "professional_id": "laura",
        "display_name": "Laura",
        "active": True,
        "supported_service_ids": ["manicure"],
        "created_at": "2026-10-08T12:00:00Z",
        "updated_at": "2026-10-08T12:00:00Z",
        "schema_version": 1,
    }
    return value | changes


def appointment(**changes):
    value = {
        "id": "appt_test",
        "document_type": "appointment",
        "business_id": "cne-dev",
        "business_date": DAY.isoformat(),
        "schedule_key": f"cne-dev#{DAY.isoformat()}",
        "appointment_id": "appt_test",
        "professional_id": "laura",
        "service_ids": ["manicure"],
        "starts_at": "2026-10-09T20:00:00Z",
        "service_ends_at": "2026-10-09T21:00:00Z",
        "status": "scheduled",
        "removal_status": "unspecified",
        "removal_role": "unspecified",
        "created_at": "2026-10-08T12:00:00Z",
        "updated_at": "2026-10-08T12:00:00Z",
        "schema_version": 1,
    }
    return value | changes


def block(**changes):
    value = {
        "id": "block_test",
        "document_type": "schedule_block",
        "business_id": "cne-dev",
        "business_date": DAY.isoformat(),
        "schedule_key": f"cne-dev#{DAY.isoformat()}",
        "block_id": "block_test",
        "professional_id": "laura",
        "block_type": "lunch",
        "starts_at": "2026-10-09T17:00:00Z",
        "ends_at": "2026-10-09T18:00:00Z",
        "active": True,
        "created_at": "2026-10-08T12:00:00Z",
        "updated_at": "2026-10-08T12:00:00Z",
        "schema_version": 1,
    }
    return value | changes


def test_parses_professional_and_known_appointment_status():
    parsed_professional = parse_professional(professional(), business_id="cne-dev")
    parsed_appointment = parse_schedule_entry(
        appointment(), business_id="cne-dev", business_date=DAY
    )
    assert parsed_professional.professional_id == "laura"
    assert parsed_appointment.status is ExistingAppointmentStatus.SCHEDULED


def test_parses_general_block_kind():
    parsed = parse_schedule_entry(
        block(
            block_type="absence",
            starts_at="2026-10-09T13:00:00Z",
            ends_at="2026-10-09T15:00:00Z",
        ),
        business_id="cne-dev",
        business_date=DAY,
    )
    assert parsed.kind is ScheduleBlockKind.ABSENCE


@pytest.mark.parametrize(
    "document",
    [
        appointment(status="unknown"),
        appointment(starts_at="2026-10-09T15:00:00"),
        appointment(schedule_key="wrong"),
        appointment(service_ids=["manicure", "manicure"]),
        block(ends_at="2026-10-09T17:30:00Z"),
        appointment(schema_version=2),
    ],
)
def test_rejects_corrupt_schedule_documents(document):
    with pytest.raises(CosmosDataError):
        parse_schedule_entry(document, business_id="cne-dev", business_date=DAY)


def test_parses_active_closure_and_rejects_unknown_type():
    document = {
        "id": f"closure#{DAY.isoformat()}",
        "document_type": "business_closure",
        "business_id": "cne-dev",
        "business_date": DAY.isoformat(),
        "closure_type": "holiday",
        "active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "schema_version": 1,
    }
    assert parse_closure(document, business_id="cne-dev", business_date=DAY).active
    with pytest.raises(CosmosDataError):
        parse_closure(
            document | {"closure_type": "surprise"},
            business_id="cne-dev",
            business_date=DAY,
        )
