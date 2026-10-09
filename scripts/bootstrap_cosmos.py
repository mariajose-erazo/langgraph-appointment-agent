"""Explicitly create or validate the Cosmos development infrastructure."""

from pathlib import Path
import sys

from azure.cosmos import PartitionKey
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cne_agent.adapters.cosmos.client import create_cosmos_client  # noqa: E402
from cne_agent.adapters.cosmos.config import CosmosConfig  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    config = CosmosConfig.from_env()
    client = create_cosmos_client(config)
    database = client.create_database_if_not_exists(config.database_name)
    definitions = (
        (config.professionals_container, "/business_id"),
        (config.schedule_container, "/schedule_key"),
        (config.closures_container, "/business_id"),
    )
    for name, path in definitions:
        container = database.create_container_if_not_exists(
            id=name,
            partition_key=PartitionKey(path=path),
        )
        properties = container.read()
        paths = properties.get("partitionKey", {}).get("paths")
        if paths != [path]:
            raise RuntimeError(
                f"container {name} usa partition key incompatible: {paths}"
            )
        print(f"validated container: {name} ({path})")


if __name__ == "__main__":
    main()
