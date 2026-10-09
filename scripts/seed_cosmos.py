"""Idempotently load fictitious development-only operational data."""

import json
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cne_agent.adapters.cosmos.client import (  # noqa: E402
    create_cosmos_client,
    get_container_clients,
)
from cne_agent.adapters.cosmos.config import CosmosConfig  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    config = CosmosConfig.from_env()
    payload = json.loads((ROOT / "data" / "cosmos_seed.json").read_text("utf-8"))
    if payload.get("business_id") != config.business_id:
        raise RuntimeError(
            "el business_id del seed no coincide con la configuracion"
        )
    client = create_cosmos_client(config)
    professionals, schedule, closures = get_container_clients(client, config)
    for document in payload["professionals"]:
        professionals.upsert_item(document)
    for document in payload["schedule_entries"]:
        schedule.upsert_item(document)
    for document in payload["business_closures"]:
        closures.upsert_item(document)
    print(
        "seed completed: "
        f"professionals={len(payload['professionals'])} "
        f"schedule_entries={len(payload['schedule_entries'])} "
        f"closures={len(payload['business_closures'])}"
    )


if __name__ == "__main__":
    main()
