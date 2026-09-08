from __future__ import annotations

import asyncio
import importlib.metadata
import os
import signal
import subprocess
import sys
from enum import StrEnum
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from sentinel.cli.service import service_app
from sentinel.config import get_config
from sentinel.log import configure_logging

_STATE_DIR = Path.home() / ".local" / "state" / "macsentry"
_PID_FILE = _STATE_DIR / "serve.pid"
_LOG_DIR = Path.home() / "Library" / "Logs" / "macsentry"
_API_URL = "http://127.0.0.1:7173"


def _serve_pid() -> int | None:
    """Return PID of a running background serve process, or None."""
    if not _PID_FILE.exists():
        return None
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        _PID_FILE.unlink(missing_ok=True)
        return None


app = typer.Typer(
    name="macsentry",
    help="Local security and privacy monitor.",
    no_args_is_help=False,
    invoke_without_command=True,
)
scan_app = typer.Typer(help="Run security scans.")
baseline_app = typer.Typer(help="Manage baseline expectations.")

app.add_typer(scan_app, name="scan")
app.add_typer(baseline_app, name="baseline")
app.add_typer(service_app, name="service")

console = Console()
err_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    cfg = get_config()
    configure_logging(cfg.log_level)
    if ctx.invoked_subcommand is None:
        _launch_tui()


@app.command()
def version() -> None:
    """Show macsentry version."""
    v = "dev"
    for pkg in ("macsentry", "sentinel"):
        try:
            v = importlib.metadata.version(pkg)
            break
        except importlib.metadata.PackageNotFoundError:
            continue
    console.print(f"macsentry [bold]{v}[/bold]")


