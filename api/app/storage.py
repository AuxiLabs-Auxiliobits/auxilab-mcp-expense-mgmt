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


def upload_receipt_blob(employee_id: str, filename: str, data: bytes) -> str:
    """Store a receipt under `receipts/{employee_id}/{filename}` and return its URI.

    Azure: uploads to the `receipt_container` with the `{employee_id}/` prefix (the folder
    hierarchy required by the change spec) and returns the blob URL. Offline: writes under
    `receipt_local_dir/{employee_id}/` and returns a `file://` path. Callers pass an already
    collision-safe `filename` (e.g. prefixed with the attachment id).
    """
    blob_name = f"{employee_id}/{filename}"

    if not _use_azure():
        root = Path(settings.receipt_local_dir) / employee_id
        root.mkdir(parents=True, exist_ok=True)
        dest = root / filename
        dest.write_bytes(data)
        return dest.resolve().as_uri()

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobServiceClient  # noqa: PLC0415

    client = BlobServiceClient(
        account_url=settings.storage_account_url, credential=DefaultAzureCredential()
    )
    container = client.get_container_client(settings.receipt_container)
    container.upload_blob(name=blob_name, data=data, overwrite=True)
    return f"{settings.storage_account_url.rstrip('/')}/{settings.receipt_container}/{blob_name}"


def read_blob(uri: str) -> bytes:
    """Read a stored blob (policy or receipt) back by its URI.

    Offline resolves `file://` URIs from disk. In Azure the API reads the receipt/policy
    container with its Managed Identity (Blob Data Reader) and streams the bytes to the
    authorized caller — the scope/RBAC check happens in the router before this is called.
    """
    if uri.startswith("file:"):
        from urllib.parse import urlparse, unquote  # noqa: PLC0415

        path = unquote(urlparse(uri).path)
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]
        return Path(path).read_bytes()

    # Azure: parse "{account_url}/{container}/{blob_name}" and download.
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobServiceClient  # noqa: PLC0415

    account = settings.storage_account_url.rstrip("/")
    rest = uri[len(account) + 1 :]
    container, _, blob_name = rest.partition("/")
    client = BlobServiceClient(account_url=account, credential=DefaultAzureCredential())
    return client.get_container_client(container).download_blob(blob_name).readall()


# Back-compat alias (policy docs read the same way).
read_policy_blob = read_blob
