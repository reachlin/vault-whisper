#!/usr/bin/env bash
# chat-send.sh — send a message to a room.
#
# Usage:
#   chat-send.sh <room> <message...>
#
# Example:
#   chat-send.sh '#general' 'hello everyone'

source "$(dirname "$0")/_common.sh"

ROOM="${1:-}"
shift || true
MESSAGE="${*:-}"

if [[ -z "$ROOM" || -z "$MESSAGE" ]]; then
  echo "usage: chat-send.sh <room> <message...>" >&2
  exit 1
fi

vw_check_tools
vw_check_auth
vw_load_config

SLUG=$(vw_room_slug "$ROOM")
ISSUE=$(jq -r --arg s "$SLUG" '.rooms[$s].issue // empty' "$VW_CONFIG")

if [[ -z "$ISSUE" ]]; then
  cat >&2 <<EOF
vault-whisper: room '$ROOM' not found in local config.
  Join it first: /chat-join $ROOM
EOF
  exit 1
fi

# Build the message payload.
TS=$(vw_now_iso)
MSG_ID=$(uuidgen 2>/dev/null || echo "$(date +%s)-$RANDOM")
PAYLOAD=$(jq -n \
  --arg from "$VW_USER" \
  --arg room "$SLUG" \
  --arg body "$MESSAGE" \
  --arg ts "$TS" \
  --arg id "$MSG_ID" \
  '{
    id: $id,
    from: $from,
    room: $room,
    type: "text",
    body: $body,
    ts: $ts
  }')

# Unique path: no two writers can collide.
FILENAME="$(vw_now_filename)-${VW_USER}-${MSG_ID:0:8}.json"
PATH_IN_REPO="rooms/$SLUG/$FILENAME"

# Commit message references the sentinel issue → GitHub notifies subscribers.
COMMIT_MSG="[$SLUG] $VW_USER: $(printf '%s' "$MESSAGE" | head -c 60) (refs #$ISSUE)"

vw_put_file "$VW_REPO" "$PATH_IN_REPO" "$COMMIT_MSG" "$PAYLOAD"

echo "sent to #$SLUG ($VW_REPO)"
