"""Generic Service Bus consumer loop (SCOPING §8, §11, §14).

Receive → dispatch to a handler → complete on success, retry-with-backoff on transient
failure, dead-letter after N deliveries. The cardinal rule (SCOPING §8, §14): NEVER
silent-approve on error — a handler failure abandons/dead-letters the message and leaves
the sheet on the queue for retry or human attention, it never falls through to "approved".

`azure-servicebus` is imported lazily so the module imports without the `[azure]` extra.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from workers.config import Settings

logger = logging.getLogger(__name__)

# A handler takes the decoded message body (str) and raises on failure.
MessageHandler = Callable[[str], None]


def run_consumer(
    queue_name: str,
    handler: MessageHandler,
    settings: Settings,
    *,
    max_messages: int | None = None,
) -> None:
    """Consume `queue_name`, dispatching each message body to `handler` (SCOPING §14).

    `max_messages` bounds the loop for tests/smoke runs; None runs until interrupted.
    Requires a real Service Bus connection (the `[azure]` extra + WORKERS_SERVICE_BUS_*).
    """
    if not settings.service_bus_enabled:
        raise RuntimeError(
            "No Service Bus connection configured. Set WORKERS_SERVICE_BUS_CONNECTION_STRING "
            "or WORKERS_SERVICE_BUS_NAMESPACE and install the 'azure' extra, or use "
            "`python -m workers demo` for offline."
        )
    try:
        from azure.servicebus import ServiceBusClient  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - exercised only with extras absent
        raise RuntimeError(
            "run_consumer needs the 'azure' extra: pip install expense-workers[azure]"
        ) from e

    client = _build_client(ServiceBusClient, settings)
    processed = 0
    with client, client.get_queue_receiver(
        queue_name=queue_name,
        max_wait_time=settings.receive_max_wait_seconds,
    ) as receiver:
        logger.info("Consuming queue %s", queue_name)
        # The receiver iterator stops after an idle window; re-enter it so the worker stays
        # alive and keeps waiting for messages. `max_messages` bounds this for tests/smoke.
        while True:
            for msg in receiver:
                _process_message(receiver, msg, handler, settings)
                processed += 1
                if max_messages is not None and processed >= max_messages:
                    return
            if max_messages is not None:
                return  # bounded run: idle window elapsed, nothing more to take
            # Unbounded: loop and keep listening (Ctrl-C to stop).


def _build_client(service_bus_client_cls, settings: Settings):
    """Build the ServiceBusClient (SCOPING §11).

    Prefer the connection string when set; otherwise authenticate to the fully-qualified
    namespace with the worker's Managed Identity (Service Bus Data Receiver role).
    """
    if settings.service_bus_connection_string:
        return service_bus_client_cls.from_connection_string(
            settings.service_bus_connection_string
        )

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    return service_bus_client_cls(
        fully_qualified_namespace=settings.service_bus_namespace,
        credential=DefaultAzureCredential(),
    )


def _process_message(receiver, msg, handler: MessageHandler, settings: Settings) -> None:
    """Dispatch one message; complete on success, dead-letter/abandon on failure.

    On the final delivery attempt we dead-letter (no silent approval, SCOPING §8); earlier
    attempts abandon with a short backoff so the broker redelivers (retry-with-backoff,
    SCOPING §14).
    """
    body = _decode(msg)
    try:
        handler(body)
    except Exception as exc:  # noqa: BLE001 - we must not let any error silent-approve
        delivery_count = getattr(msg, "delivery_count", 0) or 0
        if delivery_count + 1 >= settings.max_delivery_count:
            logger.error("Dead-lettering after %d deliveries: %s", delivery_count + 1, exc)
            receiver.dead_letter_message(
                msg, reason="handler_failed", error_description=str(exc)[:500]
            )
        else:
            backoff = _backoff_seconds(delivery_count)
            logger.warning("Handler failed (delivery %d), abandoning for retry: %s",
                           delivery_count + 1, exc)
            time.sleep(backoff)
            receiver.abandon_message(msg)
        return
    receiver.complete_message(msg)


def _decode(msg) -> str:
    """Decode a Service Bus message body to text."""
    body = msg.body
    if isinstance(body, (bytes, bytearray)):
        return body.decode("utf-8")
    if isinstance(body, str):
        return body
    # Body may be an iterable of byte chunks.
    try:
        return b"".join(bytes(part) for part in body).decode("utf-8")
    except TypeError:
        return str(body)


def _backoff_seconds(delivery_count: int) -> float:
    """Exponential backoff capped at 30s (SCOPING §14 retry-with-backoff)."""
    return float(min(30, 2**delivery_count))
