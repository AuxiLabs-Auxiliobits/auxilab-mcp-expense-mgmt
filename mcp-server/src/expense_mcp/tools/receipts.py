"""Receipt tools — list metadata, upload, download, preview. Scope is enforced by the API
(owner / in-agency manager / finance-admin)."""

from __future__ import annotations

import mimetypes
import os
from typing import Any

from expense_mcp import client
from expense_mcp.annotations import READ, WRITE
from expense_mcp.client import ApiError
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def list_receipts(sheet_id: str) -> list[dict[str, Any]]:
    """List all receipts on a sheet (filename, type, size, upload date) — for review."""
    return client.get(f"/sheets/{sheet_id}/receipts")


@mcp.tool(annotations=READ)
def get_receipt_details(attachment_id: str) -> dict[str, Any]:
    """Get a receipt's metadata (filename, content type, size, uploaded_at)."""
    return client.get(f"/attachments/{attachment_id}")


@mcp.tool(annotations=WRITE)
def upload_receipt(sheet_id: str, line_item_id: str, file_path: str) -> dict[str, Any]:
    """Upload a local file as a receipt on a DRAFT line item (.pdf/.png/.jpg/.docx, ≤25MB)."""
    if not os.path.isfile(file_path):
        raise ApiError(f"File not found: {file_path}")
    name = os.path.basename(file_path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        files = {"file": (name, f.read(), ctype)}
    return client.post(f"/sheets/{sheet_id}/line-items/{line_item_id}/receipt", files=files)


@mcp.tool(annotations=WRITE)
def download_receipt(attachment_id: str, dest_path: str) -> dict[str, Any]:
    """Download a receipt's bytes to a local path. Returns where it was saved + byte size."""
    content, _headers = client.get(f"/attachments/{attachment_id}/content", params={"download": "true"}, raw=True)
    with open(dest_path, "wb") as f:
        f.write(content)
    return {"saved_to": os.path.abspath(dest_path), "bytes": len(content)}
