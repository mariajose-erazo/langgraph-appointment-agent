"""Cosmos client composition without infrastructure provisioning."""

from typing import Any

from azure.cosmos import CosmosClient

from cne_agent.adapters.cosmos.config import CosmosConfig, CosmosConfigurationError


def create_cosmos_client(
    config: CosmosConfig,
    *,
    credential: Any | None = None,
) -> CosmosClient:
    selected_credential = credential
    if selected_credential is None and config.auth_mode == "key":
        selected_credential = config.key
    if selected_credential is None:
        raise CosmosConfigurationError(
            "default_credential exige un credential inyectado"
        )
    return CosmosClient(config.endpoint, credential=selected_credential)


def get_container_clients(client: CosmosClient, config: CosmosConfig):
    database = client.get_database_client(config.database_name)
    return (
        database.get_container_client(config.professionals_container),
        database.get_container_client(config.schedule_container),
        database.get_container_client(config.closures_container),
    )
