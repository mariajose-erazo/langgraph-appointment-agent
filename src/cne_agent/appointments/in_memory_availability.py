"""In-memory schedule source for deterministic tests and local development."""

from dataclasses import dataclass

from cne_agent.appointments.scheduling import ScheduleQuery, ScheduleSnapshot


@dataclass
class InMemoryAvailabilityProvider:
    snapshot: ScheduleSnapshot
    call_count: int = 0
    queries: tuple[ScheduleQuery, ...] = ()

    def get_schedule(self, query: ScheduleQuery) -> ScheduleSnapshot:
        self.call_count += 1
        self.queries += (query,)
        return self.snapshot
