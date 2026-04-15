#!/usr/bin/env bash
# chat-setup.sh — configure vault-whisper to use a GitHub repo as its chat backend.
#
# Usage:
#   chat-setup.sh <owner/repo>                    Join an existing backend.
#   chat-setup.sh <owner/repo> --init             Create and initialize a new backend.
#   chat-setup.sh <owner/repo> --init --root DIR  Use DIR as the chat root (default: chat).

source "$(dirname "$0")/_common.sh"

REPO=""
MODE="join"
ROOT="chat"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --init) MODE="init"; shift ;;
    --root) ROOT="$2"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*) echo "vault-whisper: unknown flag: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$REPO" ]]; then REPO="$1"
      else echo "vault-whisper: unexpected argument: $1" >&2; exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$REPO" ]]; then
  # No arguments → show current status if configured.
  if [[ -f "$VW_CONFIG" ]]; then
    vw_check_tools
    vw_load_config
    echo "vault-whisper status"
    echo "  repo:    $VW_REPO"
    echo "  user:    $VW_USER"
    echo "  root:    $VW_ROOT"
    echo "  config:  $VW_CONFIG"
    echo
    rooms=$(jq -r '.rooms | keys[]?' "$VW_CONFIG")
    if [[ -z "$rooms" ]]; then
      echo "Rooms: (none joined)"
    else
      echo "Rooms:"
      while IFS= read -r room; do
        issue=$(jq -r --arg r "$room" '.rooms[$r].issue' "$VW_CONFIG")
        last_seen=$(jq -r --arg r "$room" '.rooms[$r].last_seen_commit // empty' "$VW_CONFIG")
        if [[ -z "$last_seen" ]]; then
          printf '  #%-12s  issue #%s   (no messages read yet)\n' "$room" "$issue"
        else
          printf '  #%-12s  issue #%s   last seen %s\n' "$room" "$issue" "${last_seen:0:7}"
        fi
      done <<< "$rooms"
    fi
    exit 0
  fi
  cat >&2 <<EOF
vault-whisper is not configured.

usage: /chat-setup                                 show current status (when configured)
       /chat-setup <owner/repo>                    join an existing backend
       /chat-setup <owner/repo> --init             create and initialize a new backend
       /chat-setup <owner/repo> --init --root DIR  use DIR as the chat root (default: chat)
EOF
  exit 1
fi

vw_check_tools
vw_check_auth

USER=$(gh api user -q .login)
echo "Authenticated as: $USER"

init_backend() {
  local repo="$1" root="$2"

  # 1. Create the repo if it doesn't exist.
  if ! vw_repo_exists "$repo"; then
    echo "Creating private repo $repo..."
    gh repo create "$repo" --private \
      --description "vault-whisper chat backend" \
      --add-readme >/dev/null
  else
    echo "Repo $repo already exists, initializing in place."
  fi

  # 2. Check for existing marker — don't clobber if this repo is already a backend.
  local existing_marker
  existing_marker=$(vw_get_marker "$repo" || true)
  if [[ -n "$existing_marker" ]]; then
    echo "Repo $repo already has a vault-whisper marker. Joining instead of re-initializing."
    MARKER_JSON="$existing_marker"
    GENERAL_ISSUE=$(echo "$existing_marker" | jq -r '.rooms.general.issue // empty')
    CHAT_ROOT=$(echo "$existing_marker" | jq -r '.root // "chat"')
    return 0
  fi

  # 3. Create sentinel issue for #general.
  echo "Creating sentinel issue for #general..."
  local issue_json
  issue_json=$(gh api -X POST "repos/$repo/issues" \
    -f title="#general" \
    -f body="Sentinel issue for the #general room. Do not delete. Subscribe to this issue to receive messages.")
  local general_issue
  general_issue=$(echo "$issue_json" | jq -r .number)
  echo "  issue #$general_issue"

  # 4. Write marker file via Contents API.
  echo "Writing $VW_MARKER_PATH (root: $root)..."
  local marker
  marker=$(jq -n \
    --argjson v 1 \
    --arg root "$root" \
    --argjson gi "$general_issue" \
    '{version: $v, root: $root, rooms: {general: {issue: $gi}}}')
  vw_put_file "$repo" "$VW_MARKER_PATH" \
    "init: vault-whisper backend (refs #$general_issue)" \
    "$marker"

  echo "Backend initialized."
  MARKER_JSON="$marker"
  GENERAL_ISSUE="$general_issue"
  CHAT_ROOT="$root"
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
  CHAT_ROOT=$(echo "$marker" | jq -r '.root // "chat"')
}

if [[ "$MODE" == "init" ]]; then
  init_backend "$REPO" "$ROOT"
else
  join_backend "$REPO"
fi

# Write local config.
mkdir -p "$VW_CONFIG_DIR"
CONFIG=$(jq -n \
  --arg repo "$REPO" \
  --arg user "$USER" \
  --arg root "$CHAT_ROOT" \
  --argjson issue "${GENERAL_ISSUE:-null}" \
  '{
    repo: $repo,
    user: $user,
    root: $root,
    rooms: (
      if $issue == null then {}
      else { general: { issue: $issue, last_seen_commit: null } }
      end
    )
  }')
vw_save_config "$CONFIG"

# Subscribe to #general. Issue authors are auto-subscribed, so for --init
# this is a no-op on the first run; for --join it adds the user as an
# assignee which makes them a participant and routes cross-reference
# notifications to their /notifications feed.
if [[ -n "${GENERAL_ISSUE:-}" && "$GENERAL_ISSUE" != "null" ]]; then
  vw_subscribe_issue "$REPO" "$GENERAL_ISSUE" "$USER"
  echo "Subscribed to #general (issue #$GENERAL_ISSUE)."
fi

cat <<EOF

Setup complete.
  repo:    $REPO
  user:    $USER
  root:    $CHAT_ROOT
  config:  $VW_CONFIG

Try: /chat-send #general "hello from $USER"
EOF
