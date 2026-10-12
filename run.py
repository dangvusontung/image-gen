"""Start backend and frontend together: python3 run.py (Windows: py run.py)."""
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check installation without starting servers")
    args = parser.parse_args()
    python = ROOT / "backend/venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if not python.exists() or not npm or not (ROOT / "frontend/node_modules").exists() or not (ROOT / ".env").exists():
        raise SystemExit("Run setup.py first: python3 setup.py (Windows: py setup.py)")
    if args.check:
        print("Installation found. Ready to start.")
        return
    for port in (8000, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is already in use. Stop the existing app before running this launcher.") from None
    print("Applying database migrations…", flush=True)
    migrated = subprocess.run([str(python), "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend")
    if migrated.returncode:
        raise SystemExit("Database migration failed; servers were not started. Check the logs above.")
    processes = []
    group_options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
    try:
        processes.append(subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT / "backend", **group_options))
        processes.append(subprocess.Popen([npm, "run", "dev", "--", "--port", "5173", "--strictPort"], cwd=ROOT / "frontend", **group_options))
        print("Open http://127.0.0.1:5173 — press Ctrl+C to stop both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise SystemExit("A server exited; both servers have been stopped. Check the logs above.")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if sys.platform == "win32":
                if process.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
