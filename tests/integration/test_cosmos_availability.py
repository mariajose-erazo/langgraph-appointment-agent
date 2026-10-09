import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from dotenv import load_dotenv

from cne_agent.adapters.cosmos.availability import (
    create_cosmos_availability_provider,
)
from cne_agent.adapters.cosmos.client import (
    create_cosmos_client,
    get_container_clients,
)
from cne_agent.adapters.cosmos.config import CosmosConfig
from cne_agent.appointments.request import RemovalRole, RemovalStatus
from cne_agent.appointments.scheduling import (
    ProfessionalScope,
    ProfessionalScopeKind,
    ScheduleQuery,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


pytestmark = [
    pytest.mark.cosmos_integration,
    pytest.mark.skipif(
        os.getenv("RUN_COSMOS_INTEGRATION_TESTS") != "1",
        reason="Cosmos integration tests are disabled.",
    ),
]


def test_real_cosmos_provider_reads_isolated_fixture():
    base = CosmosConfig.from_env()
    namespace = f"test_{uuid4().hex}"
    config = CosmosConfig(
        endpoint=base.endpoint,
        database_name=base.database_name,
        professionals_container=base.professionals_container,
        schedule_container=base.schedule_container,
        closures_container=base.closures_container,
        business_id=namespace,
        auth_mode=base.auth_mode,
        key=base.key,
    )
    client = create_cosmos_client(config)
    professionals, schedule, _closures = get_container_clients(client, config)
    professional_id = f"test_prof_{uuid4().hex}"
    appointment_id = f"test_appt_{uuid4().hex}"
    day = date.today() + timedelta(days=7)
    schedule_key = config.schedule_key(day.isoformat())
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    professional_document = {
        "id": professional_id,
        "document_type": "professional",
        "business_id": namespace,
        "professional_id": professional_id,
        "display_name": "Test Professional",
        "active": True,
        "supported_service_ids": ["manicure"],
        "created_at": now,
        "updated_at": now,
        "schema_version": 1,
    }
    start_utc = datetime.combine(day, time(20), timezone.utc)
    appointment_document = {
        "id": appointment_id,
        "document_type": "appointment",
        "business_id": namespace,
        "business_date": day.isoformat(),
        "schedule_key": schedule_key,
        "appointment_id": appointment_id,
        "professional_id": professional_id,
        "service_ids": ["manicure"],
        "starts_at": start_utc.isoformat().replace("+00:00", "Z"),
        "service_ends_at": (start_utc + timedelta(hours=1)).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "scheduled",
        "removal_status": "unspecified",
        "removal_role": "unspecified",
        "created_at": now,
        "updated_at": now,
        "schema_version": 1,
    }
    professional_created = False
    appointment_created = False
    try:
        professionals.create_item(professional_document)
        professional_created = True
        schedule.create_item(appointment_document)
        appointment_created = True
        provider = create_cosmos_availability_provider(config)
        snapshot = provider.get_schedule(
            ScheduleQuery(
                ("manicure",),
                day,
                time(15),
                ProfessionalScope(
                    ProfessionalScopeKind.SPECIFIC,
                    (professional_id,),
                ),
                RemovalStatus.UNSPECIFIED,
                RemovalRole.UNSPECIFIED,
            )
        )
        assert snapshot.professional_ids == (professional_id,)
        assert len(snapshot.appointments) == 1
    finally:
        if appointment_created:
            try:
                schedule.delete_item(appointment_id, partition_key=schedule_key)
            except CosmosResourceNotFoundError:
                pass
        if professional_created:
            try:
                professionals.delete_item(
                    professional_id,
                    partition_key=namespace,
                )
            except CosmosResourceNotFoundError:
                pass
