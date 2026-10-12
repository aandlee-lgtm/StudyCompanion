"""Desktop launcher used by the packaged app (macOS .app / Windows .exe).

Keeps the data (database, backups, .env with an optional API key) in the user's
application-data folder so reinstalling or updating the app never touches it. Starts the
server on 127.0.0.1, opens Chrome (or the default browser) and shows a small window with
"Open" and "Quit" buttons. If another copy is already running it simply opens the browser."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "HSC Companion"
PREFERRED_PORT = 8000


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


def bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def prepare_environment() -> Path:
    data = Path(os.environ.get("HSC_DATA_DIR") or user_data_dir())
    data.mkdir(parents=True, exist_ok=True)
    os.environ["HSC_DATA_DIR"] = str(data)
    env_file = data / ".env"
    example = bundle_dir() / ".env.example"
    if not env_file.exists() and example.exists():
        text = example.read_text(encoding="utf-8").replace("HSC_DATA_DIR=./data", f"# Data folder: {data}")
        env_file.write_text(text, encoding="utf-8")
    return data


def ours_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return r.read().startswith(b"hsc-companion")
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def instance_file(data: Path) -> Path:
    return data / "instance.json"


def running_instance(data: Path) -> int | None:
    """Port of an HSC Companion already serving this data folder, if any."""
    import json

    try:
        port = int(json.loads(instance_file(data).read_text())["port"])
    except Exception:
        port = PREFERRED_PORT
    return port if ours_running(port) else None


def pick_port() -> int:
    for p in (PREFERRED_PORT, 8001, 8002, 8765):
        if port_free(p):
            return p
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def open_browser(url: str) -> None:
    """Prefer Google Chrome, as the app is designed for it; fall back to the default browser."""
    try:
        if sys.platform == "darwin" and Path("/Applications/Google Chrome.app").exists():
            subprocess.Popen(["open", "-a", "Google Chrome", url])
            return
        if os.name == "nt":
            for c in (os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                      os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                      os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")):
                if os.path.exists(c):
                    subprocess.Popen([c, url])
                    return
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        if chrome:
            subprocess.Popen([chrome, url])
            return
    except Exception:
        pass
    webbrowser.open(url)


def self_test() -> int:
    """Used by the build pipeline: create a database in a temp folder and render key pages.
    Results are also written to hsc-selftest.log in the working directory, because a
    windowed Windows executable has no console to print to."""
    import tempfile
    import traceback

    lines: list[str] = []

    def out(msg: str) -> None:
        lines.append(msg)
        if sys.stdout:
            print(msg, flush=True)

    ok = False
    tmp = tempfile.mkdtemp(prefix="hsc-selftest-")
    try:
        os.environ["HSC_DATA_DIR"] = tmp
        from fastapi.testclient import TestClient

        from app.config import config
        from app.db import get_engine
        from app.main import create_app

        config.data_dir = Path(tmp)
        with TestClient(create_app(f"sqlite:///{Path(tmp) / 'selftest.db'}")) as client:
            ok = client.get("/setup").status_code == 200 and client.get("/api/ping").text.startswith("hsc-companion")
            client.post("/setup", data={"student_name": "Test"})
            for path in ("/", "/curriculum", "/questions", "/progress", "/legal-evidence", "/settings", "/static/vendor/katex/katex.min.js"):
                code = client.get(path).status_code
                out(f"{path}: {code}")
                ok = ok and code == 200
        from app.services.maths_templates import generate

        from app.services import maths_templates as mt

        g = generate("1B", 1, 2)
        out(f"maths templates loaded: {len(mt.TEMPLATES)}; 1B generated: {g is not None}")
        if g is None:
            try:  # say why, so a packaging problem is visible in the build log
                fn = mt.TEMPLATES.get("1B")
                out(f"1B template: {fn}")
                if fn:
                    import random as _r
                    fn(_r.Random(1), 2)
            except Exception:
                out(traceback.format_exc())
        ok = ok and g is not None
        get_engine().dispose()  # release the SQLite file so Windows can delete the folder
    except Exception:
        out(traceback.format_exc())
        ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out("SELF-TEST " + ("PASSED" if ok else "FAILED"))
    try:
        Path("hsc-selftest.log").write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass
    return 0 if ok else 1


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    data = prepare_environment()
    existing = running_instance(data)
    if existing:  # already open: never run two servers on one database
        open_browser(f"http://127.0.0.1:{existing}")
        return
    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    import json

    instance_file(data).write_text(json.dumps({"port": port, "pid": os.getpid()}))

    import logging

    import uvicorn

    log_file = data / "hsc_companion.log"
    logging.basicConfig(filename=str(log_file), level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from app.main import create_app

    try:
        from app.services.backup import auto_backup

        auto_backup()  # daily safety copy before anything changes
    except Exception:
        logging.getLogger("hsc").exception("automatic backup failed")
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning", log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    if os.environ.get("HSC_HEADLESS"):  # used by the build smoke test: no browser, no window
        print(f"{APP_NAME} serving {url} (headless)", flush=True)
        thread.join()
        return
    open_browser(url)
    run_window(url, data, server)


def run_window(url: str, data: Path, server) -> None:
    try:
        import tkinter as tk
    except ImportError:  # no GUI toolkit: keep running until interrupted
        print(f"{APP_NAME} is running at {url}  (data: {data}). Press Ctrl+C to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.should_exit = True
        return

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("420x190")
    root.resizable(False, False)
    tk.Label(root, text=f"{APP_NAME} 2027 is running", font=("Helvetica", 15, "bold")).pack(pady=(18, 4))
    tk.Label(root, text=url, fg="#2f5d8a").pack()
    tk.Label(root, text="Keep this window open while you study.\nClosing it stops the app.", fg="#5d6470").pack(pady=6)
    row = tk.Frame(root)
    row.pack(pady=6)
    tk.Button(row, text="Open in browser", width=16, command=lambda: open_browser(url)).pack(side="left", padx=6)
    tk.Button(row, text="Data folder", width=12, command=lambda: reveal(data)).pack(side="left", padx=6)

    def quit_app():
        server.should_exit = True
        root.destroy()

    tk.Button(row, text="Quit", width=8, command=quit_app).pack(side="left", padx=6)
    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.mainloop()


def reveal(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


if __name__ == "__main__":
    main()
