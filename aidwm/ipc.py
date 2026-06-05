from __future__ import annotations

import json
import logging
import socket
import threading
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

_BUFSIZE = 4096


class IpcServer:
    """Unix-socket IPC server embedded in the daemon.

    Accepts single-line JSON commands; sends single-line JSON responses.
    """

    def __init__(
        self, socket_path: Path, handler: Callable[[dict[str, object]], dict[str, object]]
    ) -> None:
        self._path = socket_path
        self._handler = handler
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._path.exists():
            self._path.unlink()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self._path))
        self._sock.listen(5)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="aidwm-ipc")
        self._thread.start()
        log.info("IPC server listening on %s", self._path)

    def stop(self) -> None:
        if self._sock:
            self._sock.close()
        if self._path.exists():
            self._path.unlink()

    def _accept_loop(self) -> None:
        assert self._sock
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        with conn:
            try:
                data = conn.recv(_BUFSIZE)
                command = json.loads(data.decode())
                response = self._handler(command)
                conn.sendall((json.dumps(response) + "\n").encode())
            except Exception:
                log.exception("IPC error")


def send_command(socket_path: Path, command: dict[str, object]) -> dict[str, object]:
    """Send a command to the daemon and return the response."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        sock.sendall((json.dumps(command) + "\n").encode())
        result: dict[str, object] = json.loads(sock.recv(_BUFSIZE).decode())
        return result
