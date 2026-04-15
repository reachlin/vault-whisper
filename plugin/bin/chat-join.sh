#!/usr/bin/env bash
# chat-join.sh — subscribe to a room's sentinel issue and record it in local config.
#
# Usage:
#   chat-join.sh <room>
#
# The room must already exist in the backend repo's marker file. Use /chat-create
# (not yet implemented) to create new rooms.

source "$(dirname "$0")/_common.sh"

ROOM="${1:-}"
[[ -n "$ROOM" ]] || { echo "usage: chat-join.sh <room>" >&2; exit 1; }

vw_check_tools
vw_check_auth
vw_load_config

SLUG=$(vw_room_slug "$ROOM")

# Read the backend's marker file to find the room's sentinel issue.
marker=$(vw_get_marker "$VW_REPO" || true)
if [[ -z "$marker" ]]; then
  echo "vault-whisper: backend $VW_REPO has no marker file. Re-run /chat-setup $VW_REPO --init." >&2
  exit 1
fi

ISSUE=$(echo "$marker" | jq -r --arg s "$SLUG" '.rooms[$s].issue // empty')
FOLDER=$(echo "$marker" | jq -r --arg s "$SLUG" '.rooms[$s].folder // empty')

if [[ -z "$ISSUE" ]]; then
  echo "vault-whisper: room '#$SLUG' does not exist in $VW_REPO." >&2
  echo "  Available rooms: $(echo "$marker" | jq -r '.rooms | keys | join(", ")')" >&2
  exit 1
fi

# Subscribe to the sentinel issue.
gh api -X PUT "repos/$VW_REPO/issues/$ISSUE/subscription" \
  -f subscribed=true >/dev/null

# Record it in local config.
vw_update_config "
  .rooms[\"$SLUG\"] = {
    issue: $ISSUE,
    folder: \"$FOLDER\",
    last_seen_commit: null
  }
"

echo "joined #$SLUG (issue #$ISSUE)"
