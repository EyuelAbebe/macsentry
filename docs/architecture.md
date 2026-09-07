# Architecture

Sentinel is built around a single principle: **one engine, many interfaces**. The CLI, TUI, and future GUI all call the same application services. There is no separate scanning logic for each interface.

---

## Component overview

```mermaid
flowchart TD
    subgraph IF["Interfaces"]
        CLI["CLI\nsentinel scan · ports · network"]
        TUI["TUI\nsentinel · sentinel watch"]
        GUI["GUI\n*(Phase 9)*"]
    end

    subgraph APP["Application Core"]
        QSS["QuickScanService"]
        CS["CorrelationService"]
        FE["FindingEngine"]
        SD["SnapshotDiffer"]
        EB["EventBus"]
        SR["CurrentStateRegistry"]
    end

    subgraph DOM["Domain Layer"]
        direction LR
        M1["ProcessIdentity\nSocketObservation\nNetworkEndpoint"]
        M2["Event\nFinding\nClassificationEvidence"]
    end

    subgraph COL["Collectors"]
        PC["PsutilProcessCollector"]
        NC["PsutilNetworkCollector"]
        BC["BrowserCollector\n*(Phase 8)*"]
    end

    subgraph ADP["Adapters — optional"]
        OQ["osquery *(Phase 7)*"]
        YX["YARA-X *(Phase 7)*"]
        TR["Tracker datasets *(Phase 5)*"]
        SZ["Suricata / Zeek *(Phase 10)*"]
    end

    DB[("SQLite\n~/.local/share/macsentry/\n*(Phase 4+)*")]

    IF -->|"in-process calls\n(Phase 0–8)"| APP
    GUI -. "HTTP / WebSocket\n*(Phase 9+)*" .-> APP
    APP -->|"snapshot()"| COL
    APP -->|"enrich()"| ADP
    COL & ADP --> DOM
    APP --> DOM
    APP -->|"persist events"| DB
```

`*` GUI technology decision deferred until the local API layer is proven (Phase 9 ADR).

---

## How a scan works

The sequence below shows exactly what happens when a user runs `sentinel scan`.

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant QSS as QuickScanService
    participant PC as PsutilProcessCollector
    participant NC as PsutilNetworkCollector
    participant CS as CorrelationService
    participant FE as FindingEngine
    participant R as RichRenderer

    User->>CLI: sentinel scan

    CLI->>QSS: run()

    par collect in parallel
        QSS->>PC: snapshot()
        PC-->>QSS: list[ProcessObservation]
    and
        QSS->>NC: snapshot()
        NC-->>QSS: list[SocketObservation]
    end

    QSS->>CS: correlate(processes, sockets)
    Note over CS: Links each socket to its<br/>owning process by PID
    CS-->>QSS: list[CorrelatedProcess]

    QSS->>FE: evaluate(correlated)
    Note over FE: Evaluates signals:<br/>all_interface_listener<br/>suspicious_location<br/>executable_missing
    FE-->>QSS: list[Finding]

    QSS-->>CLI: ScanResult

    CLI->>R: render(result)
    R-->>User: Formatted output
```

---

## Event pipeline (Phase 4+)

Once live monitoring is active, snapshots are diffed continuously. Only *changes* produce events — polling a stable listener 100 times does not create 100 events.

```mermaid
flowchart TD
    COL["Collector\nsnapshot()"]

    COL --> DIFF["SnapshotDiffer\ndiff against CurrentStateRegistry"]

    DIFF --> CHK{Changed?}

    CHK -->|"No change detected"| SKIP["Skip\nno duplicate events"]

    CHK -->|"Process appeared"| E1["PROCESS_STARTED"]
    CHK -->|"Process disappeared"| E2["PROCESS_STOPPED"]
    CHK -->|"Listener appeared"| E3["PORT_OPENED"]
    CHK -->|"Connection appeared"| E4["CONNECTION_OPENED"]
    CHK -->|"Listener removed"| E5["PORT_CLOSED"]
    CHK -->|"Connection dropped"| E6["CONNECTION_CLOSED"]

    E1 & E2 & E3 & E4 & E5 & E6 --> PERSIST["Persist Event\nto SQLite"]

    PERSIST --> UPDATE["Update\nCurrentStateRegistry"]

    UPDATE --> COR["CorrelationService\nProcess ↔ Socket"]
    COR --> CLASS["Classification\nDomain → Org → Category"]
    CLASS --> FIND["FindingEngine\nSignal evaluation"]

    FIND --> PUB["Publish to subscribers"]

    PUB --> TUI_OUT["TUI live update"]
    PUB --> REP["Report engine"]
    PUB --> WS["WebSocket\n*(Phase 9)*"]
