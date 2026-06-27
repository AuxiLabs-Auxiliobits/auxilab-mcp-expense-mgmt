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


def delete_receipt_blob(uri: str) -> None:
    """Best-effort delete of a receipt blob (used when a library upload is attached or removed).
    Never raises — an orphaned blob is preferable to a failed user action. Offline unlinks the
    `file://` path; Azure deletes the blob with the API's Managed Identity."""
    if not uri:
        return
    try:
        if uri.startswith("file:"):
            from urllib.parse import unquote, urlparse  # noqa: PLC0415

            path = unquote(urlparse(uri).path)
            if os.name == "nt" and path.startswith("/"):
                path = path[1:]
            Path(path).unlink(missing_ok=True)
            return

        from azure.identity import DefaultAzureCredential  # noqa: PLC0415
        from azure.storage.blob import BlobClient  # noqa: PLC0415

        BlobClient.from_blob_url(uri, credential=DefaultAzureCredential()).delete_blob()
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass


def read_receipt_blob(uri: str) -> bytes:
    """Read a receipt's bytes for streaming back to the UI. Offline resolves `file://`;
    Azure reads the blob with the API's Managed Identity (Blob Data Contributor)."""
    if uri.startswith("file:"):
        from urllib.parse import unquote, urlparse  # noqa: PLC0415

        path = unquote(urlparse(uri).path)
        if os.name == "nt" and path.startswith("/"):
            path = path[1:]
        return Path(path).read_bytes()

    from azure.identity import DefaultAzureCredential  # noqa: PLC0415
    from azure.storage.blob import BlobClient  # noqa: PLC0415

    return BlobClient.from_blob_url(uri, credential=DefaultAzureCredential()).download_blob().readall()


def read_policy_blob(uri: str) -> bytes:
    """Read a policy document back (used by tests / local tooling). Offline only resolves
    `file://` URIs; Azure URIs require the worker's Blob reader role."""
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
read_blob = read_policy_blob
