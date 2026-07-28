# Golden-dataset regression evals

Regression gate for the **category classifier** and **receipt parser** (SCOPING §11.2:
"golden-dataset regression evals for classifier/parser in CI so a model swap can't
silently regress accuracy").

The eval runs **fully offline and deterministically** — it exercises the classifier's
keyword fallback and the parser's regex/reconciliation path via `LocalEchoProvider`, so
there is **no Azure or network dependency** and results are stable in CI. If a model or
the deterministic logic (keyword maps, reconciliation math) regresses, a metric drops
below its threshold and the process exits non-zero, failing the build.

## Layout

```
core-engine/
  evals/
    datasets/
      category_golden.jsonl   # >=25 cases: {description, merchant, expected_category}, all 8 categories
      receipt_golden.jsonl    # >=15 cases: {receipt_text, expected_total, expected_tax, expected_reconciles}
    thresholds.json           # per-metric regression gate thresholds
    README.md
  src/expense_core/evals/     # runner (importable + python -m entrypoint)
```

The datasets/thresholds are **test fixtures** and intentionally live under `evals/`, not
inside the installed wheel.

## Running

From the `core-engine/` directory:

```bash
python -m expense_core.evals
```

Exit code `0` = all metrics meet thresholds; non-zero = regression gate failed (with a
printed list of which metrics fell below threshold and which cases failed).

If you run from elsewhere, point the runner at the fixtures directory:

```bash
EXPENSE_EVALS_DIR=/path/to/core-engine/evals python -m expense_core.evals
```

## Metrics and thresholds

| metric                        | threshold | current deterministic score |
|-------------------------------|-----------|-----------------------------|
| `category_accuracy`           | 0.90      | 1.000                       |
| `category_macro_recall`       | 0.90      | 1.000                       |
| `receipt_total_match`         | 0.95      | 1.000                       |
| `receipt_tax_match`           | 0.95      | 1.000                       |
| `receipt_reconcile_accuracy`  | 0.95      | 1.000                       |

Thresholds sit just below the actual offline scores so the gate is a *real* gate (it
catches regressions in the keyword map / reconciliation math) but not flaky.

## Editing the golden sets

Expected values must match what the **deterministic offline path** actually produces, or
CI will be unstable. A couple of intentional edge cases capture the keyword map's
first-hit-wins quirks (e.g. a "dinner" description matches `inn` -> `Travel - Hotel`
before the meals keywords are reached; `wi-fi` outranks `office`). These exist so the
eval catches anyone reordering the keyword list. Add new cases by appending JSONL rows
and confirming `python -m expense_core.evals` still exits 0.