@app.command()
def doctor() -> None:
    """Check environment and tool availability."""
    import platform

    table = Table(title="Environment", box=box.SIMPLE_HEAD, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    # Python version
    py = sys.version.split()[0]
    py_ok = tuple(int(x) for x in py.split(".")[:2]) >= (3, 12)
    _add_row(table, "Python ≥ 3.12", py_ok, py)

    # psutil
    try:
        import psutil  # noqa: F401
        import psutil as _ps

        _add_row(table, "psutil", True, _ps.__version__)
    except ImportError:
        _add_row(table, "psutil", False, "not installed")

    # rich
    try:
        import importlib.metadata as _meta

        rich_ver = _meta.version("rich")
        _add_row(table, "rich", True, rich_ver)
    except Exception:
        _add_row(table, "rich", False, "not installed")

    # textual
    try:
        import importlib.metadata as _meta2

        textual_ver = _meta2.version("textual")
        _add_row(table, "textual", True, textual_ver)
    except Exception:
        _add_row(table, "textual", False, "not installed")

    # pydantic
    try:
        import pydantic  # noqa: F401

        _add_row(table, "pydantic", True, pydantic.__version__)
    except ImportError:
        _add_row(table, "pydantic", False, "not installed")

    # osquery (optional)
    import shutil

    osq = shutil.which("osqueryi") or shutil.which("osquery")
    _add_row(table, "osquery (optional)", osq is not None, osq or "not found")

    # fastapi / uvicorn (optional)
    try:
        import importlib.metadata as _fm

        fa_ver = _fm.version("fastapi")
        uv_ver = _fm.version("uvicorn")
        _add_row(table, "fastapi+uvicorn (optional)", True, f"{fa_ver} / {uv_ver}")
    except Exception:
        _add_row(
            table,
            "fastapi+uvicorn (optional)",
            False,
            "not installed — run: pip install 'sentinel[api]'",
        )

    # yara (optional)
    try:
        import importlib.metadata as _ym

        yara_ver = _ym.version("yara-python")
        _add_row(table, "yara-python (optional)", True, yara_ver)
    except Exception:
        _add_row(
            table,
            "yara-python (optional)",
            False,
            "not installed — deep scan uses rules without YARA",
        )

    # zeek (optional)
    import shutil as _shutil2

    zeek_bin = _shutil2.which("zeek") or _shutil2.which("bro")
    zeek_log = "/opt/zeek/logs/current/conn.log"
    import os as _os

    zeek_log_exists = _os.path.exists(zeek_log)
    zeek_detail = (
        f"binary: {zeek_bin}, log: {zeek_log}" if zeek_bin or zeek_log_exists else "not found"
    )
    _add_row(table, "zeek (optional)", zeek_bin is not None or zeek_log_exists, zeek_detail)

    # suricata (optional)
    suricata_bin = _shutil2.which("suricata")
    suricata_log = "/var/log/suricata/eve.json"
    suricata_log_exists = _os.path.exists(suricata_log)
    suricata_detail = (
        f"binary: {suricata_bin}, log: {suricata_log}"
        if suricata_bin or suricata_log_exists
        else "not found"
    )
    _add_row(
        table,
        "suricata (optional)",
        suricata_bin is not None or suricata_log_exists,
        suricata_detail,
    )

    # launchd service (macOS only)
    import subprocess

    launchd_label = "com.macsentry.agent"
    try:
        result = subprocess.run(
            ["launchctl", "list", launchd_label],
            capture_output=True,
            text=True,
            timeout=3,
        )
        launchd_loaded = result.returncode == 0
        launchd_detail = (
            "loaded" if launchd_loaded else "not loaded — run: macsentry service install"
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        launchd_loaded = False
        launchd_detail = "launchctl not available"
    _add_row(table, "launchd agent (optional)", launchd_loaded, launchd_detail)

    # platform
    _add_row(table, "Platform", True, platform.platform())

    console.print(table)


def _add_row(table: Table, name: str, ok: bool, detail: str) -> None:
    status = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
    table.add_row(name, status, detail)


# ── scan subcommands ────────────────────────────────────────────────────────


class ScanMode(StrEnum):
    quick = "quick"
    deep = "deep"


@scan_app.callback(invoke_without_command=True)
def scan_default(
    ctx: typer.Context,
    output_json: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Run a quick security scan (default)."""
    if ctx.invoked_subcommand is None:
        _run_scan(output_json=output_json)


@scan_app.command("quick")
def scan_quick(
    output_json: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Run a quick security scan."""
    _run_scan(output_json=output_json)


@scan_app.command("deep")
def scan_deep(
    output_json: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Run a deep security scan (hash integrity + YARA)."""
    from sentinel.application.deep_scan_service import DeepScanService
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector
    from sentinel.storage.database import get_engine, init_db

    engine = get_engine()
    init_db(engine)
    svc = DeepScanService(
        process_collector=PsutilProcessCollector(),
        network_collector=PsutilNetworkCollector(),
        engine=engine,
    )
    result = asyncio.run(svc.run())

    if output_json:
        import json

        data = {
            "process_count": result.quick.process_count,
            "listener_count": result.quick.listener_count,
            "connection_count": result.quick.connection_count,
            "finding_count": result.finding_count,
            "errors": result.errors,
        }
        print(json.dumps(data))
    else:
        from sentinel.cli.renderers.rich_renderer import render_scan_result

        render_scan_result(result.quick)
        if result.hash_findings:
            console.print(
                f"\n[bold yellow]Hash integrity findings: {len(result.hash_findings)}[/bold yellow]"
            )
            for f in result.hash_findings:
                console.print(f"  [red]●[/red] {f.subject}")
        if result.yara_findings:
            console.print(f"\n[bold red]YARA matches: {len(result.yara_findings)}[/bold red]")
            for f in result.yara_findings:
                for r in f.reasons:
                    console.print(f"  [red]![/red] {f.subject}: {r.description}")
        if result.errors:
            for err in result.errors:
                console.print(f"[yellow]⚠  {err}[/yellow]")


def _run_scan(output_json: bool = False) -> None:
    import time

    from sentinel.application.scan_service import QuickScanService
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector

    svc = QuickScanService(
        process_collector=PsutilProcessCollector(),
        network_collector=PsutilNetworkCollector(),
    )

    t0 = time.monotonic()
    result = asyncio.run(svc.run())
    duration = time.monotonic() - t0

    if output_json:
        from sentinel.cli.renderers.json_renderer import render_scan_result_json

        print(render_scan_result_json(result))
    else:
        from sentinel.cli.renderers.rich_renderer import render_scan_result

        render_scan_result(result, duration=duration)


# ── standalone subcommands ─────────────────────────────────────────────────


@app.command()
def processes() -> None:
    """List running processes."""
    from sentinel.application.correlation import CorrelationService
    from sentinel.cli.renderers.rich_renderer import render_processes_table
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector

    proc_obs = asyncio.run(PsutilProcessCollector().snapshot())
    sock_obs = asyncio.run(PsutilNetworkCollector().snapshot())
    correlated = CorrelationService().correlate(proc_obs, sock_obs)
    render_processes_table(correlated)


@app.command()
def ports() -> None:
    """List listening ports."""
    from sentinel.application.correlation import CorrelationService
    from sentinel.cli.renderers.rich_renderer import render_ports_table
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector

    proc_obs = asyncio.run(PsutilProcessCollector().snapshot())
    sock_obs = asyncio.run(PsutilNetworkCollector().snapshot())
    correlated = CorrelationService().correlate(proc_obs, sock_obs)
    render_ports_table(correlated)


@app.command()
def network() -> None:
    """List active connections."""
    from sentinel.application.correlation import CorrelationService
    from sentinel.cli.renderers.rich_renderer import render_network_table
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector

    proc_obs = asyncio.run(PsutilProcessCollector().snapshot())
    sock_obs = asyncio.run(PsutilNetworkCollector().snapshot())
    correlated = CorrelationService().correlate(proc_obs, sock_obs)
    render_network_table(correlated)


@app.command()
def inspect(
    query: str = typer.Argument(..., help="Port number, process name, or IP address to inspect."),
) -> None:
    """Deep-dive into a specific port, process name, or IP address."""
    from sentinel.application.scan_service import QuickScanService
    from sentinel.cli.renderers.rich_renderer import render_inspect
    from sentinel.collectors.network_psutil import PsutilNetworkCollector
    from sentinel.collectors.process_psutil import PsutilProcessCollector

    svc = QuickScanService(
        process_collector=PsutilProcessCollector(),
        network_collector=PsutilNetworkCollector(),
    )
    result = asyncio.run(svc.run())
    render_inspect(result, query)


@app.command()
def watch() -> None:
    """Launch the interactive TUI monitor."""
    _launch_tui()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address."),
    port: int = typer.Option(7173, "--port", "-p", help="Port number."),
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run in foreground (blocks; useful for dev/debugging)."
    ),
    reload: bool = typer.Option(
        False, "--reload", help="Enable hot-reload (implies --foreground)."
    ),
) -> None:
    """Start the MacSentry API server (runs in background by default)."""
    if foreground or reload:
        _serve_foreground(host, port, reload)
    else:
        _serve_background(host, port)


def _serve_foreground(host: str, port: int, reload: bool = False) -> None:
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]uvicorn is required for the API server.[/bold red]\n"
            "Install with:  [bold]pip install 'macsentry[api]'[/bold]"
        )
        raise typer.Exit(1) from None

    console.print(f"[green]MacSentry API starting on http://{host}:{port}[/green]")
    uvicorn.run("sentinel.api.app:app", host=host, port=port, reload=reload, log_level="warning")


def _serve_background(host: str, port: int) -> None:
    try:
        import uvicorn as _uv  # noqa: F401
    except ImportError:
        console.print(
            "[bold red]uvicorn is required for the API server.[/bold red]\n"
            "Install with:  [bold]pip install 'macsentry[api]'[/bold]"
        )
        raise typer.Exit(1) from None

    existing = _serve_pid()
    if existing:
        console.print(
            f"[yellow]MacSentry API is already running[/yellow] [dim](PID {existing})[/dim]"
        )
        console.print(f"  API  [dim]{_API_URL}/health[/dim]")
        return

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_out = _LOG_DIR / "macsentry.log"
    log_err = _LOG_DIR / "macsentry.err.log"

    with open(log_out, "a") as out, open(log_err, "a") as err:
        proc = subprocess.Popen(
            [sys.argv[0], "serve", "--foreground", "--host", host, "--port", str(port)],
            stdout=out,
            stderr=err,
            start_new_session=True,
        )

    _PID_FILE.write_text(str(proc.pid))
    console.print(f"[green]MacSentry API started[/green] [dim](PID {proc.pid})[/dim]")
    console.print(f"  API   [dim]{_API_URL}/health[/dim]")
    console.print(f"  Logs  [dim]{log_out}[/dim]")
    console.print("  Stop with:  [bold]macsentry stop[/bold]")


@app.command()
def status() -> None:
    """Show whether the MacSentry API server is running."""
    pid = _serve_pid()

    if pid:
        console.print(f"  Service  [green]running[/green]  [dim](PID {pid})[/dim]")
    else:
        # Fall back to checking the launchd service
        import subprocess as _sp

        from sentinel.cli.service import LABEL as _SVC_LABEL

        r = _sp.run(["launchctl", "list", _SVC_LABEL], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            console.print("  Service  [green]running[/green]  [dim](via launchd)[/dim]")
        else:
            console.print("  Service  [red]stopped[/red]")
            console.print("  Start with:  [bold]macsentry serve[/bold]")

    try:
        import urllib.request

        req = urllib.request.urlopen(f"{_API_URL}/health", timeout=2)
        body = req.read().decode()
        console.print(f"  API      [green]reachable[/green]  [dim]{body.strip()[:60]}[/dim]")
    except Exception:
        console.print(f"  API      [dim]not reachable at {_API_URL}/health[/dim]")

    console.print(f"  Logs     [dim]{_LOG_DIR}/macsentry.log[/dim]")


@app.command()
def stop() -> None:
    """Stop the background MacSentry API server."""
    pid = _serve_pid()
    if pid is None:
        console.print("[dim]No background serve process found.[/dim]")
        console.print("If running as a launchd service, use:  [bold]macsentry service stop[/bold]")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        console.print(f"[green]MacSentry API stopped[/green] [dim](PID {pid})[/dim]")
    except ProcessLookupError:
        _PID_FILE.unlink(missing_ok=True)
        console.print("[dim]Process was not running — cleaned up stale PID file.[/dim]")
    except PermissionError:
        console.print(f"[red]Permission denied stopping PID {pid}.[/red]")
        raise typer.Exit(1) from None


@app.command(name="help")
def help_cmd(ctx: typer.Context) -> None:
    """Show this help message."""
    typer.echo(ctx.parent.get_help() if ctx.parent else ctx.get_help())


# ── baseline subcommands ───────────────────────────────────────────────────


@baseline_app.command("list")
def baseline_list() -> None:
    """Show all baseline entries."""
    from sentinel.application.baseline_service import BaselineService
    from sentinel.storage.baseline_repository import BaselineRepository
    from sentinel.storage.database import get_engine, init_db

    engine = get_engine()
    init_db(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        svc = BaselineService(BaselineRepository(session))
        entries = svc.list_all()

    if not entries:
        console.print("[dim]No baseline entries. Use 'sentinel baseline add' to add one.[/dim]")
        return

    table = Table(title="Baselines", box=box.SIMPLE_HEAD, header_style="bold cyan")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Type")
    table.add_column("Subject")
    table.add_column("Reason")
    for e in entries:
        table.add_row(str(e.id), e.subject_type, e.subject, e.reason or "—")
    console.print(table)


@baseline_app.command("add")
def baseline_add(
    process: str | None = typer.Option(None, "--process", "-p", help="Process name to allow."),
    port: int | None = typer.Option(None, "--port", help="Port number to allow."),
    domain: str | None = typer.Option(None, "--domain", "-d", help="Domain to allow."),
    reason: str = typer.Option("", "--reason", "-r", help="Why this is expected."),
) -> None:
    """Add a process, port, or domain to the baseline."""
    from sqlalchemy.orm import Session

    from sentinel.application.baseline_service import BaselineService
    from sentinel.storage.baseline_repository import BaselineRepository
    from sentinel.storage.database import get_engine, init_db

    if not any([process, port, domain]):
        console.print("[red]Provide at least one of --process, --port, or --domain.[/red]")
        raise typer.Exit(1)

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        svc = BaselineService(BaselineRepository(session))
        if process:
            entry = svc.add_process(process, reason=reason)
            session.commit()
            console.print(f"[green]Added process baseline:[/green] {entry.subject} (id={entry.id})")
        if port is not None:
            entry = svc.add_port(port, reason=reason)
            session.commit()
            console.print(f"[green]Added port baseline:[/green] :{entry.subject} (id={entry.id})")
        if domain:
            entry = svc.add_domain(domain, reason=reason)
            session.commit()
            console.print(f"[green]Added domain baseline:[/green] {entry.subject} (id={entry.id})")


@baseline_app.command("remove")
def baseline_remove(
    entry_id: int = typer.Argument(..., help="Baseline entry ID (from 'baseline list')."),
) -> None:
    """Remove a baseline entry by ID."""
    from sqlalchemy.orm import Session

    from sentinel.application.baseline_service import BaselineService
    from sentinel.storage.baseline_repository import BaselineRepository
    from sentinel.storage.database import get_engine, init_db

    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        svc = BaselineService(BaselineRepository(session))
        removed = svc.remove(entry_id)
        if removed:
            session.commit()
            console.print(f"[green]Removed baseline entry {entry_id}.[/green]")
        else:
            console.print(f"[red]No baseline entry with id={entry_id}.[/red]")
            raise typer.Exit(1)


def _launch_tui() -> None:
    try:
        from sentinel.tui.app import SentinelApp
    except ImportError:
        console.print(
            "[bold red]The interactive TUI requires the [cyan]textual[/cyan] package.[/bold red]\n"
            "Install it with:  [bold]pip install 'sentinel[tui]'[/bold]"
        )
        raise SystemExit(1) from None

    SentinelApp().run()
