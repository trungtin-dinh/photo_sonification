from __future__ import annotations

import os
import sys
import time
import socket
import threading
from pathlib import Path


def _resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path


def _find_free_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found between 8501 and 8599.")


def _start_streamlit(app_path: Path, port: int) -> None:
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]

    stcli.main()


def main() -> int:
    app_path = _resource_path("app_local.py")
    if not app_path.exists():
        raise FileNotFoundError(f"Cannot find app_local.py at: {app_path}")

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(
        target=_start_streamlit,
        args=(app_path, port),
        daemon=True,
    )
    thread.start()

    time.sleep(2.0)

    import webview

    window = webview.create_window(
        title="Photo Sonification",
        url=url,
        width=1280,
        height=850,
        min_size=(1000, 700),
        text_select=True,
    )

    webview.start(gui="gtk", debug=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
