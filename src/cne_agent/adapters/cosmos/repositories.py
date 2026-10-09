"""Concrete read repositories over Cosmos container clients."""

from datetime import date

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from cne_agent.adapters.cosmos.config import CosmosDataError
from cne_agent.adapters.cosmos.documents import (
    CosmosClosure,
    CosmosProfessional,
    parse_closure,
    parse_professional,
    parse_schedule_entry,
)
from cne_agent.appointments.scheduling import ExistingAppointment, ScheduleBlock


class CosmosProfessionalRepository:
    def __init__(self, container, *, business_id: str):
        self._container = container
        self._business_id = business_id

    def get(self, professional_id: str) -> CosmosProfessional | None:
        try:
            document = self._container.read_item(
                item=professional_id,
                partition_key=self._business_id,
            )
        except CosmosResourceNotFoundError:
            return None
        return parse_professional(document, business_id=self._business_id)

    def list_active(self) -> tuple[CosmosProfessional, ...]:
        documents = self._container.query_items(
            query=(
                "SELECT * FROM c WHERE c.document_type = @document_type "
                "AND c.active = true"
            ),
            parameters=[
                {"name": "@document_type", "value": "professional"},
            ],
            partition_key=self._business_id,
        )
        values = tuple(
            parse_professional(item, business_id=self._business_id)
            for item in documents
        )
        _ensure_unique(
            (item.professional_id for item in values),
            "profesionales duplicadas",
        )
        return values


class CosmosScheduleRepository:
    def __init__(self, container, *, business_id: str):
        self._container = container
        self._business_id = business_id

    def list_for_date(
        self,
        business_date: date,
        professional_ids: tuple[str, ...],
    ) -> tuple[tuple[ExistingAppointment, ...], tuple[ScheduleBlock, ...]]:
        if not professional_ids:
            return (), ()
        business_date_text = business_date.isoformat()
        schedule_key = f"{self._business_id}#{business_date_text}"
        documents = self._container.query_items(
            query=(
                "SELECT * FROM c WHERE "
                "ARRAY_CONTAINS(@professional_ids, c.professional_id) "
                "AND ARRAY_CONTAINS(@document_types, c.document_type)"
            ),
            parameters=[
                {"name": "@professional_ids", "value": list(professional_ids)},
                {
                    "name": "@document_types",
                    "value": ["appointment", "schedule_block"],
                },
            ],
            partition_key=schedule_key,
        )
        appointments: list[ExistingAppointment] = []
        blocks: list[ScheduleBlock] = []
        seen_ids: set[str] = set()
        for document in documents:
            parsed = parse_schedule_entry(
                document,
                business_id=self._business_id,
                business_date=business_date,
            )
            document_id = document.get("id")
            if document_id in seen_ids:
                raise CosmosDataError("documento de agenda duplicado")
            if isinstance(document_id, str):
                seen_ids.add(document_id)
            if parsed is None:
                continue
            if parsed.professional_id not in professional_ids:
                raise CosmosDataError("entrada de profesional no solicitada")
            if isinstance(parsed, ExistingAppointment):
                appointments.append(parsed)
            else:
                blocks.append(parsed)
        return tuple(appointments), tuple(blocks)


class CosmosBusinessClosureRepository:
    def __init__(self, container, *, business_id: str):
        self._container = container
        self._business_id = business_id

    def get_for_date(self, business_date: date) -> CosmosClosure | None:
        try:
            document = self._container.read_item(
                item=f"closure#{business_date.isoformat()}",
                partition_key=self._business_id,
            )
        except CosmosResourceNotFoundError:
            return None
        return parse_closure(
            document,
            business_id=self._business_id,
            business_date=business_date,
        )


def _ensure_unique(values, message):
    values = tuple(values)
    if len(set(values)) != len(values):
        raise CosmosDataError(message)
