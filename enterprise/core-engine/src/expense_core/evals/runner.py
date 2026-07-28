"""Golden-dataset regression eval runner (SCOPING §11.2).

Runs the category classifier and receipt parser over fixed JSONL golden datasets and
gates accuracy against ``thresholds.json``. Designed to run fully OFFLINE: it uses the
deterministic keyword fallback (classifier) and regex reconciliation (parser) via the
``LocalEchoProvider``, so there is no Azure/network dependency and results are reproducible
in CI. A model swap that silently regresses the deterministic paths (keyword maps,
reconciliation math) makes a metric drop below threshold and the process exits non-zero.

Dataset/threshold files live under ``core-engine/evals/`` (not in the wheel — they are
test fixtures). The directory is resolved from ``$EXPENSE_EVALS_DIR`` if set, else from a
few well-known locations relative to CWD and this file.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from expense_core.schemas.enums import Category
from expense_core.tools import classify_category, parse_receipt

# --------------------------------------------------------------------------- #
# Dataset / threshold location.
# --------------------------------------------------------------------------- #

def _evals_dir() -> Path:
    """Locate the ``evals/`` fixtures directory (datasets + thresholds.json)."""
    env = os.environ.get("EXPENSE_EVALS_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    # CWD-relative (CI runs `cd core-engine && python -m expense_core.evals`).
    candidates.append(Path.cwd() / "evals")
    candidates.append(Path.cwd() / "core-engine" / "evals")
    # Relative to this source file: src/expense_core/evals/ -> core-engine/evals.
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / "evals")
    for c in candidates:
        if (c / "thresholds.json").exists():
            return c
    raise FileNotFoundError(
        "Could not locate the evals/ fixtures directory. Set EXPENSE_EVALS_DIR or run "
        "from the core-engine/ directory. Tried: " + ", ".join(str(c) for c in candidates)
    )


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------------- #
# Metric containers.
# --------------------------------------------------------------------------- #
@dataclass
class CategoryMetrics:
    total: int
    correct: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    per_class: dict[str, dict[str, float]]
    failures: list[str] = field(default_factory=list)


@dataclass
class ReceiptMetrics:
    total: int
    total_match: float
    tax_match: float
    reconcile_accuracy: float
    failures: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Category eval.
# --------------------------------------------------------------------------- #
def evaluate_category(rows: list[dict]) -> CategoryMetrics:
    correct = 0
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    support: dict[str, int] = defaultdict(int)
    failures: list[str] = []

    for row in rows:
        expected = row["expected_category"]
        support[expected] += 1
        result = classify_category(row["description"], row["merchant"])
        predicted = result.category.value
        if predicted == expected:
            correct += 1
            tp[expected] += 1
        else:
            fp[predicted] += 1
            fn[expected] += 1
            failures.append(
                f"  merchant={row['merchant']!r} desc={row['description']!r}: "
                f"predicted {predicted!r}, expected {expected!r}"
            )

    classes = [c.value for c in Category]
    per_class: dict[str, dict[str, float]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    for cls in classes:
        p_denom = tp[cls] + fp[cls]
        r_denom = tp[cls] + fn[cls]
        precision = tp[cls] / p_denom if p_denom else 1.0
        recall = tp[cls] / r_denom if r_denom else 1.0
        per_class[cls] = {
            "support": float(support[cls]),
            "precision": precision,
            "recall": recall,
        }
        # Macro averages over classes that appear in the golden set (have support).
        if support[cls]:
            precisions.append(precision)
            recalls.append(recall)

    total = len(rows)
    return CategoryMetrics(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        macro_precision=sum(precisions) / len(precisions) if precisions else 0.0,
        macro_recall=sum(recalls) / len(recalls) if recalls else 0.0,
        per_class=per_class,
        failures=failures,
    )


# --------------------------------------------------------------------------- #
# Receipt eval.
# --------------------------------------------------------------------------- #
def evaluate_receipt(rows: list[dict]) -> ReceiptMetrics:
    total_ok = 0
    tax_ok = 0
    reconcile_ok = 0
    failures: list[str] = []

    for row in rows:
        result = parse_receipt(row["receipt_text"])
        exp_total = Decimal(str(row["expected_total"]))
        exp_tax = Decimal(str(row["expected_tax"]))
        exp_reconciles = bool(row["expected_reconciles"])

        t_match = result.total == exp_total
        x_match = result.tax == exp_tax
        r_match = result.reconciles == exp_reconciles
        total_ok += t_match
        tax_ok += x_match
        reconcile_ok += r_match

        if not (t_match and x_match and r_match):
            failures.append(
                f"  {row['receipt_text'][:50]!r}: "
                f"total {result.total} (exp {exp_total}), "
                f"tax {result.tax} (exp {exp_tax}), "
                f"reconciles {result.reconciles} (exp {exp_reconciles})"
            )

    n = len(rows)
    return ReceiptMetrics(
        total=n,
        total_match=total_ok / n if n else 0.0,
        tax_match=tax_ok / n if n else 0.0,
        reconcile_accuracy=reconcile_ok / n if n else 0.0,
        failures=failures,
    )


# --------------------------------------------------------------------------- #
# Report + gate.
# --------------------------------------------------------------------------- #
def run() -> int:
    """Run the full eval, print a report, and return a process exit code."""
    evals_dir = _evals_dir()
    thresholds = json.loads((evals_dir / "thresholds.json").read_text(encoding="utf-8"))

    cat_rows = _load_jsonl(evals_dir / "datasets" / "category_golden.jsonl")
    rec_rows = _load_jsonl(evals_dir / "datasets" / "receipt_golden.jsonl")

    cat = evaluate_category(cat_rows)
    rec = evaluate_receipt(rec_rows)

    scores = {
        "category_accuracy": cat.accuracy,
        "category_macro_recall": cat.macro_recall,
        "receipt_total_match": rec.total_match,
        "receipt_tax_match": rec.tax_match,
        "receipt_reconcile_accuracy": rec.reconcile_accuracy,
    }

    print("=" * 68)
    print("Golden-dataset regression eval (offline / deterministic path)")
    print("=" * 68)

    print(f"\nCategory classifier — {cat.correct}/{cat.total} correct")
    print(f"  accuracy        : {cat.accuracy:.3f}")
    print(f"  macro precision : {cat.macro_precision:.3f}")
    print(f"  macro recall    : {cat.macro_recall:.3f}")
    print("  per-class (support / precision / recall):")
    for cls, m in cat.per_class.items():
        print(
            f"    {cls:26} support={int(m['support']):>2}  "
            f"P={m['precision']:.2f}  R={m['recall']:.2f}"
        )
    if cat.failures:
        print("  failures:")
        print("\n".join(cat.failures))

    print(f"\nReceipt parser — {rec.total} cases")
    print(f"  total exact-match     : {rec.total_match:.3f}")
    print(f"  tax exact-match       : {rec.tax_match:.3f}")
    print(f"  reconcile-flag accuracy: {rec.reconcile_accuracy:.3f}")
    if rec.failures:
        print("  failures:")
        print("\n".join(rec.failures))

    print("\n" + "-" * 68)
    print(f"{'metric':32} {'score':>8} {'threshold':>10}  result")
    print("-" * 68)
    failed: list[str] = []
    for name, score in scores.items():
        threshold = thresholds.get(name)
        if threshold is None:
            continue
        passed = score >= threshold
        if not passed:
            failed.append(name)
        print(
            f"{name:32} {score:>8.3f} {threshold:>10.3f}  "
            f"{'PASS' if passed else 'FAIL'}"
        )
    print("-" * 68)

    if failed:
        print(f"\nREGRESSION GATE FAILED: {', '.join(failed)} below threshold.")
        return 1
    print("\nAll metrics meet thresholds. Regression gate passed.")
    return 0
