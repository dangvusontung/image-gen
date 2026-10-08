"""One-time local setup: python3 setup.py (Windows: py setup.py)."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check prerequisites without changing files")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit("Install Python 3.12 or newer, then run this script again.")
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    node = shutil.which("node")
    if not npm or not node:
        raise SystemExit("Install Node.js 24 (includes npm), then run this script again.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    parts = tuple(int(p) for p in version.lstrip("v").split(".")[:2])
    if not (parts >= (22, 12) or (parts[0] == 20 and parts >= (20, 19))):
        raise SystemExit("Node.js 20.19+ or 22.12+ is required. Node.js 24 is recommended.")
    print(f"Python {sys.version.split()[0]}, Node.js {version}: ready", flush=True)
    if args.check:
        return
    env_path = ROOT / ".env"
    if not env_path.exists():
        # Exclusive creation preserves an existing configuration and its keys.
        with env_path.open("x", encoding="utf-8") as output:
            output.write((ROOT / ".env.example").read_text(encoding="utf-8"))
        if sys.platform != "win32":
            env_path.chmod(0o600)
    backend = ROOT / "backend"
    venv_dir = backend / "venv"
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend, check=True)
    subprocess.run([str(python), "-m", "alembic", "upgrade", "head"], cwd=backend, check=True)
    subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True)
    print("Setup complete. Optional: add API keys to .env. Start with: python3 run.py (Windows: py run.py)")


if __name__ == "__main__":
    main()
