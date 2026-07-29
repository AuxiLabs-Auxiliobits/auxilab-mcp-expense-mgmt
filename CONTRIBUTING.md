# Contributing

Thanks for taking a look. Issues and pull requests are both welcome — including
"the docs confused me", which is a real bug.

- [Development setup](#development-setup)
- [Running tests](#running-tests)
- [Code style](#code-style)
- [Four rules that matter](#four-rules-that-matter)
- [Adding or changing things](#adding-or-changing-things)
- [Commit conventions](#commit-conventions)
- [Pull request process](#pull-request-process)
- [Reporting issues](#reporting-issues)
- [Releasing](#releasing)

## Development setup

```bash
git clone https://github.com/AuxiLabs-Auxiliobits/auxilab-mcp-expense-mgmt.git
cd auxilab-mcp-expense-mgmt

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt
pytest
```

That is the whole setup. No account, no key, no `.env`, no service to start, no database to
migrate — the SQLite file creates and seeds itself on first use.

Supported Python versions are **3.11, 3.12 and 3.13**. CI runs all three.

## Running tests

```bash
pytest                              # everything
pytest tests/test_policy_checker.py # one module
pytest -k duplicate                 # by name
pytest --cov                        # with coverage (must stay at or above 90%)
pytest -x -vv                       # stop at the first failure, verbose
```

Every test runs against an isolated temporary database. Nothing touches
`local_db/sqlite.db`. Fixtures live in [tests/conftest.py](tests/conftest.py) — use `store`
for an empty one, `seeded_store` for the demo dataset, and `shared_store` when the code
under test resolves the database itself.

Some tests start the real Gradio server on a loopback port. If your firewall blocks that,
they will fail locally but pass in CI.

## Code style

[Ruff](https://docs.astral.sh/ruff/) handles both formatting and linting. There is no
separate formatter to configure.

```bash
ruff format .          # format
ruff check . --fix     # lint and auto-fix
ruff check .           # just check — this is what CI runs
```

Line length is 100. Rules are `E, F, I, UP, B, SIM, C4` — configured in
[pyproject.toml](pyproject.toml), not in your editor.

Beyond what the linter enforces:

- **Type hints on public functions.** Internal helpers can skip them where obvious.
- **Docstrings explain *why*.** The signature already says what. If a line of code needed
  a decision, record the decision.
- **Comments earn their place.** A comment restating the code is worse than no comment.

`enterprise/` is excluded from the style pass — it is archived reference code. It is still
checked for real defects with `make lint-enterprise`.

## Four rules that matter

These are enforced by tests, so you will find out quickly either way.
[ARCHITECTURE.md](ARCHITECTURE.md) explains the reasoning behind each.

**1. `compliance_tools/` depends on `pydantic` and nothing else.**
Not the database, not MCP, not Gradio, not an HTTP client. That constraint is what makes
the engine embeddable and what keeps the tests fast. If a tool needs data, take it as an
argument — see how `detect_duplicates` receives its history.

**2. Money is `Decimal`. Always.**
Never `float`. SQLite columns holding money are `TEXT`. A reconciliation system that
drifts by a cent is worse than no reconciliation system.

**3. The published package stays offline.**
No cloud SDK, no network client, no credential handling, no `AZURE_*` variable.
[tests/test_offline_guarantee.py](tests/test_offline_guarantee.py) parses the AST of every
shipped file and fails the build otherwise. The archived enterprise implementation lives in
`enterprise/` and stays there.

**4. A model may phrase things. It may not decide them.**
If you extend an LLM-assisted tool, validate the response and keep a deterministic
fallback. Look at `_parse_llm` in
[compliance_tools/category_classifier.py](compliance_tools/category_classifier.py): a
hallucinated category cannot escape the enum, and an unusable response falls through to
keyword matching. Adding a model should only ever improve results, never break
correctness.

## Adding or changing things

### A policy rule

Rules live in
[compliance_tools/baseline_policy.json](compliance_tools/baseline_policy.json) and are
validated by `BaselinePolicy`. Adding one means:

1. A field on `BaselinePolicy` in [compliance_tools/policy.py](compliance_tools/policy.py),
   defaulted so existing policy files keep loading.
2. A check in `check_policy` emitting a new violation code.
3. Tests for the rule firing, not firing, and its boundary.
4. A row in the README's violation-code table.

### An MCP tool

The server exposes exactly five, and
[tests/test_mcp_server.py](tests/test_mcp_server.py) asserts it. This is deliberate — the
project this was extracted from had 61, and the small surface is the feature. A sixth needs
a good argument in an issue first. Private helper functions are fine.

If you change a tool's signature: describe every parameter with `Field(description=...)`,
prefer typed models over `dict` so the schema is real, and never expose a clock override.

### The demo

Handlers in [app.py](app.py) must not import Gradio at module level — that is what lets
the demo fall back to the CLI when Gradio is unavailable, and what makes the handlers
directly testable. A test enforces it.

If you change anything visible, regenerate the screenshots:

```bash
pip install playwright pillow
python -m playwright install chromium
python docs/capture_screenshots.py
```

## Commit conventions

[Conventional Commits](https://www.conventionalcommits.org/). The prefix drives the
changelog and makes history skimmable.

```
feat(policy): add per-night hotel cap
fix(receipt): skip percentages when reading the tax line
docs(readme): document the EXPENSE_RECEIPT_DIR sandbox
test(duplicate): cover the near-match window boundary
chore(deps): bump pydantic to 2.13
refactor(store): sum money with Decimal instead of CAST
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`.
Common scopes: `policy`, `receipt`, `classifier`, `duplicate`, `report`, `mcp`, `db`,
`demo`, `cli`, `deps`.

Keep the subject imperative and under ~72 characters. Explain *why* in the body when it is
not obvious. Add `!` after the type for a breaking change (`feat(mcp)!: ...`).

## Pull request process

1. Fork, branch from `mcp-mavericks`, and give the branch a descriptive name.
2. Make the change, with tests.
3. Run `ruff format . && ruff check . && pytest`.
4. Add an entry under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
5. Open the PR and fill in the template.

What happens next:

- CI runs lint, format, the enterprise correctness gate, tests with coverage on three
  Python versions, a CLI smoke test, and a packaging check. All must pass.
- A maintainer reviews. Expect questions about *why* rather than style — the linter
  handles style.
- Small, focused PRs get reviewed faster than large ones. If a change is big, open an issue
  first so we can agree on the shape before you write it.

Review is a conversation, not a gate. If you disagree with a comment, say so — you may well
be right.

## Reporting issues

Use the [issue templates](https://github.com/AuxiLabs-Auxiliobits/auxilab-mcp-expense-mgmt/issues/new/choose).
There is one each for bugs, feature requests and questions.

For a bug, the single most useful thing is a short reproduction. These tools have no setup,
so that is usually five lines of Python.

**Security vulnerabilities do not go in issues.** Open a
[private advisory](https://github.com/AuxiLabs-Auxiliobits/auxilab-mcp-expense-mgmt/security/advisories/new)
instead — see [SECURITY.md](SECURITY.md) for the policy and the threat model.

## Releasing

For maintainers. The version lives in exactly one place:
`compliance_tools/__init__.py`, which hatch reads when building.

1. Bump `__version__` in [compliance_tools/\_\_init\_\_.py](compliance_tools/__init__.py).
2. Move `[Unreleased]` entries into a new dated section in [CHANGELOG.md](CHANGELOG.md).
3. `git tag v1.2.3 && git push origin v1.2.3`.

The [release workflow](.github/workflows/release.yml) refuses to build unless the tag, the
package version and the changelog all agree, then runs the full suite on three Python
versions, builds the sdist and wheel, verifies the wheel installs and reports the right
version, and publishes a GitHub release with that changelog section as the notes.

### Before a first PyPI release

Two things are deliberately deferred until someone actually publishes to an index:

1. **Enable the PyPI job.** It is written and commented at the foot of the release
   workflow. It needs a Trusted Publisher configured on PyPI for this repository — no API
   token is stored either way.
2. **Switch the README images to absolute URLs.** They are repository-relative today,
   because that renders on GitHub whatever branch you are on and survives forks. PyPI
   serves the README from package metadata with no repository behind it, so relative paths
   render as broken images there. Rewrite them to
   `https://raw.githubusercontent.com/<owner>/<repo>/<default-branch>/docs/images/…` as a
   release step, and update `test_readme_images_are_repository_relative` to match.

`docs/` is excluded from the sdist on purpose — 1.7 MB of screenshots has no business in a
source distribution. That is why the image question only arises for the rendered PyPI page.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be decent to
each other.
