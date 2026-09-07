# Changelog

All notable changes to Sentinel are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

**Background service management via CLI**
- `sentinel service install` — writes launchd plist to `~/Library/LaunchAgents/`, starts the API server at login automatically
- `sentinel service uninstall` — stops the service and removes the plist
- `sentinel service start` / `stop` / `restart` — control the running agent without reinstalling
- `sentinel service status` — shows loaded state, PID, API health check, and log path
- `packaging/install.sh` and `packaging/uninstall.sh` now delegate to the CLI when `sentinel` is on PATH (fall back to raw launchctl otherwise)
- `sentinel doctor` updated to reference `sentinel service install` instead of `bash packaging/install.sh`

**Collapsible process groups in TUI and browser dashboard**
- Apps screen: connections grouped under each process row; `→` expands, `←` collapses, `Enter` toggles; child rows show remote address, local endpoint, connection type, and socket state; detail panel shows process summary on header rows and individual connection detail on child rows
- Network screen: active connections grouped by process with same `→`/`←`/`Enter` expand-collapse; cursor position restored after re-render
- Browser Processes panel: click process row (or `▶`/`▼` toggle) to expand/collapse connections; child rows show local→remote, protocol, state
- Browser Network Connections panel: connections grouped by process name with click-to-expand; child rows show per-connection details

---

## [0.7.0] — 2026-08-31

### Added

**README: real screenshots replace ASCII art**
- 7 TUI tab screenshots (Overview, Apps, Network, Findings, Search, Users, Resources) captured from a live headless run
- 5 browser dashboard screenshots (Overview, Network, Processes, Findings, Activity) captured with Playwright
- `scripts/take_screenshots.py` and `scripts/capture_dashboard.py` for regenerating screenshots

### Fixed

**Browser dashboard: per-panel scrolling**
- Tables and content lists scroll inside their own panel instead of scrolling the whole page
- Network, Processes, Findings, and Activity panels grow to fill screen height and scroll independently

**TUI: search returns results for processes without open sockets**
- Searching by process name now shows a `PROC` row for any name/path match, not just processes with open ports

**TUI: arrow keys switch tabs without breaking search Input**
- Left/right arrow in the search input no longer accidentally switches tabs

**Network collection on macOS without root**
- `proc.net_connections()` pconn namedtuples are now wrapped with `.pid` so the correlator can join sockets to processes; the network tab was previously empty without root

**Browser dashboard: hot-reload without server restart**
- Dashboard HTML is read from disk on each request instead of being cached at startup

---

## [0.6.0] — 2026-08-31

### Changed

**TUI: horizontal split layouts across all screens**
- Overview: attention panel (left 60 %) and live activity log (right 40 %) are now visible
  side-by-side at the same time instead of stacking vertically
- Network: listening-ports table and active-connections table rendered side by side so both
  are visible simultaneously; detail panel remains at the bottom
- Apps: new `Conns` and `Status` columns — see active connection count and per-process risk
  badge (`CLEAN / SUSPECT / LISTENING / FLAGGED`) inline without opening the detail panel;
  path column smart-trims `/Applications/…` and `/Library/…` prefixes for readability
- Users: user table and detail panel are now side by side; detail panel shows a full
  annotated process list with port → exposure chain (`loop` / `local` / `all ⚠`),
  child-process markers, and connection counts per process; icon column shows user
  classification at a glance (root ⬛, macOS service ◆, you ●, user ◇)
- Resources: system metrics (CPU bars, RAM, Disk I/O, Network I/O) are on the left,
  top-processes table on the right — both visible simultaneously; per-core CPU bars now
  render 4 across for efficiency

**Network connections: remote endpoint classification**
- New `Type` column in the connections table: `loopback` (green), `local-net` (yellow),
  `external` (cyan) — instant visibility into whether a process is reaching out to the
  internet, a local device, or just talking to itself

**Overview: richer all-clear panel**
- When no findings, the attention pane now lists all checked signals and scan counts so the
  tab is informative even when everything is healthy

---

## [0.4.0] — 2026-08-29

