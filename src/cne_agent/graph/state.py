from datetime import datetime
from typing import TypedDict

from langgraph.graph import MessagesState

from cne_agent.appointments.request import AppointmentRequest
from cne_agent.interpretation.models import TurnInterpretation
from cne_agent.interpretation.normalizer import (
    NormalizationResult,
    ProfessionalCatalogEntry,
    ServiceCatalogEntry,
)


class ConversationState(MessagesState):
    turn_interpretation: TurnInterpretation | None
    appointment_request: AppointmentRequest | None
    normalization_result: NormalizationResult | None


class ConversationContext(TypedDict):
    current_date: str
    business_context: str
    capabilities_context: str
    service_catalog: tuple[ServiceCatalogEntry, ...]
    professional_catalog: tuple[ProfessionalCatalogEntry, ...]
    reference_at: datetime
