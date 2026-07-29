"""Terminal demo.

``cli.py`` is what runs when Gradio is unavailable, and it is the smoke test CI relies on,
so it deserves real coverage rather than only being launched as a subprocess.
"""

from __future__ import annotations

import pytest

import cli

pytestmark = pytest.mark.usefixtures("shared_store")

ALL_DEMOS = ["policy", "receipt", "classify", "duplicates", "report"]


def test_runs_every_demo_by_default(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for heading in [
        "1. Policy Checker",
        "2. Receipt Parser",
        "3. Category Classifier",
        "4. Duplicate Detector",
        "5. Report Summariser",
    ]:
        assert heading in out


@pytest.mark.parametrize("name", ALL_DEMOS)
def test_each_demo_runs_alone(name, capsys):
    assert cli.main([name]) == 0
    assert capsys.readouterr().out.strip()


def test_several_demos_can_be_selected(capsys):
    assert cli.main(["policy", "report"]) == 0
    out = capsys.readouterr().out
    assert "1. Policy Checker" in out
    assert "5. Report Summariser" in out
    assert "2. Receipt Parser" not in out


def test_unknown_demo_is_rejected_with_guidance(capsys):
    assert cli.main(["nope"]) == 2
    out = capsys.readouterr().out
    assert "Unknown demo" in out
    assert "Available:" in out
    for name in ALL_DEMOS:
        assert name in out


def test_demo_registry_matches_the_documented_names():
    assert list(cli.DEMOS) == ALL_DEMOS


# --------------------------------------------------------------------------- #
# Output correctness — the demo must not claim something the engine disagrees with
# --------------------------------------------------------------------------- #
def test_policy_demo_reports_the_real_violations(capsys):
    cli.main(["policy"])
    out = capsys.readouterr().out
    assert "OVER_CATEGORY_LIMIT" in out
    assert "PROHIBITED_CATEGORY" in out
    assert "RECEIPT_REQUIRED" in out
    assert "AMOUNT_MISMATCH" in out
    assert "FUTURE_DATE" in out


def test_receipt_demo_shows_both_outcomes(capsys):
    cli.main(["receipt"])
    out = capsys.readouterr().out
    assert "[ok]" in out  # the clean receipt reconciles
    assert "caught, off by 10.00" in out  # the tampered one does not


def test_duplicate_demo_finds_the_seeded_pair(capsys):
    cli.main(["duplicates"])
    out = capsys.readouterr().out
    assert "risk=high" in out
    assert "EXACT_KEY" in out


def test_report_demo_prints_a_narrative(capsys):
    cli.main(["report"])
    out = capsys.readouterr().out
    assert "Compliance rate" in out
    assert "Reviewed 5 line item(s)" in out


def test_mark_helper():
    assert "ok" in cli.mark(True)
    assert "flag" in cli.mark(False)
