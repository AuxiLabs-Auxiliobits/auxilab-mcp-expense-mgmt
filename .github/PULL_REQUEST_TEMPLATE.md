<!--
Thanks for contributing. Keep this short — a good PR description explains why, and lets
the diff explain how.
-->

## What and why

<!-- What does this change, and what problem does it solve? Link the issue if there is one. -->

Closes #

## Type of change

- [ ] Bug fix (does not break existing behaviour)
- [ ] New feature (does not break existing behaviour)
- [ ] Breaking change (existing behaviour changes)
- [ ] Documentation
- [ ] Internal (refactor, tests, tooling, CI)

## How it was verified

<!--
Not "tests pass" — say what you actually exercised. If you fixed a parsing bug, which
receipt shapes did you try? If you touched the demo, did you run it?
-->

## Checklist

- [ ] `ruff format .` and `ruff check .` are clean
- [ ] `pytest` passes
- [ ] New behaviour has tests, including the failure cases
- [ ] Docs updated if behaviour or an interface changed
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`

## Project constraints

<!-- These are enforced by tests. Confirm your change respects them. -->

- [ ] `compliance_tools/` still depends only on `pydantic` — no database, MCP, Gradio or HTTP imports
- [ ] No network calls, credentials, cloud SDKs or `AZURE_*` variables in the published package
- [ ] Money is still `Decimal` everywhere it is money
- [ ] The MCP server still exposes exactly five tools
- [ ] If an LLM-assisted path changed, the deterministic fallback still works and is tested

## Anything else

<!--
Trade-offs you weighed, alternatives you rejected, things you are unsure about, or areas
you would especially like reviewed.
-->
