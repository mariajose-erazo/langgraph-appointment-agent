from datetime import date, time

import pytest

from cne_agent.adapters.cosmos.availability import CosmosAvailabilityProvider
from cne_agent.adapters.cosmos.config import CosmosProfessionalPreconditionError
from cne_agent.adapters.cosmos.documents import CosmosClosure, CosmosProfessional
from cne_agent.appointments.request import RemovalRole, RemovalStatus
from cne_agent.appointments.scheduling import (
    ProfessionalScope,
    ProfessionalScopeKind,
    ScheduleQuery,
)


DAY = date(2026, 10, 9)


class Professionals:
    def __init__(self, values):
        self.values = {item.professional_id: item for item in values}
        self.requested = []

    def get(self, identifier):
        self.requested.append(identifier)
        return self.values.get(identifier)

    def list_active(self):
        return tuple(item for item in self.values.values() if item.active)


class Schedule:
    def __init__(self, result=((), ())):
        self.result = result
        self.calls = []

    def list_for_date(self, day, identifiers):
        self.calls.append((day, identifiers))
        return self.result


class Closures:
    def __init__(self, value=None):
        self.value = value

    def get_for_date(self, _day):
        return self.value


def professional(identifier, *, active=True, services=("manicure",)):
    return CosmosProfessional(identifier, identifier.title(), active, services)


def query(kind, identifiers=("laura",)):
    return ScheduleQuery(
        ("manicure",),
        DAY,
        time(15),
        ProfessionalScope(kind, identifiers),
        RemovalStatus.UNSPECIFIED,
        RemovalRole.UNSPECIFIED,
    )


def test_specific_reads_only_requested_professional_and_empty_agenda_is_valid():
    professionals = Professionals((professional("laura"), professional("valentina")))
    schedule = Schedule()
    snapshot = CosmosAvailabilityProvider(
        professionals, schedule, Closures()
    ).get_schedule(query(ProfessionalScopeKind.SPECIFIC))
    assert professionals.requested == ["laura"]
    assert schedule.calls == [(DAY, ("laura",))]
    assert snapshot.professional_ids == ("laura",)
    assert snapshot.appointments == ()


@pytest.mark.parametrize(
    "values",
    [
        (),
        (professional("laura", active=False),),
        (professional("laura", services=("pedicure",)),),
    ],
)
def test_specific_precondition_failures_are_not_empty_agendas(values):
    with pytest.raises(CosmosProfessionalPreconditionError):
        CosmosAvailabilityProvider(
            Professionals(values), Schedule(), Closures()
        ).get_schedule(query(ProfessionalScopeKind.SPECIFIC))


def test_any_returns_only_active_authorized_known_candidates_in_stable_order():
    professionals = Professionals(
        (
            professional("valentina"),
            professional("laura"),
            professional("maria_jose", active=False),
            professional("external"),
        )
    )
    schedule = Schedule()
    snapshot = CosmosAvailabilityProvider(
        professionals, schedule, Closures()
    ).get_schedule(
        query(
            ProfessionalScopeKind.ANY,
            ("valentina", "laura", "maria_jose"),
        )
    )
    assert snapshot.professional_ids == ("laura", "valentina")
    assert schedule.calls[0][1] == ("laura", "valentina")


def test_active_closure_is_added_without_deciding_availability():
    closure = CosmosClosure(DAY, True, "holiday")
    snapshot = CosmosAvailabilityProvider(
        Professionals((professional("laura"),)),
        Schedule(),
        Closures(closure),
    ).get_schedule(query(ProfessionalScopeKind.SPECIFIC))
    assert snapshot.closed_dates == frozenset({DAY})


def test_repository_failure_propagates():
    class BrokenSchedule:
        def list_for_date(self, *_args):
            raise TimeoutError("cosmos unavailable")

    with pytest.raises(TimeoutError, match="cosmos unavailable"):
        CosmosAvailabilityProvider(
            Professionals((professional("laura"),)),
            BrokenSchedule(),
            Closures(),
        ).get_schedule(query(ProfessionalScopeKind.SPECIFIC))