### Added

**Search/Inspect tab (TUI)**
- New "5 Search" tab with real-time filtering by port number, process name, or IP address
- Results `DataTable` with columns Type / Port·Address / Process / State·Exposure
- Detail panel updates as cursor moves, showing full breakdown for listeners and connections
- Press `/` from any tab to jump to Search and focus the input field
- Press `5` to switch to the Search tab

**`sentinel inspect` CLI command**
- `sentinel inspect <query>` — runs a scan and deep-dives into a specific port, process, or IP
- Displays matching listeners as Rich panels with process, bind address, exposure, path, user, and command
- Displays matching connections as a table (local ↔ remote, state)
- Appends any related findings at the bottom so you see the full picture in one command

**CLI output legend**
- Severity legend printed after the summary table: `▲ LOW  ◆ MEDIUM  ● HIGH  ⬛ CRITICAL`
- "Attention = findings that need review" inline explanation

### Changed
- `KeyBar` hints on Search tab updated to show `1-5` tab range and `/` for search

---

## [0.3.0] — 2026-08-29

### Added

**Phase 4b — Live Monitor Service**
- `LiveMonitorService` — async background polling loop: collect → diff → persist events → emit via `EventBus`
- Optional SQLite persistence: pass `engine` to `LiveMonitorService` to store events and findings across restarts
- 9 unit tests covering lifecycle (start/stop/double-start), event emission, graceful degradation, and persistence

**Phase 4c — TUI Live Integration**
- TUI (`SentinelApp`) now creates and owns a `LiveMonitorService` with shared `EventBus`
- `on_mount()` starts the monitor; `on_unmount()` stops it cleanly
- Domain events streamed into the Overview screen's activity log via Textual's message-passing API
- Each event type has a labelled, colour-coded prefix (`[PROC]`, `[PORT]`, `[CONN]`, `[SITE]`)

**Phase 5 — Domain Classification Engine**
- `src/sentinel/adapters/tracker_lists.py` — 100+ entry offline domain database covering analytics, advertising, tracking, CDN, cloud API, and social categories
- `ClassificationService` — classifies any domain via subdomain hierarchy walking; returns `ClassificationEvidence` with source and confidence
- `known_tracker_connection` signal in `FindingEngine` — raises finding for connections to TRACKING or ADVERTISING domains
- `SITE_VISITED` and `THIRD_PARTY_REQUEST` events emitted by the classification layer

**Phase 6 — Baselines and Explainable Findings**
- `BaselineEntry` ORM model (unique by `subject_type` + `subject`)
- `BaselineRepository` — upsert, delete, query, find-by-subject
- `BaselineService` — `is_process_expected()`, `is_port_expected()`, `is_domain_expected()`, `add_*()`, `remove()`, `list_all()`
- `FindingEngine` respects baselines: baselined processes marked `EXPECTED`, baselined ports/domains suppress signals
- `sentinel baseline list / add / remove` CLI commands

**Phase 7 — Deep Scan with Hash Integrity and YARA**
- `HashCacheService` — SHA-256 with mtime-based cache invalidation in SQLite (`ExecutableHashRecord`)
- `YaraScanner` — optional yara-python adapter; graceful no-op if not installed; bundles 4 YARA rules: `SuspiciousTempExecutable`, `EicarTest`, `EncodedPayload`, `ReverseShell`
- `DeepScanService` — QuickScan + hash integrity check + YARA scan; returns `DeepScanResult`
- `sentinel scan deep` — runs deep scan with Rich output; hash and YARA findings displayed separately
- `sentinel doctor` — reports yara-python installation status

**Phase 8 — Browser Privacy Extension**
- Chrome MV3 + Firefox MV2 extension in `browser-extension/`
- Service worker (`background.js`) classifies every navigation via `GET /classify` on the local API
- Popup shows current site category badge, classification detail, and recent domain list
- Dark-themed UI (`popup.css`) with category-coloured badges (analytics, advertising, CDN, etc.)
- `README.md` covers load-unpacked instructions for both browsers

