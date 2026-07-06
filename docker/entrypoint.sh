#!/bin/bash
# ──────────────────────────────────────────────────────────
# entrypoint.sh — Hello Agent Container Startup
# ──────────────────────────────────────────────────────────
set -e

# ── Colors for output ──────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}${BOLD}  🤖 Hello Agent — Starting Up  ${NC}"
echo -e "${CYAN}  ──────────────────────────────${NC}"

# ── Check required env vars ────────────────────────────
if [ -z "${GEMINI_API_KEY}" ] || [ "${GEMINI_API_KEY}" = "PASTE_YOUR_KEY_HERE" ] || [ "${GEMINI_API_KEY}" = "[GCP_API_KEY]" ]; then
  echo ""
  echo -e "${RED}  ✗ ERROR: GEMINI_API_KEY is not set!${NC}"
  echo ""
  echo -e "${YELLOW}  How to fix:${NC}"
  echo -e "  1. Get a free key at: ${BOLD}https://aistudio.google.com/apikey${NC}"
  echo -e "  2. Add it to your .env file:"
  echo -e "     ${BOLD}GEMINI_API_KEY=AIzaSy...your_key...${NC}"
  echo -e "  3. Run again: ${BOLD}make run${NC}"
  echo ""
  exit 1
fi

# ── Print config summary ───────────────────────────────
echo -e "${GREEN}  ✓ API Key      : ${NC}${GEMINI_API_KEY:0:12}... (set)"
echo -e "${GREEN}  ✓ Model        : ${NC}${LLM_MODEL:-gemini-2.0-flash}"
echo -e "${GREEN}  ✓ Agent Name   : ${NC}${AGENT_NAME:-Aria}"
echo -e "${GREEN}  ✓ Port         : ${NC}${API_PORT:-8000}"
echo ""

# ── Determine run mode ─────────────────────────────────
MODE="${RUN_MODE:-server}"   # default: web server

case "$MODE" in
  server)
    echo -e "${CYAN}  ▶ Mode: Web Server${NC}"
    echo -e "  Open → ${BOLD}http://localhost:${API_PORT:-8000}${NC}"
    echo ""
    exec python -m uvicorn api.server:app \
      --host "${API_HOST:-0.0.0.0}" \
      --port "${API_PORT:-8000}" \
      --log-level info
    ;;

  cli)
    echo -e "${CYAN}  ▶ Mode: CLI Chat${NC}"
    echo ""
    exec python main.py
    ;;

  message)
    # Non-interactive: run a single message and exit
    # Usage: docker run -e RUN_MODE=message -e AGENT_MESSAGE="..." hello-agent
    if [ -z "${AGENT_MESSAGE}" ]; then
      echo -e "${RED}  ✗ Set AGENT_MESSAGE env var to use message mode${NC}"
      exit 1
    fi
    echo -e "${CYAN}  ▶ Mode: Single Message${NC}"
    echo ""
    exec python main.py --message "${AGENT_MESSAGE}"
    ;;

  *)
    echo -e "${RED}  ✗ Unknown RUN_MODE: ${MODE}${NC}"
    echo -e "  Valid options: server | cli | message"
    exit 1
    ;;
esac
