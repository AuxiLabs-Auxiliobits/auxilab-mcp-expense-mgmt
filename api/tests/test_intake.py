"""Live intake: deterministic policy-check + receipt scan (SCOPING §4, §6.1)."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(9000, 9999))


def test_policy_check_flags_over_meal_limit(client):
    emp = login(client, "employee@demo.local")
    # Baseline per-meal limit is 75 → a 500 meal must produce violation(s).
    over = client.post(
        "/intake/policy-check",
        json={
            "category": "Meals & Entertainment",
            "amount": "500.00",
            "currency": "USD",
            "merchant": "Steakhouse",
            "description": "team dinner",
            "expense_date": THIS_MONTH,
            "has_receipt": True,
        },
        headers=auth(emp),
    )
    assert over.status_code == 200, over.text
    assert over.json()["status"] in {"fail", "warn"}
    assert len(over.json()["violations"]) >= 1


def test_policy_check_clean_item_passes(client):
    emp = login(client, "employee@demo.local")
    clean = client.post(
        "/intake/policy-check",
        json={
            "category": "Meals & Entertainment",
            "amount": "12.00",
            "currency": "USD",
            "merchant": "Cafe",
            "description": "coffee",
            "expense_date": THIS_MONTH,
            "has_receipt": True,
        },
        headers=auth(emp),
    )
    assert clean.status_code == 200, clean.text
    assert clean.json()["status"] == "pass"


def test_policy_check_requires_auth(client):
    assert client.post("/intake/policy-check", json={"amount": "10.00"}).status_code == 401


def test_policy_advisory_empty_offline(client):
    # No Azure AI Search configured in tests → advisory returns no clause (never errors).
    emp = login(client, "employee@demo.local")
    r = client.post(
        "/intake/policy-advisory",
        json={"category": "Meals & Entertainment", "merchant": "Cafe", "description": "lunch"},
        headers=auth(emp),
    )
    assert r.status_code == 200, r.text
    assert r.json()["clause"] is None


def _draft_with_item(client, token):
    n = next(_counter)
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Scan {n}",
            "period": PERIOD,
            "line_items": [
                {
                    "category": "Meals & Entertainment",
                    "amount": "42.00",
                    "currency": "USD",
                    "merchant": "Cafe",
                    "description": "lunch",
                    "expense_date": THIS_MONTH,
                    "receipt_datetime": f"{THIS_MONTH}T1{n % 9}:00:00",
                    "receipt_total": f"{n}.00",
                    "tax": "2.00",
                }
            ],
        },
        headers=auth(token),
    ).json()
    return sheet, sheet["line_items"][0]["id"]


def test_scan_404_without_receipt(client):
    emp = login(client, "employee@demo.local")
    sheet, li = _draft_with_item(client, emp)
    r = client.post(f"/sheets/{sheet['id']}/line-items/{li}/scan", headers=auth(emp))
    assert r.status_code == 404


def test_scan_text_receipt_offline(client):
    emp = login(client, "employee@demo.local")
    sheet, li = _draft_with_item(client, emp)
    receipt = b"Merchant: Cafe Bistro\nTotal: 42.00\nTax: 2.00\nLatte 40.00\n"
    up = client.post(
        f"/sheets/{sheet['id']}/line-items/{li}/receipt",
        files={"file": ("receipt.txt", receipt, "text/plain")},
        headers=auth(emp),
    )
    # .txt isn't an allowed receipt type, so attach a .pdf-named text blob instead.
    if up.status_code != 201:
        up = client.post(
            f"/sheets/{sheet['id']}/line-items/{li}/receipt",
            files={"file": ("receipt.pdf", receipt, "application/pdf")},
            headers=auth(emp),
        )
    assert up.status_code == 201, up.text

    r = client.post(f"/sheets/{sheet['id']}/line-items/{li}/scan", headers=auth(emp))
    assert r.status_code == 200, r.text
    body = r.json()
    # Offline path extracts text (no Doc Intelligence configured in tests).
    assert body["source"] in {"text", "unavailable", "document_intelligence"}
    assert "entered_amount" in body
