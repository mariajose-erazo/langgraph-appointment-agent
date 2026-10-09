import pytest

from cne_agent.adapters.cosmos.config import (
    CosmosConfig,
    CosmosConfigurationError,
)


ENV = {
    "CNE_COSMOS_ENDPOINT": "https://example.documents.azure.com:443/",
    "CNE_COSMOS_KEY": "super-secret",
    "CNE_COSMOS_DATABASE_NAME": "cne",
    "CNE_COSMOS_PROFESSIONALS_CONTAINER": "professionals",
    "CNE_COSMOS_SCHEDULE_CONTAINER": "schedule_entries",
    "CNE_COSMOS_CLOSURES_CONTAINER": "business_closures",
    "CNE_COSMOS_BUSINESS_ID": "cne-dev",
    "CNE_COSMOS_AUTH_MODE": "key",
}


def test_loads_project_prefixed_configuration_without_exposing_key():
    config = CosmosConfig.from_env(ENV)
    assert config.schedule_key("2026-10-09") == "cne-dev#2026-10-09"
    assert "super-secret" not in repr(config)


@pytest.mark.parametrize(
    "changes",
    [
        {"CNE_COSMOS_ENDPOINT": ""},
        {"CNE_COSMOS_KEY": ""},
        {"CNE_COSMOS_AUTH_MODE": "unknown"},
    ],
)
def test_rejects_invalid_configuration(changes):
    values = ENV | changes
    with pytest.raises(CosmosConfigurationError):
        CosmosConfig.from_env(values)


def test_default_credential_mode_allows_no_static_key():
    values = ENV | {
        "CNE_COSMOS_AUTH_MODE": "default_credential",
        "CNE_COSMOS_KEY": "",
    }
    assert CosmosConfig.from_env(values).key == ""
