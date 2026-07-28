"""Receipt library (My Receipts) — upload an unassigned receipt, list it, attach it to a line
item via the existing attach path, and confirm it leaves the library and lands as a real
attachment. Plus owner-isolation on the library."""

from __future__ import annotations

from tests.conftest import auth, login

_PDF = ("r.pdf", b"%PDF-1.4 receipt bytes", "application/pdf")


def _draft_with_item(client, token) -> tuple[str, str]:
    sid = client.post("/sheets", json={"title": "Lib Flow", "period": "2026-06"}, headers=auth(token)).json()["id"]
    client.post(f"/sheets/{sid}/line-items", headers=auth(token), json={
        "amount": "42.00", "merchant": "Cafe", "expense_date": "2026-06-10",
        "category": "Meals & Entertainment", "receipt_total": "42.00",
        "receipt_datetime": "2026-06-10T12:00:00"})
    li = client.get(f"/sheets/{sid}", headers=auth(token)).json()["line_items"][0]["id"]
    return sid, li


def test_upload_list_and_attach_from_library(client):
    et = login(client, "employee@demo.local")

    # Upload to the library (unassigned).
    up = client.post("/receipts", files={"file": _PDF}, headers=auth(et))
    assert up.status_code == 201, up.text
    rid = up.json()["id"]
    assert up.json()["filename"] == "r.pdf"

    # It shows up in My Receipts.
    listed = client.get("/receipts", headers=auth(et)).json()
    assert any(r["id"] == rid for r in listed)

    # And is downloadable.
    blob = client.get(f"/receipts/{rid}/file", headers=auth(et))
    assert blob.status_code == 200 and blob.content == _PDF[1]

    # Attach it to a line item.
    sid, li = _draft_with_item(client, et)
    att = client.post(
        f"/sheets/{sid}/line-items/{li}/receipt/from-library",
        json={"receipt_id": rid}, headers=auth(et),
    )
    assert att.status_code == 201, att.text
    assert att.json()["line_item_id"] == li

    # It left the library and is now a real attachment on the line item.
    assert all(r["id"] != rid for r in client.get("/receipts", headers=auth(et)).json())
    receipts = client.get(f"/sheets/{sid}/line-items/{li}/receipts", headers=auth(et)).json()
    assert len(receipts) == 1 and receipts[0]["filename"] == "r.pdf"


def test_delete_from_library(client):
    et = login(client, "employee@demo.local")
    rid = client.post("/receipts", files={"file": _PDF}, headers=auth(et)).json()["id"]
    assert client.delete(f"/receipts/{rid}", headers=auth(et)).status_code == 204
    assert all(r["id"] != rid for r in client.get("/receipts", headers=auth(et)).json())


def test_library_is_owner_scoped(client):
    et = login(client, "employee@demo.local")
    other = login(client, "manager@demo.local")
    rid = client.post("/receipts", files={"file": _PDF}, headers=auth(et)).json()["id"]
    # Another user can neither see, download, nor delete it.
    assert all(r["id"] != rid for r in client.get("/receipts", headers=auth(other)).json())
    assert client.get(f"/receipts/{rid}/file", headers=auth(other)).status_code == 404
    assert client.delete(f"/receipts/{rid}", headers=auth(other)).status_code == 404
