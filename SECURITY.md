# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |
| < 1.0 | No — pre-release, not published |

Fixes land on the latest minor release. There are no long-term-support branches.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report it privately through
[GitHub Security Advisories](https://github.com/AuxiLabs-Auxiliobits/auxilab-mcp-expense-mgmt/security/advisories/new).
That opens a channel visible only to you and the maintainers, and lets us collaborate on a fix and
issue a CVE if warranted.

Helpful things to include, as far as you have them:

- What the issue is and roughly how severe you think it is
- Steps to reproduce, or a proof of concept
- Affected version, Python version, and operating system
- Anything you already know about a fix

## What to expect

| Stage | Target |
|---|---|
| Acknowledgement | 3 working days |
| Initial assessment | 7 working days |
| Fix or mitigation plan | 30 days for high severity; longer for complex low-severity issues |
| Public disclosure | After a fix ships, coordinated with you |

This is a volunteer-maintained project, not a commercial product with an on-call rota. Those targets
are honest intentions rather than a contractual SLA. If a report goes quiet for longer than the
targets above, a nudge on the advisory thread is welcome.

We will credit you in the advisory and the changelog unless you prefer otherwise.

## Responsible disclosure

We ask that you:

- Give us a reasonable chance to fix the issue before disclosing it publicly
- Avoid accessing, modifying or deleting data that is not yours
- Avoid degrading the service of anyone running this software

We commit that we will not pursue legal action against researchers who follow this policy in good
faith.

There is no bug bounty.

## Threat model

Understanding what this software *is* helps calibrate what counts as a vulnerability.

**It is a local developer tool.** It has no server, no user accounts, no authentication and no
network calls. It runs with the privileges of whoever starts it and stores data in a local SQLite
file. It is not multi-tenant and is not designed to be exposed to the internet.

**In scope**

- Anything that lets untrusted *input* — receipt text, a policy file, MCP tool arguments — read files
  it should not, execute code, or escape the optional `EXPENSE_RECEIPT_DIR` sandbox
- Incorrect compliance verdicts that could be induced deliberately, for example a crafted receipt
  that reconciles when it should not
- Dependency vulnerabilities that are reachable from this code
- Anything that leaks local data off the machine

**Out of scope**

- The demo having no authentication. It binds to `127.0.0.1` on purpose. Deliberately exposing it
  with `GRADIO_SERVER_NAME=0.0.0.0` and then reporting that it is unauthenticated is not a finding.
- `receipt_parser` reading a file the user themselves can already read, when
  `EXPENSE_RECEIPT_DIR` is not set. That is the documented default; the sandbox exists for when it
  matters. See [the README](README.md#a-note-on-file-access).
- Anything in [`enterprise/`](enterprise/). It is archived reference code, is not installed, not
  imported, and not part of the published package.
- Denial of service achieved by feeding the tool an enormous local file you own.

## Security practices in this project

These are enforced by tests, not just intended:

- **No network at all.** [`tests/test_offline_guarantee.py`](tests/test_offline_guarantee.py) parses
  the AST of every published file and fails the build if an HTTP client, a cloud SDK, an `AZURE_*`
  variable or an auth token appears.
- **No credentials anywhere.** There is nothing to leak — no keys, no tokens, no auth flow.
- **Input validation at every boundary.** All tool inputs are `pydantic` models with `extra="forbid"`.
- **Constrained file reads.** Only `.txt`, `.text`, `.md` and `.pdf`, refused above 10 MB, with the
  type checked before the file is opened.
- **Path traversal is handled by resolving first.** `EXPENSE_RECEIPT_DIR` containment is checked
  against the fully resolved path, so `../` cannot escape it.
- **Parameterised SQL only.** No string interpolation anywhere near the database.
- **No `eval`, `exec`, `pickle` or `yaml.load`.** Deserialisation is `json` and `pydantic` only.
- **The clock is not caller-controlled** through MCP, so a caller cannot decide whether its own
  expense is inside the claim window.
- **The demo binds to loopback** by default.

## Dependency policy

The published package has four direct runtime dependencies — `pydantic`, `mcp`, `gradio`, `pypdf`
— and only three if you skip the browser demo. All install from prebuilt wheels, so no build
toolchain runs on your machine. Keeping the list short is a deliberate security measure: a
dependency is a trust relationship, and most supply-chain risk arrives through transitive ones.

- **Dependabot** proposes dependency updates weekly and GitHub Actions updates monthly.
- Updates are merged after CI passes on Python 3.11, 3.12 and 3.13.
- Security updates are prioritised over feature updates.
- Actions are pinned to major versions and reviewed on update.
- New runtime dependencies need a clear justification in the pull request. "It would be convenient"
  is not one.

If you find a vulnerability in a dependency rather than in this code, report it upstream first, then
open an issue here so we can pin or patch.
