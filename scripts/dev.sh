#!/bin/bash
# Development launcher — starts backend + frontend with live reload

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Pineapple Development ===${NC}"
echo ""
echo -e "  ${GREEN}Backend:${NC}  PYTHONPATH=src python3 -m pineapple dashboard (port 8765)"
echo -e "  ${GREEN}Frontend:${NC} npm run dev (port 5173, proxies /api to :8765)"
echo -e "  ${GREEN}Tests:${NC}    PYTHONPATH=src python3 tests/test_clone_detect.py"
echo ""

# Start backend in background with auto-restart
restart_backend() {
    echo -e "${GREEN}Starting backend...${NC}"
    cd "$PROJECT_DIR"
    while true; do
        PYTHONPATH=src python3 -m pineapple dashboard 2>&1 | while IFS= read -r line; do
            echo -e "${BLUE}[backend]${NC} $line"
        done
        echo -e "${BLUE}[backend]${NC} Restarting..."
        sleep 1
    done
}

# Start frontend
start_frontend() {
    echo -e "${GREEN}Starting frontend...${NC}"
    cd "$PROJECT_DIR/frontend"
    npm run dev 2>&1 | while IFS= read -r line; do
        echo -e "${GREEN}[frontend]${NC} $line"
    done
}

# Trap to kill both on Ctrl+C
trap 'kill 0' EXIT

# Start both
restart_backend &
BACKEND_PID=$!
sleep 2
start_frontend &
FRONTEND_PID=$!

wait
