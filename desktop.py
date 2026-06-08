"""Run Mandom as a native desktop app.

Same FastAPI web UI, just hosted inside a native OS window (via pywebview) instead
of a browser tab. The server runs on a private localhost port in a background
thread; nothing is exposed to the network.

    pip install -e ".[web,desktop]"
    python desktop.py

Package into a single double-click executable (no Python needed by the user)
with PyInstaller — see the README "Desktop app" section.
"""

from __future__ import annotations

import socket
import threading
import time

import uvicorn
import webview  # pywebview

# Import the app object directly (not via uvicorn's "module:app" string) so
# PyInstaller actually bundles the whole `app` package into the .exe.
from app.web.server import app as fastapi_app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_up(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    port = _free_port()
    config = uvicorn.Config(
        fastapi_app, host="127.0.0.1", port=port,
        log_level="warning", log_config=None,  # no console in --windowed builds
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_until_up(port)

    webview.create_window(
        "Mandom",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(940, 620),
    )
    webview.start()  # blocks until the window is closed

    # Window closed -> shut the server down.
    server.should_exit = True


if __name__ == "__main__":
    main()
