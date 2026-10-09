"""Validated Cosmos configuration loaded from project-prefixed variables."""

from dataclasses import dataclass, field
import os
from typing import Mapping


class CosmosAdapterError(RuntimeError):
    """Base class for adapter failures."""


class CosmosConfigurationError(CosmosAdapterError):
    """Cosmos configuration is missing or contradictory."""


class CosmosDataError(CosmosAdapterError):
    """A persisted document violates the operational contract."""


class CosmosProfessionalPreconditionError(CosmosAdapterError):
    """A requested professional is unavailable as an operational candidate."""


@dataclass(frozen=True)
class CosmosConfig:
    endpoint: str
    database_name: str
    professionals_container: str
    schedule_container: str
    closures_container: str
    business_id: str
    auth_mode: str = "key"
    key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        values = {
            "endpoint": self.endpoint,
            "database_name": self.database_name,
            "professionals_container": self.professionals_container,
            "schedule_container": self.schedule_container,
            "closures_container": self.closures_container,
            "business_id": self.business_id,
        }
        for name, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise CosmosConfigurationError(f"{name} es obligatorio")
        if self.auth_mode not in {"key", "default_credential"}:
            raise CosmosConfigurationError("CNE_COSMOS_AUTH_MODE no soportado")
        if self.auth_mode == "key" and (
            not isinstance(self.key, str) or not self.key.strip()
        ):
            raise CosmosConfigurationError("CNE_COSMOS_KEY es obligatorio")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CosmosConfig":
        source = os.environ if env is None else env
        return cls(
            endpoint=source.get("CNE_COSMOS_ENDPOINT", ""),
            database_name=source.get("CNE_COSMOS_DATABASE_NAME", ""),
            professionals_container=source.get(
                "CNE_COSMOS_PROFESSIONALS_CONTAINER", ""
            ),
            schedule_container=source.get("CNE_COSMOS_SCHEDULE_CONTAINER", ""),
            closures_container=source.get("CNE_COSMOS_CLOSURES_CONTAINER", ""),
            business_id=source.get("CNE_COSMOS_BUSINESS_ID", ""),
            auth_mode=source.get("CNE_COSMOS_AUTH_MODE", "key"),
            key=source.get("CNE_COSMOS_KEY"),
        )

    def schedule_key(self, business_date: str) -> str:
        return f"{self.business_id}#{business_date}"
