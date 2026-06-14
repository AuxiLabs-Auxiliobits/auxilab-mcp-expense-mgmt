"""Outbound messaging — enqueue work for the workers package (SCOPING §11, §14).

Production sends a JSON message to a Service Bus queue (Managed Identity); with no
`servicebus_namespace` configured the call is a logged no-op so the API runs offline. In
that mode you drive ingestion manually with `python -m workers ingestion` against a local
message, or simply exercise the rest of the flow without indexing.

`azure-servicebus` / `azure-identity` are imported lazily.
"""

from __future__ import annotations

import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def _use_azure() -> bool:
    return bool(settings.servicebus_namespace)


def enqueue_ingestion(*, agency_id: str, policy_version: str, blob_uri: str, policy_id: str) -> bool:
    """Enqueue one policy doc for the ingestion worker. Returns True if actually sent.

    The payload shape matches `workers.consumers.ingestion.ingest_document`.
    """
    payload = {
        "agency_id": agency_id,
        "policy_version": policy_version,
        "blob_uri": blob_uri,
        "policy_id": policy_id,
    }

    if not _use_azure():
        logger.info("ingestion enqueue (offline no-op): %s", payload)
        return False

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.servicebus import ServiceBusClient, ServiceBusMessage  # noqa: PLC0415

    fqns = f"{settings.servicebus_namespace}.servicebus.windows.net"
    client = ServiceBusClient(fqns, credential=DefaultAzureCredential())
    with client, client.get_queue_sender(settings.ingestion_queue_name) as sender:
        sender.send_messages(ServiceBusMessage(json.dumps(payload)))
    logger.info("ingestion enqueued for policy %s (agency=%s)", policy_id, agency_id)
    return True
