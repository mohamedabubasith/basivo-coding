#!/usr/bin/env python3
"""
start_app.py — Basivo one-file launcher for cloud servers
----------------------------------------------------------
Usage:
    python3 start_app.py                        # production, all automatic
    python3 start_app.py --domain example.com   # set CORS + display URL
    python3 start_app.py --port 9000            # custom port
    python3 start_app.py --dev                  # dev mode (hot-reload + vite)

Everything is handled automatically — no .env editing required:
    1. Checks Python / Node / npm / opencode
    2. Generates .env with secure random secrets (skips if already present)
    3. Creates .venv and installs requirements.txt
    4. Ensures PostgreSQL DB + user exist
    5. Runs Alembic migrations (alembic upgrade head)
    6. npm install + npm run build (production frontend)
    7. Starts uvicorn on 127.0.0.1 (expose via nginx)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).parent.resolve()
VENV        = ROOT / ".venv"
FRONTEND    = ROOT / "frontend"
DIST        = FRONTEND / "dist"
ENV_FILE    = ROOT / ".env"
PROJECTS_DIR= ROOT / "projects"

# ── Colours ───────────────────────────────────────────────────────────────────

CYAN  = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW= "\033[1;33m"
RED   = "\033[0;31m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def log(msg: str)  -> None: print(f"{CYAN}[basivo]{RESET} {msg}")
def ok(msg: str)   -> None: print(f"{GREEN}[basivo]{RESET} {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}[basivo]{RESET} {msg}")
def die(msg: str)  -> None: print(f"{RED}[basivo] ERROR:{RESET} {msg}", file=sys.stderr); sys.exit(1)

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd: list[str], *, cwd: Path = ROOT, env: dict | None = None,
        capture: bool = False) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd, cwd=str(cwd), env=merged_env,
        capture_output=capture, text=True,
    )
    if result.returncode != 0:
        if capture:
            print(result.stderr or result.stdout, file=sys.stderr)
        die(f"Command failed: {' '.join(cmd)}")
    return result


def python_in_venv() -> str:
    if platform.system() == "Windows":
        return str(VENV / "Scripts" / "python.exe")
    return str(VENV / "bin" / "python")


def pip_in_venv() -> str:
    if platform.system() == "Windows":
        return str(VENV / "Scripts" / "pip.exe")
    return str(VENV / "bin" / "pip")


def alembic_in_venv() -> str:
    if platform.system() == "Windows":
        return str(VENV / "Scripts" / "alembic.exe")
    return str(VENV / "bin" / "alembic")


def uvicorn_in_venv() -> str:
    if platform.system() == "Windows":
        return str(VENV / "Scripts" / "uvicorn.exe")
    return str(VENV / "bin" / "uvicorn")

# ── Step 1 — Prerequisite checks ─────────────────────────────────────────────

def check_prerequisites() -> None:
    log("Checking prerequisites…")

    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) < (3, 11):
        die(f"Python 3.11+ required, found {major}.{minor}")
    log(f"Python {major}.{minor} ✓")

    if not shutil.which("node"):
        die("Node.js not found — install: https://nodejs.org")
    node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
    log(f"Node {node_ver} ✓")

    if not shutil.which("npm"):
        die("npm not found — install Node.js: https://nodejs.org")
    npm_ver = subprocess.check_output(["npm", "--version"], text=True).strip()
    log(f"npm {npm_ver} ✓")

    if not shutil.which("opencode"):
        warn("opencode not found — AI workspace features will be unavailable")
    else:
        log("opencode ✓")

# ── Step 2 — Auto-generate .env (zero touch) ──────────────────────────────────

def ensure_env(domain: str | None) -> None:
    if ENV_FILE.exists():
        log(".env already present — skipping generation")
        return

    import secrets as _s
    jwt_key = _s.token_hex(32)

    try:
        from cryptography.fernet import Fernet
        fernet_key = Fernet.generate_key().decode()
    except ImportError:
        import base64
        fernet_key = base64.urlsafe_b64encode(os.urandom(32)).decode()

    if domain:
        scheme = "https" if not domain.startswith("http") else ""
        origin = f"{scheme}://{domain}" if scheme else domain
        cors = f'["{origin}"]'
    else:
        cors = '["*"]'

    ENV_FILE.write_text(f"""\
DEBUG=false
CORS_ORIGINS={cors}

DATABASE_URL=postgresql+asyncpg://basivo:basivo@localhost:5432/basivo

JWT_SECRET_KEY={jwt_key}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

ENCRYPTION_KEY={fernet_key}

RESET_TOKEN_EXPIRE_MINUTES=30

