from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="aidwm — AI desktop window manager")

_config_option = typer.Option(None, "--config", "-c", help="Path to config.toml")
_verbose_option = typer.Option(False, "--verbose", "-v", help="Enable debug logging")


@app.command()
def start(
    config: Optional[Path] = _config_option,
    verbose: bool = _verbose_option,
) -> None:
    """Start the aidwm daemon."""
    _configure_logging(verbose)

    from aidwm.backends.x11 import X11Backend
    from aidwm.config import Config
    from aidwm.engine import LayoutEngine
    from aidwm.ipc import IpcServer
    from aidwm.planner.heuristic import HeuristicPlanner

    cfg = Config.load(config)
    backend = X11Backend()
    planner = HeuristicPlanner()
    engine = LayoutEngine(backend, planner, cfg)

    ipc = IpcServer(cfg.socket_path_resolved(), handler=lambda cmd: _handle_ipc(cmd, engine, cfg, config))
    ipc.start()

    typer.echo(f"aidwm started. IPC socket: {cfg.socket_path_resolved()}")
    try:
        engine.run()   # blocks until backend stops
    except KeyboardInterrupt:
        typer.echo("Stopping.")
    finally:
        ipc.stop()
        backend.stop()


@app.command()
def reload(config: Optional[Path] = _config_option) -> None:
    """Signal the running daemon to reload its config."""
    from aidwm.config import Config
    from aidwm.ipc import send_command

    cfg = Config.load(config)
    sock = cfg.socket_path_resolved()
    if not sock.exists():
        typer.echo("aidwm is not running.", err=True)
        raise typer.Exit(1)
    response = send_command(sock, {"cmd": "reload"})
    typer.echo(response.get("message", "ok"))


@app.command()
def status(config: Optional[Path] = _config_option) -> None:
    """Show the daemon's current state."""
    from aidwm.config import Config
    from aidwm.ipc import send_command

    cfg = Config.load(config)
    sock = cfg.socket_path_resolved()
    if not sock.exists():
        typer.echo("aidwm is not running.")
        raise typer.Exit(1)
    response = send_command(sock, {"cmd": "status"})
    for key, value in response.items():
        typer.echo(f"{key}: {value}")


def _handle_ipc(command: dict, engine: object, cfg: object, config_path: Optional[Path]) -> dict:
    from aidwm.config import Config
    from aidwm.engine import LayoutEngine

    assert isinstance(engine, LayoutEngine)
    match command.get("cmd"):
        case "reload":
            new_cfg = Config.load(config_path)
            engine.reload_config(new_cfg)
            return {"status": "ok", "message": "Config reloaded"}
        case "status":
            return {
                "status": "running",
                "socket": str(cfg.socket_path_resolved() if hasattr(cfg, "socket_path_resolved") else "?"),  # type: ignore[union-attr]
            }
        case _:
            return {"status": "error", "message": f"Unknown command: {command.get('cmd')}"}


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )
