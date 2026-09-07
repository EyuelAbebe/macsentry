# Contributing to Sentinel

This guide covers everything you need to go from zero to a merged pull request.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| macOS | 14+ | — |
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) or `brew install python@3.12` |
| Poetry | latest | `pipx install poetry` |
| Git | any | pre-installed on macOS |
| GitHub CLI | latest | `brew install gh` then `gh auth login` |

---

## 1. Set up your development environment

```bash
# clone the repo
git clone https://github.com/EyuelAbebe/macsentry.git
cd macsentry

# install everything (runtime + TUI + dev tools)
poetry install

# verify the install
poetry run sentinel doctor
```

You should see all checks pass. If `psutil` reports partial network access, that is normal under macOS SIP — it does not affect development.

Run the test suite once to confirm your environment is healthy:

```bash
make test
```

---

## 2. Understand the project structure

```
src/sentinel/
  domain/         Pure data models and enums — no I/O, no framework imports
  application/    Business logic: scan, correlate, find — no UI code here
  collectors/     Reads live data via psutil
  cli/            Command-line interface (Typer + Rich)
  tui/            Interactive terminal UI (Textual)
  config.py       Configuration via environment variables (SENTINEL_*)
  log.py          Structured logging — always to stderr

tests/
  unit/           Fast tests using only fixtures (no real processes or sockets)
  integration/    Tests that bind real sockets — auto-skip under macOS SIP
```

**The key rule:** all scanning logic lives in `application/`. The `cli/` and `tui/` layers only call services and render results. If you find yourself adding an `if` statement about process behaviour inside a CLI command, move that logic to the application layer.

---

## 3. Pick up a task

- Check the current phase in `CLAUDE.md` (the **Phase state** table)
- Look at the build spec (`local_security_monitor_build_spec.md` in the parent directory) for the full requirements of the next phase
- For architecture-level changes, write an ADR first (`docs/decisions/ADR-XXXX-*.md`)

---

## 4. Create a branch

Branch names follow a consistent pattern:

| What you're doing | Branch name |
|---|---|
| New feature | `feature/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Documentation only | `docs/<short-description>` |
| Refactoring | `refactor/<short-description>` |

```bash
git checkout -b feature/live-monitor-polling
```

---

## 5. Make your changes

Keep commits small and focused — one logical change per commit. Commit messages are plain English:

```bash
# good
git commit -m "add polling loop to QuickScanService"
git commit -m "handle AccessDenied in live monitor gracefully"

# avoid
git commit -m "WIP"
git commit -m "fix stuff"
git commit -m "feat: add polling loop"   # no conventional commits prefix needed
```

Before pushing, run the full quality suite:

```bash
make fmt          # auto-fix formatting and lint
make lint         # verify ruff is clean (read-only)
make typecheck    # mypy strict — must pass
make test         # pytest — must pass
```

---

## 6. Open a pull request

```bash
git push origin feature/live-monitor-polling

gh pr create \
  --title "add live monitor polling loop" \
  --body "$(cat <<'EOF'
## Changes

- Added `LiveMonitorService` that polls `QuickScanService` on a configurable interval
- Emits `PROCESS_STARTED` / `PROCESS_STOPPED` events via `EventBus`
- Gracefully degrades when a collector raises `AccessDenied`

## Testing

- `tests/unit/test_live_monitor.py` — covers start/stop/pause behaviour
- `tests/integration/test_live_monitor_integration.py` — real process lifecycle
EOF
)"
```

**PR checklist before requesting review:**

- [ ] CI is passing (lint, mypy, pytest on 3.12 + 3.13)
- [ ] New logic in `application/` or `domain/` has unit tests
- [ ] New `FindingEngine` signals have both a happy-path test and a benign-case test
- [ ] No sensitive values are logged
- [ ] `sentinel scan --json 2>/dev/null` still produces clean JSON

---

## 7. After the PR is merged

Delete your branch:

```bash
git checkout main
git pull origin main
git branch -d feature/live-monitor-polling
```

---

## Common make targets

| Command | What it does |
|---|---|
| `make install` | `poetry install` |
| `make test` | `pytest` (all tests) |
| `make lint` | `ruff check + format --check` (read-only) |
| `make fmt` | `ruff check --fix + format` (auto-fix) |
| `make typecheck` | `mypy` strict mode |

---

## Architecture rules (must not be broken)

The codebase is structured in strict layers. Each layer may only import from layers below it:

```
cli/ and tui/          ← user-facing, renders results only
      │
application/           ← all business logic lives here
      │
collectors/            ← reads live data from the OS
      │
domain/                ← pure models, no I/O
```

- `cli/` must never import `tui/`, and vice versa
- `application/` must never import `cli/` or `tui/`
- `domain/` must never import anything outside stdlib

Violating these rules breaks the ability to add new interfaces (GUI, web API) without rewriting the core.

---

## Code style rules

**Datetime:** always use `datetime.now(UTC)` — never `datetime.utcnow()` (deprecated in Python 3.13).

**Error handling in collectors:**

```python
# correct
try:
    info = proc.info
except (psutil.AccessDenied, psutil.NoSuchProcess):
    continue   # or return []
```

**Logging:** use `sentinel.log.get_logger(__name__)`. Never log cookie values, auth headers, full URLs, or passwords at any level.

**Findings:** every `Finding` must have at least one `FindingReason`. The `FindingEngine` computes severity — the UI only reads it.

**JSON output:** `sentinel scan --json` must produce clean JSON. Test with `sentinel scan --json 2>/dev/null | python3 -m json.tool`.

---

## Writing tests

**Unit tests** go in `tests/unit/`. They use only fixtures — no real processes, no real network sockets.

**Integration tests** go in `tests/integration/`. They may bind real sockets. They must skip automatically when `psutil.net_connections()` raises `AccessDenied`:

```python
import pytest
import psutil

def _can_read_connections() -> bool:
    try:
        psutil.net_connections()
        return True
    except psutil.AccessDenied:
        return False

skip_if_no_access = pytest.mark.skipif(
    not _can_read_connections(),
    reason="psutil.net_connections() requires elevated access",
)
```

**Never** write tests that depend on public internet hosts. All tests must be runnable offline.

---

## Releases

Releases are handled by two manual GitHub Actions workflows. You do not create release tags by hand.

See [docs/release-process.md](release-process.md) for the full process.

---

## Getting help

- Architecture questions: read `docs/architecture.md` and the ADRs in `docs/decisions/`
- What to work on next: check the **Phase state** table in `CLAUDE.md`
- Build spec: `local_security_monitor_build_spec.md` in the parent directory
