"""AvailabilityProvider backed by validated Cosmos repositories."""

import logging
from time import perf_counter

from cne_agent.adapters.cosmos.config import CosmosProfessionalPreconditionError
from cne_agent.adapters.cosmos.config import CosmosConfig
from cne_agent.adapters.cosmos.client import (
    create_cosmos_client,
    get_container_clients,
)
from cne_agent.adapters.cosmos.repositories import (
    CosmosBusinessClosureRepository,
    CosmosProfessionalRepository,
    CosmosScheduleRepository,
)
from cne_agent.appointments.scheduling import (
    ProfessionalScopeKind,
    ScheduleQuery,
    ScheduleSnapshot,
)
from cne_agent.appointments.request import RemovalRole


logger = logging.getLogger(__name__)


def create_cosmos_availability_provider(
    config: CosmosConfig,
    *,
    credential=None,
    independent_removal_service_id: str = "removal-independent",
):
    client = create_cosmos_client(config, credential=credential)
    professionals, schedule, closures = get_container_clients(client, config)
    return CosmosAvailabilityProvider(
        CosmosProfessionalRepository(
            professionals,
            business_id=config.business_id,
        ),
        CosmosScheduleRepository(schedule, business_id=config.business_id),
        CosmosBusinessClosureRepository(
            closures,
            business_id=config.business_id,
        ),
        independent_removal_service_id=independent_removal_service_id,
    )


class CosmosAvailabilityProvider:
    def __init__(
        self,
        professionals: CosmosProfessionalRepository,
        schedule: CosmosScheduleRepository,
        closures: CosmosBusinessClosureRepository,
        *,
        independent_removal_service_id: str = "removal-independent",
    ):
        self._professionals = professionals
        self._schedule = schedule
        self._closures = closures
        self._independent_removal_service_id = independent_removal_service_id

    def get_schedule(self, query: ScheduleQuery) -> ScheduleSnapshot:
        if not isinstance(query, ScheduleQuery):
            raise TypeError("query debe ser ScheduleQuery")
        started = perf_counter()
        try:
            professional_ids = self._resolve_professionals(query)
            appointments, blocks = self._schedule.list_for_date(
                query.requested_date,
                professional_ids,
            )
            closure = self._closures.get_for_date(query.requested_date)
            closed_dates = (
                frozenset({query.requested_date})
                if closure is not None and closure.active
                else frozenset()
            )
            snapshot = ScheduleSnapshot(
                professional_ids,
                appointments,
                blocks,
                closed_dates,
            )
            logger.info(
                "cosmos schedule read completed professionals=%d appointments=%d blocks=%d elapsed_ms=%.2f",
                len(professional_ids),
                len(appointments),
                len(blocks),
                (perf_counter() - started) * 1000,
            )
            return snapshot
        except Exception as error:
            logger.error(
                "cosmos schedule read failed error_type=%s elapsed_ms=%.2f",
                type(error).__name__,
                (perf_counter() - started) * 1000,
            )
            raise

    def _resolve_professionals(self, query: ScheduleQuery) -> tuple[str, ...]:
        required_services = set(query.service_ids)
        if query.removal_role is RemovalRole.ONLY:
            required_services = {self._independent_removal_service_id}
        requested = query.professional_scope.professional_ids
        if query.professional_scope.kind is ProfessionalScopeKind.SPECIFIC:
            professional = self._professionals.get(requested[0])
            if professional is None:
                raise CosmosProfessionalPreconditionError(
                    "la profesional solicitada no existe"
                )
            if not professional.active:
                raise CosmosProfessionalPreconditionError(
                    "la profesional solicitada no esta activa"
                )
            if not required_services <= set(professional.supported_service_ids):
                raise CosmosProfessionalPreconditionError(
                    "la profesional no esta autorizada para los servicios"
                )
            return (professional.professional_id,)

        maximum = set(requested)
        candidates = [
            item.professional_id
            for item in self._professionals.list_active()
            if item.professional_id in maximum
            and required_services <= set(item.supported_service_ids)
        ]
        return tuple(sorted(candidates))
