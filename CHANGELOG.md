# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Known limitations** section in the README: text-not-pixels parsing, English label matching,
  totals-keyword precedence, keyword-based classification, local-only duplicate detection,
  single-currency reconciliation, and the demo nature of the baseline policy.

## [1.1.0] — 2026-07-28

Architectural work on the two areas an independent audit flagged: the receipt parser's
design, and unrestricted filesystem access by default. The five tools, the MCP surface, the
CLI and the UI are unchanged.

### Changed

- **The receipt parser is now a pipeline rather than a stack of regexes.** Text is
  normalised, each line is classified exactly once, amounts are parsed in one place, and the
  result is assembled from the classified lines. Previously several independent regexes each
  scanned the whole document and could claim the same text — the cause of every parsing bug
  this project has had. See
  [ARCHITECTURE.md](ARCHITECTURE.md#how-the-receipt-parser-works).
- **Receipt file reads are sandboxed by default.** `receipt_parser`'s `file_path` is confined
  to the working directory unless `EXPENSE_RECEIPT_DIR` says otherwise; `EXPENSE_RECEIPT_DIR=*`
  restores the previous unrestricted behaviour. This is a deliberate behaviour change: the
  caller is usually a language model, and the previous default let a crafted call read any
  file the user could.
- **`app.py` split into `app.py` (interface) and `demo_handlers.py` (logic).** The handlers
  were already Gradio-free; they are now visibly so. `app.run_policy_checker` and friends
  still work — they are re-exported.
- The policy is loaded on first use rather than at import, in both the MCP server and the
  demo. A bad `EXPENSE_POLICY_PATH` now produces a clear error instead of an import failure.

### Added

- [`compliance_tools/money.py`](compliance_tools/money.py) — amount parsing across locale
  conventions: `1,234.56`, `1.234,56`, `1 234,56`, `1'234.56`, accounting negatives
  `(12.50)` and trailing-sign negatives `12.50-`. Returns `None` rather than zero for
  non-amounts, so a missing figure can never silently become a real one.
- [`compliance_tools/receipt_lines.py`](compliance_tools/receipt_lines.py) — line
  classification. `scan(text)` returns what the parser made of every line, which is now the
  fastest way to explain any parse.
- Multiple tax lines are summed, so a receipt with state and city tax reconciles.
- Tips, gratuities and service charges count toward the total instead of being discarded,
  so a receipt carrying one reconciles.
- Tab-separated and OCR-collapsed columns are recognised as purchases.
- 138 tests for the new modules, covering locale formats, OCR artefacts, unicode whitespace,
  and the false positives and negatives that caused earlier bugs.

### Fixed

- A purchase whose name merely contains a totals keyword is no longer discarded. `Postcard`
  matched "card", `Cardamom Tea` matched "card", `Taxi Receipt Book` matched "tax" — each
  vanished from the receipt, which then failed to reconcile with nothing to explain why.
- `2 nights @ $210` on a line by itself is no longer read as a `$210` charge; the quantity
  is applied during classification rather than in a fallback that never ran.
- Amounts written in European, French or Swiss conventions are no longer misread.

### Performance

Faster on every benchmark case despite the extra structure, because each line is now read
once instead of several times:

| Case | Before | After | Change |
|---|---|---|---|
| Single-line receipt | 0.064 ms | 0.046 ms | −27% |
| Typical printed receipt | 0.160 ms | 0.142 ms | −11% |
| Inline quantity pricing | 0.077 ms | 0.057 ms | −26% |
| 120-item receipt | 2.266 ms | 2.231 ms | −2% |
| Prose with no amounts | 0.256 ms | 0.113 ms | −56% |

## [1.0.0] — 2026-07-28

First public release.

This release extracts five expense-compliance tools from an Azure enterprise platform and turns them
into a standalone, offline, open-source tool. The enterprise implementation remains in the repository
under [`enterprise/`](enterprise/) but is fully isolated — see
[ARCHITECTURE.md](ARCHITECTURE.md#why-the-azure-code-is-isolated-rather-than-deleted).

### Added

- **Five compliance tools** in [`compliance_tools/`](compliance_tools/), depending only on `pydantic`:
  - **Policy Checker** — seven deterministic rules covering category caps, prohibited categories,
    receipt requirements, the claim window, and entered-amount-versus-receipt agreement.
  - **Receipt Parser** — extracts merchant, timestamp, tax, total and line items, then recomputes the
    arithmetic itself so a receipt that does not add up is always caught.
  - **Category Classifier** — assigns one of eight categories with a confidence score.
  - **Duplicate Detector** — screens against prior expenses via `EXACT_KEY`, `INTRA_SHEET` and
    `NEAR_MATCH_WINDOW` matching.
  - **Report Summariser** — per-category totals, violation count, amount at risk, compliance rate.
- **Local MCP server** ([`mcp_server.py`](mcp_server.py)) exposing exactly those five tools over
  stdio, with fully described and typed input schemas. `duplicate_detector` and `report_summariser`
  read local history so an agent does not have to carry state.
- **Browser demo** ([`app.py`](app.py)) — Gradio, one tab per tool, falls back to the terminal demo
  when Gradio is unavailable.
- **Terminal demo** ([`cli.py`](cli.py)) — exercises all five tools with no browser and no Gradio.
- **SQLite persistence** ([`local_db/`](local_db/)) on the standard library's `sqlite3`. Created,
  migrated and seeded on first use; no ORM, no migration framework, no committed binary.
- **Policy as data** — rules live in
  [`compliance_tools/baseline_policy.json`](compliance_tools/baseline_policy.json) and can be
  versioned in git and diffed in a pull request. `load_policy("my-policy.json")` to override.
- **Bring-your-own-model seam** — `LLMGateway` is a structural `Protocol`, so any object with a
  `complete()` method works. No provider SDK is shipped.
- **Sample documents** in [`demo/`](demo/) — receipt, policy and report as `.txt`/`.json` plus real
  PDFs, all reproducible via `python demo/generate_samples.py`.
- **320 tests** covering each tool's happy path, edge cases, degenerate input, and — for the
  LLM-assisted tools — unusable model responses. The receipt parser additionally has
  property-based tests ([hypothesis](https://hypothesis.readthedocs.io/)) generating receipt shapes,
  because it is the one component built on stacked regexes and generated input has caught defects
  the example tests did not.
- **Offline guarantee test** — parses the AST of every published file and fails the build if a cloud
  SDK, `AZURE_*` variable, auth token or HTTP client appears.
- **CI** across Python 3.11, 3.12 and 3.13: lint, format check, enterprise correctness gate, tests
  with coverage, CLI smoke test, and a packaging job that installs the wheel and imports it from
  outside the source tree.
- **Documentation** — [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md),
  [CONTRIBUTING.md](CONTRIBUTING.md), [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY.md](SECURITY.md),
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### Changed

- **MCP tool surface reduced from 61 to 5.** The other 56 were authenticated adapters over a REST
  backend and cannot function without it. A test now fails if the count changes.
- **Policy rules are enforced rather than declared.** The original ruleset carried six fields no code
  read; caps, receipt thresholds and the claim window are now evaluated.
- **Money is `Decimal` end to end**, stored in SQLite as `TEXT` and summed in Python. Totals are
  exact to the cent.
- **Runtime dependencies reduced to four** — `pydantic`, `mcp`, `gradio`, `pypdf`, and only three
  without the browser demo. All install from prebuilt wheels, so no compiler is required.
- **Enterprise code isolated** into `enterprise/`: not imported, not installed, not packaged, and
  excluded from the style lint while still gated for correctness.

### Removed

- All Azure SDK dependencies: `azure-identity`, `azure-storage-blob`, `azure-servicebus`,
  `azure-search-documents`, `azure-keyvault-secrets`, `azure-ai-documentintelligence`,
  `azure-ai-contentsafety`, `azure-core`, `msal`, `openai`.
- All web-stack dependencies from the published package: `fastapi`, `uvicorn`, `sqlalchemy`,
  `alembic`, `psycopg`, `langgraph`, `httpx`, `python-jose`, `passlib`, and the Node/Next.js tree.
- Authentication, RBAC and multi-tenant scoping — the standalone tool has no auth model because it
  has no server and no users.
- The root `.env.example`. The standalone tool has no required configuration; every option has a
  working default.
- Superseded material: the old root demo script, an HTTP client for the removed API, and a slide
  deck. The product specification and hardening notes were relocated to `enterprise/docs/`.

### Fixed

- **Tax extraction captured the rate, not the charge.** `Tax (8.625%)   3.88` yielded `8.625`,
  silently producing wrong reconciliation results. Percentages are now skipped.
- **Purchases were dropped when their name contained a totals keyword.** `Postcard` matched
  `card`, `Cardamom Tea` matched `card`, `Taxi Receipt Book` matched `tax` — the line vanished and
  the receipt then failed to reconcile with nothing to explain why. A totals row is now recognised
  only when the label starts the line *and* ends on a word boundary. Found by property-based tests.
- **A quantity description swallowed its list separator.** `2 nights @ $210, Tax $42` produced the
  description `2 nights @ $210,`.
- **Receipt timestamps lost their time component** when a receipt padded the gap between date and
  time (`2026-06-01  12:47`).
- **`stats()` summed money through `CAST(amount AS REAL)`**, reintroducing the float imprecision that
  storing money as `TEXT` exists to prevent.
- **The shared store silently returned a database at a different path** than the one requested.
- **Gradio startup crash** — `launch(show_api=...)` was removed in Gradio 6, so `python app.py`
  raised `TypeError`. Launch options are now restricted to parameters common to Gradio 5 and 6, and
  a test starts the real server to catch any recurrence.
- **Installed packages wrote their database into `site-packages`**, which may be read-only. Installed
  builds now use the platform's per-user data directory.
- **Editable installs shadowed the source.** Hatchling copied root modules into `site-packages`,
  so edits to `mcp_server.py` were silently ignored after `pip install -e .`.
- Handlers no longer fail with `AttributeError` when Gradio returns `None` for a cleared field.
- Six genuine defects in the archived enterprise code — unused imports and dead locals — found by a
  correctness-only lint pass.

### Security

- **Receipt file reads are constrained.** `receipt_parser` accepts only `.txt`, `.text`, `.md` and
  `.pdf`, refuses files over 10 MB, and rejects anything else before opening it.
- **Optional filesystem sandbox.** Setting `EXPENSE_RECEIPT_DIR` confines reads to one directory.
  Paths are resolved before the containment check, so `../` cannot escape it. Recommended when the
  MCP client is driven by a model you do not fully trust.
- **Upload size enforced at the HTTP layer** in the demo, so oversized files are rejected before
  being written to disk.
- **The clock cannot be overridden through MCP.** `check_policy` accepts an injectable `today` for
  testing; the tool does not expose it, so a caller cannot decide whether its own expense is
  future-dated or inside the claim window.
- **The demo binds to loopback only** and has no authentication by design.
- **No credentials anywhere.** No secrets, no tokens, no auth flow, and a test that fails the build
  if one appears.

[Unreleased]: https://github.com/Parteek-git2813/expense-management-mcp-server/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Parteek-git2813/expense-management-mcp-server/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Parteek-git2813/expense-management-mcp-server/releases/tag/v1.0.0
