# vault-whisper shared helpers. Sourced by the other bin/ scripts.
# Not meant to be executed directly.

set -euo pipefail

VW_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/vault-whisper"
VW_CONFIG="$VW_CONFIG_DIR/config.json"
VW_MARKER_PATH=".vault-whisper.json"

vw_require() {
  command -v "$1" >/dev/null 2>&1 || { echo "vault-whisper: missing required tool: $1" >&2; exit 1; }
}

vw_check_tools() {
  vw_require gh
  vw_require jq
  vw_require base64
}

vw_check_auth() {
  gh auth status >/dev/null 2>&1 || {
    echo "vault-whisper: gh is not authenticated. Run 'gh auth login' first." >&2
    exit 1
  }
}

vw_load_config() {
  [[ -f "$VW_CONFIG" ]] || {
    echo "vault-whisper: not configured. Run '/chat-setup <owner/repo>' first." >&2
    exit 1
  }
  VW_REPO=$(jq -r '.repo // empty' "$VW_CONFIG")
  VW_USER=$(jq -r '.user // empty' "$VW_CONFIG")
  [[ -n "$VW_REPO" ]] || { echo "vault-whisper: config missing 'repo'" >&2; exit 1; }
  [[ -n "$VW_USER" ]] || { echo "vault-whisper: config missing 'user'" >&2; exit 1; }
}

vw_save_config() {
  # Usage: vw_save_config <json>
  mkdir -p "$VW_CONFIG_DIR"
  printf '%s\n' "$1" > "$VW_CONFIG"
  chmod 600 "$VW_CONFIG"
}

vw_update_config() {
  # Usage: vw_update_config <jq_expression>
  local tmp
  tmp=$(mktemp)
  jq "$1" "$VW_CONFIG" > "$tmp"
  mv "$tmp" "$VW_CONFIG"
  chmod 600 "$VW_CONFIG"
}

vw_now_iso() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

vw_now_filename() {
  date -u +%Y%m%dT%H%M%SZ
}

vw_b64() {
  # macOS and linux base64 both accept stdin + -w0 differs; use tr to strip newlines.
  base64 | tr -d '\n'
}

vw_room_slug() {
  # #general → general ; "Some Name" → some-name
  local name="${1#\#}"
  printf '%s' "$name" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-'
}

vw_repo_exists() {
  gh repo view "$1" >/dev/null 2>&1
}

vw_get_marker() {
  # Prints marker JSON to stdout, or exits non-zero if not present.
  gh api "repos/$1/contents/$VW_MARKER_PATH" --jq '.content' 2>/dev/null \
    | base64 -d 2>/dev/null
}

vw_put_file() {
  # Usage: vw_put_file <repo> <path> <commit_message> <content_string> [sha]
  # If sha is provided, this is an update; otherwise a create.
  local repo="$1" path="$2" msg="$3" content="$4" sha="${5:-}"
  local content_b64
  content_b64=$(printf '%s' "$content" | vw_b64)
  if [[ -n "$sha" ]]; then
    gh api -X PUT "repos/$repo/contents/$path" \
      -f message="$msg" \
      -f content="$content_b64" \
      -f sha="$sha" \
      -f branch=main >/dev/null
  else
    gh api -X PUT "repos/$repo/contents/$path" \
      -f message="$msg" \
      -f content="$content_b64" \
      -f branch=main >/dev/null
  fi
}
