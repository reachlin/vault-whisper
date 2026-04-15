#!/usr/bin/env bash
# chat-setup.sh — configure vault-whisper to use a GitHub repo as its chat backend.
#
# Usage:
#   chat-setup.sh <owner/repo>           Join an existing backend.
#   chat-setup.sh <owner/repo> --init    Create and initialize a new backend.

source "$(dirname "$0")/_common.sh"

REPO="${1:-}"
MODE="${2:-}"

if [[ -z "$REPO" ]]; then
  cat >&2 <<EOF
usage: /chat-setup <owner/repo>           join an existing backend
       /chat-setup <owner/repo> --init    create and initialize a new backend
EOF
  exit 1
fi

vw_check_tools
vw_check_auth

USER=$(gh api user -q .login)
echo "Authenticated as: $USER"

init_backend() {
  local repo="$1"

  # 1. Create the repo if it doesn't exist.
  if ! vw_repo_exists "$repo"; then
    echo "Creating private repo $repo..."
    gh repo create "$repo" --private \
      --description "vault-whisper chat backend" \
      --add-readme >/dev/null
  else
    echo "Repo $repo already exists, initializing in place."
  fi

  # 2. Create sentinel issue for #general.
  echo "Creating sentinel issue for #general..."
  local issue_json
  issue_json=$(gh api -X POST "repos/$repo/issues" \
    -f title="#general" \
    -f body="Sentinel issue for the #general room. Do not delete. Subscribe to this issue to receive messages.")
  local general_issue
  general_issue=$(echo "$issue_json" | jq -r .number)
  echo "  issue #$general_issue"

  # 3. Write marker file via Contents API.
  echo "Writing $VW_MARKER_PATH..."
  local marker
  marker=$(jq -n \
    --argjson v 1 \
    --argjson gi "$general_issue" \
    '{version: $v, rooms: {general: {issue: $gi, folder: "rooms/general"}}}')
  vw_put_file "$repo" "$VW_MARKER_PATH" \
    "init: vault-whisper backend (refs #$general_issue)" \
    "$marker"

  echo "Backend initialized."
  MARKER_JSON="$marker"
  GENERAL_ISSUE="$general_issue"
}

join_backend() {
  local repo="$1"

  if ! vw_repo_exists "$repo"; then
    cat >&2 <<EOF
vault-whisper: repo $repo does not exist.
  To create it: /chat-setup $repo --init
EOF
    exit 1
  fi

  local marker
  marker=$(vw_get_marker "$repo" || true)
  if [[ -z "$marker" ]]; then
    cat >&2 <<EOF
vault-whisper: $repo exists but is not a vault-whisper backend
               (no $VW_MARKER_PATH marker file found).
  To initialize it: /chat-setup $repo --init
EOF
    exit 1
  fi

  MARKER_JSON="$marker"
  GENERAL_ISSUE=$(echo "$marker" | jq -r '.rooms.general.issue // empty')
}

if [[ "$MODE" == "--init" ]]; then
  init_backend "$REPO"
else
  join_backend "$REPO"
fi

# Write local config.
mkdir -p "$VW_CONFIG_DIR"
CONFIG=$(jq -n \
  --arg repo "$REPO" \
  --arg user "$USER" \
  --argjson issue "${GENERAL_ISSUE:-null}" \
  '{
    repo: $repo,
    user: $user,
    rooms: {
      general: {
        issue: $issue,
        folder: "rooms/general",
        last_seen_commit: null
      }
    }
  }')
vw_save_config "$CONFIG"

# Subscribe to #general's sentinel issue so we get notifications.
if [[ -n "${GENERAL_ISSUE:-}" && "$GENERAL_ISSUE" != "null" ]]; then
  gh api -X PUT "repos/$REPO/issues/$GENERAL_ISSUE/subscription" \
    -f subscribed=true >/dev/null
  echo "Subscribed to #general (issue #$GENERAL_ISSUE)."
fi

cat <<EOF

Setup complete.
  repo:    $REPO
  user:    $USER
  config:  $VW_CONFIG

Try: /chat-send #general "hello from $USER"
EOF
