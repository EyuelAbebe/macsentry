# Installing Sentinel

**Requires:** macOS 14+, Python 3.12+

---

## Install from source (recommended for now)

Sentinel is not yet published to PyPI. Clone the repo and install with [Poetry](https://python-poetry.org).

```bash
git clone https://github.com/EyuelAbebe/macsentry.git
cd macsentry
pip install poetry          # if you don't have Poetry yet
poetry install              # installs all runtime + dev dependencies
```

Run it:

```bash
poetry run sentinel doctor  # verify environment
poetry run sentinel scan    # one-shot security scan
poetry run sentinel         # open interactive TUI monitor
poetry run sentinel serve   # start HTTP API + browser dashboard on :7173
```

To avoid typing `poetry run` each time, activate the virtual environment:

```bash
source .venv/bin/activate
sentinel doctor
```

---

## Install from PyPI (once published)

When Sentinel is released to PyPI, you'll be able to install it with [pipx](https://pipx.pypa.io):

```bash
brew install pipx
pipx ensurepath

# CLI + interactive TUI (recommended)
pipx install "macsentry[tui]"

# CLI only (no interactive monitor)
pipx install macsentry
```

Or with pip into a virtual environment:

```bash
python3 -m venv ~/.venvs/macsentry
source ~/.venvs/macsentry/bin/activate
pip install "macsentry[tui]"
```

---

## Upgrading (source install)

```bash
git pull origin main
poetry install
sentinel version
```

---

## Run automatically on login (background service)

Sentinel ships a launchd agent that starts the local API server (`sentinel serve`) automatically when you log in. The API powers the browser dashboard at `http://127.0.0.1:7173`.

### Quick install

Requires the `api` extra:

```bash
poetry install --extras api   # or: pip install "macsentry[api]"
sentinel service install
```

That's it. The service is now running. Verify:

```bash
sentinel service status
```

### Service management commands

| Command | What it does |
|---|---|
| `sentinel service install` | Write plist, register with launchd, start at login |
| `sentinel service start` | Start the service now (must be installed first) |
| `sentinel service stop` | Stop the running service |
| `sentinel service restart` | Stop then start |
| `sentinel service status` | Show running state, PID, and API health |
| `sentinel service uninstall` | Stop service and remove the plist |

```bash
sentinel service status    # loaded? running? API reachable?
sentinel service stop      # stop without uninstalling
sentinel service start     # start again
sentinel service restart   # restart (e.g. after a config change)
sentinel service uninstall # remove from launchd entirely
```

Logs are written to `~/Library/Logs/macsentry/`:
- `sentinel.log` — stdout (server access logs)
- `sentinel.err.log` — stderr (errors and warnings)

### Verify it is running

```bash
sentinel service status
curl http://127.0.0.1:7173/health
sentinel doctor             # shows "launchd agent: OK"
```

---

## Manual / fallback shell scripts

If `sentinel` is not on your PATH (e.g. running directly from the Poetry virtualenv), the shell scripts in `packaging/` provide the same functionality:

```bash
bash packaging/install.sh    # install and start
bash packaging/uninstall.sh  # stop and remove
```

When `sentinel` is on your PATH, these scripts automatically delegate to `sentinel service install` / `sentinel service uninstall`.

---

## Troubleshooting

**`sentinel: command not found`**

Make sure the Poetry virtualenv is active (`source .venv/bin/activate`) or always prefix with `poetry run`.

**`sentinel service install` fails with "launchctl not found"**

This command requires macOS. On other platforms use `sentinel serve` directly or configure your own process supervisor.

**`sentinel doctor` reports partial network access**

Normal under macOS SIP. Sentinel shows your own processes and connections fully; system processes are partially visible. No action needed.

**`ModuleNotFoundError: textual`**

Install the `tui` extra: `poetry install` already includes it for source installs. For pip, reinstall with `pip install "macsentry[tui]"`.

**`ModuleNotFoundError: fastapi` or `uvicorn`**

Install the `api` extra: `poetry install --extras api` or `pip install "macsentry[api]"`.

**Service installed but API not reachable**

Check the error log: `cat ~/Library/Logs/sentinel/sentinel.err.log`. If uvicorn is missing, run `pip install "macsentry[api]"` then `sentinel service restart`.
