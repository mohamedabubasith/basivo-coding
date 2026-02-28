#!/usr/bin/env bash
# ============================================================
#  start_project.sh — Basivo one-script project launcher
#  Usage:
#    chmod +x start_project.sh
#    ./start_project.sh             # production (build frontend, serve all via uvicorn)
#    ./start_project.sh --dev       # dev mode   (backend + vite dev server separately)
#    ./start_project.sh --build-only  # just build the frontend, don't start servers
# ============================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[basivo]${RESET} $*"; }
ok()   { echo -e "${GREEN}[basivo]${RESET} $*"; }
warn() { echo -e "${YELLOW}[basivo]${RESET} $*"; }
err()  { echo -e "${RED}[basivo]${RESET} $*" >&2; exit 1; }

# ── Parse flags ───────────────────────────────────────────────────────────────
DEV_MODE=false
BUILD_ONLY=false
HOST="0.0.0.0"
PORT=8000

for arg in "$@"; do
  case $arg in
    --dev)        DEV_MODE=true ;;
    --build-only) BUILD_ONLY=true ;;
    --host=*)     HOST="${arg#*=}" ;;
    --port=*)     PORT="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 [--dev] [--build-only] [--host=0.0.0.0] [--port=8000]"
      exit 0 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${BOLD}  Basivo — AI Coding Platform${RESET}"
echo -e "  ${DEV_MODE:+dev mode}${DEV_MODE:-production mode}\n"

# ── Prerequisite checks ───────────────────────────────────────────────────────
log "Checking prerequisites…"

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || err "Required command not found: $1. Please install it."
}

check_cmd python3
check_cmd pip3
check_cmd node
check_cmd npm

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
NODE_VER=$(node --version | sed 's/v//')
log "Python $PYTHON_VER · Node $NODE_VER"

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" \
  || err "Python 3.11+ required (found $PYTHON_VER)"

# ── .env setup ────────────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  warn ".env not found — generating one with secure random secrets…"

  # Generate secrets via Python (always available)
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
               || python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

  cat > .env <<EOF
DEBUG=true
CORS_ORIGINS=["*"]

DATABASE_URL=postgresql+asyncpg://basivo:basivo@localhost:5432/basivo

JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

ENCRYPTION_KEY=${FERNET_KEY}

RESET_TOKEN_EXPIRE_MINUTES=30

OPENCODE_BINARY=opencode
PROJECTS_ROOT=${SCRIPT_DIR}/projects
OPENCODE_TIMEOUT_SECONDS=300

CREATE_TABLES=false
EOF

  ok ".env created — review it before going to production!"
else
  log "Using existing .env"
fi

# ── PostgreSQL ─────────────────────────────────────────────────────────────────
log "Checking PostgreSQL…"

# Try to start it if pg_isready fails
if ! pg_isready -q 2>/dev/null; then
  warn "PostgreSQL not responding — attempting to start…"
  if command -v service >/dev/null 2>&1; then
    service postgresql start 2>/dev/null || true
  elif command -v pg_ctlcluster >/dev/null 2>&1; then
    pg_ctlcluster 16 main start 2>/dev/null || true
  elif command -v pg_ctl >/dev/null 2>&1; then
    pg_ctl start -D /var/lib/postgresql/data 2>/dev/null || true
  fi
  sleep 2
fi

if pg_isready -q 2>/dev/null; then
  ok "PostgreSQL is running"
else
  err "PostgreSQL is not running. Start it manually: service postgresql start"
fi

# Create DB/user if they don't exist
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='basivo'" 2>/dev/null \
  | grep -q 1 || sudo -u postgres psql -c "CREATE USER basivo WITH PASSWORD 'basivo';" 2>/dev/null || true
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='basivo'" 2>/dev/null \
  | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE basivo OWNER basivo;" 2>/dev/null || true

# ── Python virtual environment ────────────────────────────────────────────────
log "Setting up Python environment…"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
  ok "Virtual environment created at .venv"
