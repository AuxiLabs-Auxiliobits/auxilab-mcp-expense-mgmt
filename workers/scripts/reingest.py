"""Re-enqueue a policy document for ingestion (SCOPING §7).

Use when a doc is already 'published' (so the API won't re-publish/enqueue it) but the
worker didn't finish — e.g. it failed/abandoned on a transient error and you've since fixed
the cause (raised the embedding TPM, etc.). Sends one ingestion message to the queue the
running worker consumes.

    python workers/scripts/reingest.py <agency_id> <version> <blob_uri> <policy_id>

Needs WORKERS_SERVICE_BUS_CONNECTION_STRING set in this terminal (+ the [azure] extra).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workers.config import load_settings  # noqa: E402


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: reingest.py <agency_id> <version> <blob_uri> <policy_id>")
    agency_id, version, blob_uri, policy_id = sys.argv[1:5]

    settings = load_settings()
    if not settings.service_bus_connection_string:
        raise SystemExit("WORKERS_SERVICE_BUS_CONNECTION_STRING is not set in this terminal.")

    from azure.servicebus import ServiceBusClient, ServiceBusMessage  # noqa: PLC0415

    payload = {
        "agency_id": agency_id,
        "policy_version": version,
        "blob_uri": blob_uri,
        "policy_id": policy_id,
    }
    client = ServiceBusClient.from_connection_string(settings.service_bus_connection_string)
    with client, client.get_queue_sender(settings.ingestion_queue_name) as sender:
        sender.send_messages(ServiceBusMessage(json.dumps(payload)))
    print(f"enqueued -> {settings.ingestion_queue_name}: {payload}")


if __name__ == "__main__":
    main()