**Phase 9 — Local HTTP/WebSocket API**
- `src/sentinel/api/app.py` — FastAPI app: `GET /health`, `GET /classify`, `GET /scan`, `GET /findings`, `GET /baseline`, `WS /events`
- WebSocket `/events` streams live domain events from `EventBus` to any connected client
- CORS middleware allows all origins (localhost only by default)
- `sentinel serve [--host] [--port] [--reload]` CLI command
- `fastapi` and `uvicorn[standard]` added as optional `[api]` extras
- 7 unit tests via `FastAPI TestClient` (guarded with `pytest.importorskip`)

**Phase 10 — Zeek and Suricata Adapters**
- `ZeekAdapter` — tails Zeek `conn.log` TSV; emits `CONNECTION_OPENED` events; handles log rotation
- `SuricataAdapter` — tails Suricata `eve.json` NDJSON; emits `CONNECTION_OPENED` (flow) and `FINDING_CREATED` (alert) events; handles rotation
- Both expose `.available` and `.read_file()` for batch parsing and testing
- 28 unit tests (14 per adapter) covering parsing, edge cases, missing files, and availability
- `sentinel doctor` reports Zeek/Suricata binary presence and default log path existence

**Phase 11 — macOS Packaging and launchd Service**
- `packaging/com.sentinel.agent.plist` — launchd plist template; runs `sentinel serve` as a persistent user-level agent; auto-restarts on crash with 10 s throttle
- `packaging/install.sh` — resolves sentinel binary, substitutes plist placeholders, loads via `launchctl`, prints log path and health URL
- `packaging/uninstall.sh` — unloads running agent and removes plist
- `docs/installation.md` updated with one-command install instructions
- `sentinel doctor` checks whether `com.sentinel.agent` is loaded via `launchctl list`

---

## [0.2.0] — 2026-08-29

### Added

**Phase 4a — Storage Foundation**
- `src/sentinel/storage/` module: SQLite-backed persistence via SQLAlchemy 2 (WAL mode)
- `EventRecord` ORM model — stores domain events by type, instance ID, timestamp, and JSON payload
- `FindingRecord` ORM model — stores findings with severity, subject, reasons list, and status
- `EventRepository` — `write()`, `write_many()`, `query_recent()` (filterable by type/time), `count()`
- `FindingRepository` — `write()` (idempotent by `finding_id`), `write_many()`, `query_active()`, `query_all()`, `count_active()`
- `init_db()` — creates all tables from ORM metadata
- 13 unit tests in `tests/unit/test_storage.py` using in-memory SQLite
- `sqlalchemy>=2.0` and `alembic>=1.13` added as dependencies

**CLI output polish**
- Severity icons in finding panels: `●` HIGH, `◆` MEDIUM, `▲` LOW, `⬛` CRITICAL
- `Rule` separator lines replace plain bold text in scan output
- Finding reasons rendered as `rich.Text` with dim `›` bullet prefix
- Warnings changed from invisible `[dim]` to visible `[yellow]⚠ `
- Port numbers styled `bold cyan` in ports and processes tables
- Remote addresses styled `cyan`, local addresses `dim` in network table

**Documentation**
- `docs/installation.md` — pipx, pip+venv, upgrade, uninstall, launchd service, troubleshooting
- README: Mermaid pipeline diagram, terminal snapshots for `scan`/`ports`/`doctor`, cleaner layout
- GitHub Actions workflow display names improved: `CI — Lint, Test & Smoke`, `Release — Create RC`, `Release — Promote to Production`

**CI**
- CI workflow split into three focused jobs: `quality` (ruff + mypy), `test` (pytest on 3.12 + 3.13), `smoke` (install from wheel + all CLI commands)

**Developer tooling**
- `.claude/commands/` — project slash commands: `/project:update-changelog`, `/project:start-phase`, `/project:create-pr`
- `make smoke` — pre-PR local check: lint + tests + `sentinel scan`
- `make scan` — quick one-shot scan without launching TUI
- `make help` — lists all targets with descriptions
- Makefile uses `.venv/.installed` marker — skips reinstall unless `pyproject.toml`/`poetry.lock` changed
- `make install` calls `poetry env remove --all` before reinstalling to clear stale venv cache

