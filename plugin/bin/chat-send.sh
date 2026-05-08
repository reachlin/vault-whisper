#!/usr/bin/env bash
# chat-send.sh — send a message to a room.
#
# Usage:
#   chat-send.sh <room> <message...>
#
# Example:
#   chat-send.sh '#general' 'hello everyone'

source "$(dirname "$0")/_common.sh"

ROOM=""
MESSAGE=""

# If the first argument starts with '#', it's a room name; otherwise the whole
# input is the message and we default to the first joined room (#general).
# A bare word (no '#') is also treated as a room if it matches a joined room slug.
if [[ "${1:-}" == \#* ]]; then
  ROOM="${1:-}"
  shift || true
  MESSAGE="${*:-}"
else
  # Peek at config to see if the first arg is a joined room slug.
  if [[ -n "${1:-}" && -f "${XDG_CONFIG_HOME:-$HOME/.config}/vault-whisper/config.json" ]]; then
    _slug=$(printf '%s' "${1:-}" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
    _joined=$(jq -r --arg s "$_slug" '.rooms[$s] // empty' \
      "${XDG_CONFIG_HOME:-$HOME/.config}/vault-whisper/config.json")
    if [[ -n "$_joined" ]]; then
      ROOM="#${_slug}"
      shift || true
    fi
  fi
  MESSAGE="${*:-}"
fi

if [[ -z "$MESSAGE" ]]; then
  echo "usage: chat-send.sh [#room] <message...>" >&2
  exit 1
fi

vw_check_tools
vw_check_auth
vw_load_config

if [[ -n "$ROOM" ]]; then
  SLUG=$(vw_room_slug "$ROOM")
else
  SLUG=$(jq -r '.rooms | keys[0] // empty' "$VW_CONFIG")
  if [[ -z "$SLUG" ]]; then
    echo "vault-whisper: no rooms joined. Run /chat-setup first." >&2
    exit 1
  fi
fi

ISSUE=$(jq -r --arg s "$SLUG" '.rooms[$s].issue // empty' "$VW_CONFIG")
if [[ -z "$ISSUE" ]]; then
  echo "vault-whisper: room '#$SLUG' not joined. Run /chat-join $SLUG first." >&2
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
PATH_IN_REPO="$(vw_room_folder "$SLUG")/$FILENAME"

# Commit message references the sentinel issue → GitHub notifies subscribers.
COMMIT_MSG="[$SLUG] $VW_USER: $(printf '%s' "$MESSAGE" | head -c 60) (refs #$ISSUE)"

vw_put_file "$VW_REPO" "$PATH_IN_REPO" "$COMMIT_MSG" "$PAYLOAD"

echo "sent to #$SLUG ($VW_REPO)"
