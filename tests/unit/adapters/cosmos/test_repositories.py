from datetime import date

import pytest

from cne_agent.adapters.cosmos.config import CosmosDataError
from cne_agent.adapters.cosmos.repositories import (
    CosmosProfessionalRepository,
    CosmosScheduleRepository,
)


DAY = date(2026, 10, 9)


class QueryContainer:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def query_items(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.items)


class ReadContainer:
    def __init__(self, item):
        self.item = item
        self.calls = []

    def read_item(self, **kwargs):
        self.calls.append(kwargs)
        return self.item


def professional(identifier="laura"):
    return {
        "id": identifier,
        "document_type": "professional",
        "business_id": "cne-dev",
        "professional_id": identifier,
        "display_name": identifier.title(),
        "active": True,
        "supported_service_ids": ["manicure"],
        "created_at": "2026-10-08T12:00:00Z",
        "updated_at": "2026-10-08T12:00:00Z",
        "schema_version": 1,
    }


def appointment(identifier="appt_test"):
    return {
        "id": identifier,
        "document_type": "appointment",
        "business_id": "cne-dev",
        "business_date": DAY.isoformat(),
        "schedule_key": f"cne-dev#{DAY.isoformat()}",
        "appointment_id": identifier,
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


def test_professionals_query_is_bound_to_business_partition():
    container = QueryContainer([professional()])
    values = CosmosProfessionalRepository(
        container, business_id="cne-dev"
    ).list_active()
    assert values[0].professional_id == "laura"
    assert container.calls[0]["partition_key"] == "cne-dev"


def test_specific_professional_uses_partitioned_point_read():
    container = ReadContainer(professional())
    value = CosmosProfessionalRepository(
        container, business_id="cne-dev"
    ).get("laura")
    assert value.professional_id == "laura"
    assert container.calls == [
        {"item": "laura", "partition_key": "cne-dev"}
    ]


def test_schedule_query_always_uses_materialized_daily_partition():
    container = QueryContainer([appointment()])
    appointments, blocks = CosmosScheduleRepository(
        container, business_id="cne-dev"
    ).list_for_date(DAY, ("laura",))
    assert len(appointments) == 1 and blocks == ()
    assert container.calls[0]["partition_key"] == f"cne-dev#{DAY.isoformat()}"


def test_empty_professional_scope_does_not_issue_cross_partition_query():
    container = QueryContainer([])
    result = CosmosScheduleRepository(
        container, business_id="cne-dev"
    ).list_for_date(DAY, ())
    assert result == ((), ())
    assert container.calls == []


def test_duplicate_documents_are_data_errors():
    container = QueryContainer([appointment(), appointment()])
    with pytest.raises(CosmosDataError, match="duplicado"):
        CosmosScheduleRepository(
            container, business_id="cne-dev"
        ).list_for_date(DAY, ("laura",))


def test_non_mapping_schedule_document_is_a_data_error():
    with pytest.raises(CosmosDataError, match="documento Cosmos"):
        CosmosScheduleRepository(
            QueryContainer(["corrupt"]), business_id="cne-dev"
        ).list_for_date(DAY, ("laura",))


def test_cosmos_query_failure_propagates():
    class BrokenContainer:
        def query_items(self, **_kwargs):
            raise TimeoutError("cosmos timeout")

    with pytest.raises(TimeoutError, match="cosmos timeout"):
        CosmosScheduleRepository(
            BrokenContainer(), business_id="cne-dev"
        ).list_for_date(DAY, ("laura",))