fi

# shellcheck source=/dev/null
source .venv/bin/activate

log "Installing Python dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Python dependencies installed"

# ── Database migrations ────────────────────────────────────────────────────────
log "Running database migrations…"

# Generate initial migration if versions/ is empty
VERSION_COUNT=$(find alembic/versions -name "*.py" ! -name "__init__.py" | wc -l)
if [[ "$VERSION_COUNT" -eq 0 ]]; then
  warn "No migrations found — generating initial schema…"
  PYTHONPATH="$SCRIPT_DIR" alembic revision --autogenerate -m "initial_schema" 2>/dev/null || true
fi

PYTHONPATH="$SCRIPT_DIR" alembic upgrade head
ok "Database migrations applied"

# ── Projects directory ────────────────────────────────────────────────────────
mkdir -p projects
ok "Projects root directory ready: $SCRIPT_DIR/projects"

# ── Frontend ──────────────────────────────────────────────────────────────────
log "Setting up frontend…"
cd frontend

if [[ ! -d "node_modules" ]]; then
  log "Installing npm dependencies (this may take a minute)…"
  npm install --prefer-offline 2>/dev/null || npm install
  ok "npm dependencies installed"
fi

if [[ "$BUILD_ONLY" == "true" ]]; then
  log "Building frontend…"
  npm run build
  ok "Frontend built at frontend/dist/"
  exit 0
fi

if [[ "$DEV_MODE" == "false" ]]; then
  log "Building frontend for production…"
  npm run build
  ok "Frontend built at frontend/dist/ — will be served by FastAPI"
fi

cd "$SCRIPT_DIR"

# ── Start servers ─────────────────────────────────────────────────────────────

if [[ "$DEV_MODE" == "true" ]]; then
  # ── DEV: run backend + vite separately ─────────────────────────────────────
  log "Starting backend (port $PORT) + Vite dev server (port 5173)…"

  # Kill any existing processes on these ports
  fuser -k ${PORT}/tcp 2>/dev/null || true
  fuser -k 5173/tcp 2>/dev/null || true

  # Start backend
  uvicorn app.main:app --host "$HOST" --port "$PORT" --reload \
    --log-level info &
  BACKEND_PID=$!

  # Start vite dev server
  cd frontend
  npm run dev &
  VITE_PID=$!
  cd "$SCRIPT_DIR"

  echo -e "\n${BOLD}${GREEN}  ✓ Basivo is running in development mode${RESET}"
  echo -e "  Backend API:  ${CYAN}http://localhost:${PORT}/api/docs${RESET}"
  echo -e "  Frontend:     ${CYAN}http://localhost:5173${RESET}"
  echo -e "  Health:       ${CYAN}http://localhost:${PORT}/health${RESET}"
  echo -e "\n  Press Ctrl+C to stop all services\n"

  # Trap Ctrl+C and kill both
  trap "kill $BACKEND_PID $VITE_PID 2>/dev/null; exit 0" SIGINT SIGTERM

  wait $BACKEND_PID $VITE_PID

else
  # ── PRODUCTION: serve everything from uvicorn ───────────────────────────────
  log "Starting production server on ${HOST}:${PORT}…"

  if [[ ! -d "frontend/dist" ]]; then
    err "frontend/dist not found. Run with --dev or ensure the build succeeded."
  fi

  fuser -k ${PORT}/tcp 2>/dev/null || true

  echo -e "\n${BOLD}${GREEN}  ✓ Basivo is running${RESET}"
  echo -e "  App:    ${CYAN}http://localhost:${PORT}${RESET}"
  echo -e "  API:    ${CYAN}http://localhost:${PORT}/api/docs${RESET}"
  echo -e "  Health: ${CYAN}http://localhost:${PORT}/health${RESET}"
  echo -e "\n  Press Ctrl+C to stop\n"

  exec uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    --log-level info
fi