```

---

## Layers in detail

### Domain — `src/sentinel/domain/`

The domain layer owns the data structures and vocabulary of the system. It has **zero dependencies** on collectors, storage, UI, or the network. Every other layer depends on it; it depends on nothing but Python and Pydantic.

| Type | Purpose |
|---|---|
| `ProcessIdentity` | A running process: pid, name, exe path, user, start time |
| `ProcessInstance` | A `ProcessIdentity` plus a stable `instance_id` (survives PID reuse) |
| `SocketObservation` | A socket: local endpoint, remote endpoint, state, exposure level |
| `NetworkEndpoint` | An address+port with optional hostname, org, and category |
| `Event` | A versioned, timestamped change event (`PROCESS_STARTED`, `PORT_OPENED`, …) |
| `Finding` | A human-readable security alert with reasons and evidence references |
| `ClassificationEvidence` | Identity/category evidence for a domain or IP from a specific source |

**PID reuse is handled correctly.** A process is identified by `(pid, start_time)`, not pid alone. The `instance_id` is a deterministic UUID5 derived from that pair so historical records stay valid even after an OS reuses a PID.

---

### Application — `src/sentinel/application/`

The application layer orchestrates the system. It reads from collectors, computes events, and produces findings. It has no UI dependency.

| Component | Responsibility |
|---|---|
| `QuickScanService` | Collects a snapshot, correlates process↔socket, runs the finding engine, returns a `ScanResult` |
| `CorrelationService` | Links each `SocketObservation` to its owning `ProcessObservation` by PID |
| `FindingEngine` | Evaluates independent signals against correlated data and produces `Finding` objects |
| `SnapshotDiffer` | Diffs two consecutive snapshots to produce a list of `Event` objects |
| `CurrentStateRegistry` | In-memory map of the latest observed processes and sockets |
| `EventBus` | In-process async pub/sub for domain events |

**Findings are signal-based, not score-based.** Every finding lists the specific signals that triggered it (e.g. `all_interface_listener`, `suspicious_location`). A severity is *derived* from those signals — never hard-coded in the UI.

---

### Collectors — `src/sentinel/collectors/`

Collectors implement two protocols defined in `base.py`:

```python
class ProcessCollector(Protocol):
    async def snapshot(self) -> list[ProcessObservation]: ...

class NetworkCollector(Protocol):
    async def snapshot(self) -> list[SocketObservation]: ...
```

Current implementations:

| Collector | Source | Notes |
|---|---|---|
| `PsutilProcessCollector` | `psutil.process_iter()` | Skips inaccessible processes gracefully |
| `PsutilNetworkCollector` | `psutil.net_connections()` | Falls back to empty list on `AccessDenied` |

Later implementations (native macOS Endpoint Security, osquery) will satisfy the same protocols without touching the application layer.

---

### Adapters — `src/sentinel/adapters/`

Optional integrations that enrich data without being required for core operation.

| Adapter | Phase | Purpose |
|---|---|---|
| osquery | 7 | Cross-verification, file hashes, launch agents, persistence |
| YARA-X | 7 | File-pattern malware scanning for selected executables |
| Tracker datasets | 5 | Domain → category classification (Analytics, Tracking, CDN, …) |
| Suricata | 10 | IDS/network threat signature enrichment |
| Zeek | 10 | Detailed network metadata and protocol analysis |

`sentinel doctor` reports the availability of each optional adapter.

---

### CLI — `src/sentinel/cli/`

Thin wrappers around application services using [Typer](https://typer.tiangolo.com) for command routing and [Rich](https://rich.readthedocs.io) for formatting. The CLI contains no business logic — it calls `QuickScanService`, passes the result to a renderer, and exits.

Two renderers:
- `RichRenderer` — tables, panels, colour, progressive disclosure
- `JsonRenderer` — clean JSON with no ANSI escape codes (`sentinel scan --json`)

---

### TUI — `src/sentinel/tui/`

An interactive terminal application built with [Textual](https://textual.textualize.io). It calls the same `QuickScanService` in-process and refreshes on a configurable interval.

| Screen | Contents |
|---|---|
| Overview | Summary counts, attention items, live activity log |
| Apps | Sortable process table with per-process detail panel |
| Network | Listeners table + connections table with exposure badges |
| Findings | Findings list with expandable reason detail |
| Help | Keyboard reference |

---

### Storage — `src/sentinel/storage/`

Introduced in **Phase 4**. SQLite in WAL mode via SQLAlchemy and Alembic. Separate logical repositories for current state, event history, findings, baselines, classification cache, and settings.

Default path: `~/.local/share/macsentry/macsentry.db`  
Override with: `MACSENTRY_DATA_DIR=/your/path`

---

## Dependency constraints

```mermaid
flowchart LR
    DOM["domain/\npydantic · stdlib only"]
    COL["collectors/\npsutil · macOS APIs"]
    APP["application/\norchestration"]
    CLI_L["cli/\ntyper · rich"]
    TUI_L["tui/\ntextual"]
    STR["storage/\nsqlalchemy · alembic"]

    DOM --> COL
    DOM --> APP
    DOM --> CLI_L
    DOM --> TUI_L
    DOM --> STR
    COL -->|"Protocol only"| APP
    APP --> CLI_L
    APP --> TUI_L
    APP --> STR
```

| Layer | May depend on | Must not depend on |
|---|---|---|
| `domain/` | `pydantic`, Python stdlib | Everything else |
| `application/` | `domain/`, `collectors/` (protocols) | `cli/`, `tui/`, `storage/` directly |
| `collectors/` | `domain/`, `psutil`, macOS APIs | `application/`, `cli/`, `tui/` |
| `cli/` | `application/`, `domain/`, `rich`, `typer` | `tui/` |
| `tui/` | `application/`, `domain/`, `textual` | `cli/` |
| `storage/` | `domain/`, `sqlalchemy`, `alembic` | `cli/`, `tui/` |
