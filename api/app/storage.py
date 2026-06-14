"""Blob storage for uploaded documents (SCOPING §4.2, §7).

Production stores policy docs in Azure Blob via Managed Identity; with no
`storage_account_url` configured the API writes to a local directory instead, so the whole
upload → ingest flow runs offline with zero infra (mirrors the engine/worker fallbacks).

`azure-storage-blob` / `azure-identity` are imported lazily so the API imports without the
optional Azure extras.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.config import settings


def _use_azure() -> bool:
    return bool(settings.storage_account_url)


def upload_policy_blob(agency_id: str, version: int, filename: str, data: bytes) -> str:
    """Store a policy document and return its URI.

    Azure: uploads to `{policy_container}/{agency_id}/v{version}/{filename}` and returns the
    blob URL. Offline: writes under `policy_local_dir` and returns a `file://`-style path.
    The blob name is deterministic on (agency_id, version) so re-upload of a version is
    idempotent.
    """
    blob_name = f"{agency_id}/v{version}/{filename}"

    if not _use_azure():
        root = Path(settings.policy_local_dir) / agency_id / f"v{version}"
        root.mkdir(parents=True, exist_ok=True)
        dest = root / filename
        dest.write_bytes(data)
        return dest.resolve().as_uri()

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobServiceClient  # noqa: PLC0415

    client = BlobServiceClient(
        account_url=settings.storage_account_url, credential=DefaultAzureCredential()
    )
    container = client.get_container_client(settings.policy_container)
    container.upload_blob(name=blob_name, data=data, overwrite=True)
    return f"{settings.storage_account_url.rstrip('/')}/{settings.policy_container}/{blob_name}"


def read_policy_blob(uri: str) -> bytes:
    """Read a policy document back (used by tests / local tooling). Offline only resolves
    `file://` URIs; Azure URIs require the worker's Blob reader role."""
    if uri.startswith("file:"):
        from urllib.parse import urlparse, unquote  # noqa: PLC0415

        path = unquote(urlparse(uri).path)
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]
        return Path(path).read_bytes()
    raise NotImplementedError("Reading Azure blobs from the API is not supported; the worker reads them.")