---

## [0.1.0] — 2026-08-29

### Added

**Phase 0 — Bootstrap**
- Python project with `src/` layout, Poetry dependency management, and `poetry.lock`
- `sentinel --help` — command tree
- `sentinel version` — prints installed version from package metadata
- `sentinel doctor` — checks Python version, psutil, rich, textual, pydantic, and optional tools (osquery)
- Structured logging to stderr via Rich; never logs sensitive values
- `SentinelConfig` via Pydantic Settings (env: `SENTINEL_DATA_DIR`, `SENTINEL_LOG_LEVEL`, `SENTINEL_POLL_INTERVAL_SECONDS`)
- Ruff, mypy (strict), pytest, pre-commit configured
- Makefile with `install`, `lint`, `fmt`, `typecheck`, `test`, `bump-patch/minor/major` targets
- Architecture Decision Records: ADR-0001 through ADR-0005
- Initial documentation: README, architecture, privacy-model, threat-model, permissions

**Phase 1 — Domain Core**
- `ProcessIdentity` and `ProcessObservation` with PID-reuse-safe `instance_id` (UUID5 from pid+start_time)
- `NetworkEndpoint` with address, port, protocol, and optional identity/reputation fields
- `SocketObservation` with local/remote endpoints, socket state, and exposure classification
- `Event` model with versioned payload serialization (`payload_version = 1`)
- `Finding` and `FindingReason` with severity, status, reasons list, and evidence references
- `ClassificationEvidence` for domain/IP classification with source and confidence tracking
- Full enum set: `Severity`, `IdentityStatus`, `SecurityStatus`, `PrivacyCategory`, `ExposureLevel`, `SocketState`, `EventType`, `FindingStatus`, `Protocol`
- `CurrentStateRegistry` — in-memory process and socket state
- `SnapshotDiffer` — produces `PROCESS_STARTED/STOPPED`, `PORT_OPENED/CLOSED`, `CONNECTION_OPENED/CLOSED` events
- `EventBus` — in-process async pub/sub

**Phase 2 — Quick Scan**
- `PsutilProcessCollector` — collects all visible processes; skips `AccessDenied` / `NoSuchProcess` gracefully
- `PsutilNetworkCollector` — collects TCP/UDP connections; classifies exposure as `LOOPBACK`, `LOCAL_NETWORK`, or `ALL_INTERFACES`; falls back to empty list on `AccessDenied`
- `CorrelationService` — links socket observations to owning process by PID
- `FindingEngine` with signals: `all_interface_listener`, `local_network_listener`, `suspicious_location`, `executable_missing`
- `QuickScanService` — orchestrates collection, correlation, finding evaluation; returns `ScanResult`
- `sentinel scan` / `sentinel scan quick` — human-readable Rich output
- `sentinel scan --json` — machine-readable JSON (no ANSI codes)
- `sentinel processes` — process table
- `sentinel ports` — listening ports table with exposure badges
- `sentinel network` — active connections table

**Phase 3 — Interactive TUI**
- Textual-based TUI launched by `sentinel` or `sentinel watch`
- **Overview screen**: summary counts, needs-attention panel, live activity log
- **Apps screen**: sortable process table with per-process detail panel
- **Network screen**: listeners + connections tables with colour-coded exposure
- **Findings screen**: findings list with expandable reason detail
- **Help screen**: full keyboard reference
- Keyboard bindings: `s` rescan, `p` pause, `1–4` tab jump, `?` help, `q` quit
- Auto-refresh every 10 seconds; manual rescan with `s`

### Known limitations
- macOS SIP prevents `psutil.net_connections()` without elevated privileges; partial data for system processes
- Very short-lived processes (< poll interval) may not be detected

[Unreleased]: https://github.com/EyuelAbebe/macsentry/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/EyuelAbebe/macsentry/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/EyuelAbebe/macsentry/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/EyuelAbebe/macsentry/releases/tag/v0.1.0