OPENCODE_BINARY=opencode
PROJECTS_ROOT={PROJECTS_DIR}
OPENCODE_TIMEOUT_SECONDS=300
""")
    ok(".env generated with secure random secrets")

# ── Step 3 — Python venv + dependencies ──────────────────────────────────────

def ensure_venv() -> None:
    if not VENV.exists():
        log("Creating Python virtual environment…")
        run([sys.executable, "-m", "venv", str(VENV)])

    log("Installing Python dependencies…")
    run([pip_in_venv(), "install", "--quiet", "--upgrade", "pip"])
    run([pip_in_venv(), "install", "--quiet", "-r", "requirements.txt"])
    ok("Python dependencies ready")

# ── Step 4 — PostgreSQL DB + user ────────────────────────────────────────────

def ensure_postgres() -> None:
    log("Checking PostgreSQL…")

    pg_isready = shutil.which("pg_isready")
    if pg_isready:
        r = subprocess.run([pg_isready, "-q"], capture_output=True)
        if r.returncode != 0:
            log("PostgreSQL not responding — attempting to start…")
            for cmd in (
                ["service", "postgresql", "start"],
                ["pg_ctlcluster", "16", "main", "start"],
                ["pg_ctlcluster", "15", "main", "start"],
                ["pg_ctl", "start", "-D", "/var/lib/postgresql/data"],
            ):
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, capture_output=True)
                    break
            import time; time.sleep(2)

            r = subprocess.run([pg_isready, "-q"], capture_output=True)
            if r.returncode != 0:
                die("PostgreSQL is not running — start it with: service postgresql start")

    ok("PostgreSQL running")
    _psql_exec("CREATE USER basivo WITH PASSWORD 'basivo';", ignore_errors=True)
    _psql_exec("CREATE DATABASE basivo OWNER basivo;",       ignore_errors=True)
    ok("Database 'basivo' ready")


def _psql_exec(sql: str, ignore_errors: bool = False) -> None:
    for psql_cmd in (
        ["sudo", "-u", "postgres", "psql", "-c", sql],
        ["psql", "-U", "postgres",          "-c", sql],
    ):
        if shutil.which(psql_cmd[0]):
            r = subprocess.run(psql_cmd, capture_output=True, text=True)
            if r.returncode == 0 or ignore_errors:
                return
    if not ignore_errors:
        warn("psql unavailable — make sure PostgreSQL is accessible")

# ── Step 5 — Alembic migrations ──────────────────────────────────────────────

def run_migrations() -> None:
    log("Running database migrations…")
    run(
        [alembic_in_venv(), "upgrade", "head"],
        env={"PYTHONPATH": str(ROOT)},
    )
    ok("Migrations applied")

# ── Step 6 — Frontend ────────────────────────────────────────────────────────

def ensure_frontend(dev_mode: bool) -> None:
    log("Setting up frontend…")

    if not (FRONTEND / "node_modules").exists():
        log("Installing npm dependencies (first run may take a minute)…")
        run(["npm", "install", "--prefer-offline"], cwd=FRONTEND)

    if not dev_mode:
        log("Building React frontend…")
        run(["npm", "run", "build"], cwd=FRONTEND)
        ok("Frontend built")

# ── Step 7 — Start servers ────────────────────────────────────────────────────

def start_production(host: str, port: int, domain: str | None) -> None:
    if not DIST.exists():
        die(f"{DIST} not found — frontend build failed")

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    display = f"https://{domain}" if domain else f"http://{host}:{port}"
    print(f"\n{BOLD}{GREEN}  ✓ Basivo is running{RESET}")
    print(f"  URL:    {CYAN}{display}{RESET}")
    print(f"  API:    {CYAN}{display}/api/docs{RESET}")
    print(f"  Health: {CYAN}{display}/health{RESET}")
    print(f"\n  Press Ctrl+C to stop\n")

    os.execv(uvicorn_in_venv(), [
        uvicorn_in_venv(),
        "app.main:app",
        "--host", host,
        "--port", str(port),
        "--workers", "1",
        "--log-level", "info",
    ])


def start_dev(host: str, port: int) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{BOLD}{GREEN}  ✓ Basivo — dev mode{RESET}")
    print(f"  Backend:  {CYAN}http://{host}:{port}/api/docs{RESET}")
    print(f"  Frontend: {CYAN}http://localhost:5173{RESET}")
    print(f"\n  Press Ctrl+C to stop\n")

    backend = subprocess.Popen([
        uvicorn_in_venv(), "app.main:app",
        "--host", host, "--port", str(port),
        "--reload", "--log-level", "info",
    ], cwd=str(ROOT))

    vite = subprocess.Popen(["npm", "run", "dev"], cwd=str(FRONTEND))

    def _stop(sig, frame):
        log("Stopping…")
        backend.terminate()
        vite.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    backend.wait()
    vite.wait()

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Basivo launcher — no config needed")
    parser.add_argument("--dev",    action="store_true",
                        help="Development mode (hot-reload + vite dev server)")
    parser.add_argument("--domain", default=None,
                        help="Your domain, e.g. example.com — sets CORS and display URL")
    parser.add_argument("--host",   default="127.0.0.1",
                        help="Bind host (default: 127.0.0.1, exposed via nginx)")
    parser.add_argument("--port",   type=int, default=8000,
                        help="Bind port (default: 8000)")
    args = parser.parse_args()

    print(f"\n{BOLD}  Basivo — AI Coding Platform{RESET}")
    print(f"  {'development' if args.dev else 'production'} mode\n")

    check_prerequisites()
    ensure_env(args.domain)
    ensure_venv()
    ensure_postgres()
    run_migrations()
    ensure_frontend(dev_mode=args.dev)

    if args.dev:
        start_dev(args.host, args.port)
    else:
        start_production(args.host, args.port, args.domain)


if __name__ == "__main__":
    main()
