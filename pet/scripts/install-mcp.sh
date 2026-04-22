#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PET_DIR="$(dirname "$SCRIPT_DIR")"
SERVER="$PET_DIR/mcp_server/server.py"
SIMULATOR_URL="${SIMULATOR_URL:-http://localhost:18080}"

if ! command -v claude &>/dev/null; then
  echo "error: 'claude' CLI not found — install Claude Code first" >&2
  exit 1
fi

if [[ ! -f "$SERVER" ]]; then
  echo "error: MCP server not found at $SERVER" >&2
  exit 1
fi

echo "Installing AI Pet MCP server into Claude Code..."
echo "  server : $SERVER"
echo "  sim URL: $SIMULATOR_URL"

claude mcp add ai-pet \
  --scope user \
  -e "SIMULATOR_URL=$SIMULATOR_URL" \
  -- python "$SERVER"

echo ""
echo "Done. Restart Claude Code, then verify with:"
echo "  claude mcp list"
echo ""
echo "To drive Pepper, open Claude Code and run:"
echo "  /loop You are Pepper, an AI pet in a 2D grid. Each round: check your status with pet_status, then decide what to do — move, speak, or change mood. Be curious and expressive."
