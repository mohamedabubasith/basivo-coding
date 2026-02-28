#!/usr/bin/env bash
# ============================================================
#  start_project.sh — Basivo one-script project launcher
#  Usage:
#    chmod +x start_project.sh
#    ./start_project.sh             # production (docker compose up --build)
#    ./start_project.sh --dev       # dev mode   (docker compose -f docker-compose.dev.yml up --build)
#    ./start_project.sh --down      # stop and remove containers
#    ./start_project.sh --logs      # follow container logs
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
DOWN_MODE=false
LOGS_MODE=false

for arg in "$@"; do
  case $arg in
    --dev)   DEV_MODE=true ;;
    --down)  DOWN_MODE=true ;;
    --logs)  LOGS_MODE=true ;;
    -h|--help)
      echo "Usage: $0 [--dev] [--down] [--logs]"
      echo "  (no flag)  Build and start production containers"
      echo "  --dev      Build and start dev containers"
      echo "  --down     Stop and remove containers"
      echo "  --logs     Follow container logs"
      exit 0 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${BOLD}  Basivo — AI Coding Platform${RESET}"

# ── Prerequisite check ────────────────────────────────────────────────────────
log "Checking prerequisites…"

command -v docker >/dev/null 2>&1 || err "Docker not found. Please install Docker: https://docs.docker.com/get-docker/"

# Support both 'docker compose' (v2) and 'docker-compose' (v1)
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  err "Docker Compose not found. Please install it: https://docs.docker.com/compose/install/"
fi

ok "Docker & Compose ready (using: $COMPOSE)"

# ── Select compose file ───────────────────────────────────────────────────────
if [[ "$DEV_MODE" == "true" ]]; then
  COMPOSE_FILE="docker-compose.dev.yml"
  [[ -f "$COMPOSE_FILE" ]] || err "$COMPOSE_FILE not found."
  COMPOSE_CMD="$COMPOSE -f $COMPOSE_FILE"
  echo -e "  Mode: ${YELLOW}dev${RESET}\n"
else
  COMPOSE_FILE="docker-compose.yml"
  [[ -f "$COMPOSE_FILE" ]] || err "$COMPOSE_FILE not found."
  COMPOSE_CMD="$COMPOSE"
  echo -e "  Mode: ${GREEN}production${RESET}\n"
fi

# ── Run requested action ──────────────────────────────────────────────────────
if [[ "$DOWN_MODE" == "true" ]]; then
  log "Stopping containers…"
  $COMPOSE_CMD down
  ok "Containers stopped."
  exit 0
fi

if [[ "$LOGS_MODE" == "true" ]]; then
  log "Following logs (Ctrl+C to stop)…"
  $COMPOSE_CMD logs -f
  exit 0
fi

# ── Start ─────────────────────────────────────────────────────────────────────
log "Stopping any existing containers…"
$COMPOSE_CMD down 2>/dev/null || true

log "Building and starting containers…"
$COMPOSE_CMD up --build -d

echo -e "\n${BOLD}${GREEN}  ✓ Basivo is running${RESET}"
echo -e "  App:    ${CYAN}http://localhost:8080${RESET}"
echo -e "  API:    ${CYAN}http://localhost:8080/api/docs${RESET}"
echo -e "  Health: ${CYAN}http://localhost:8080/health${RESET}"
echo -e "\n  Logs:   ${BOLD}./start_project.sh --logs${RESET}"
echo -e "  Stop:   ${BOLD}./start_project.sh --down${RESET}\n"
