#!/usr/bin/env bash
# install.sh — install vault-whisper into the current user's Claude Code setup.
#
# Copies slash commands into ~/.claude/commands/, symlinks the plugin dir into
# ~/.claude/plugins/vault-whisper/ (so bin/ and statusline.sh are reachable at
# the paths the command markdown and settings reference), and merges hook +
# status-line entries into ~/.claude/settings.json.
#
# Safe to re-run. Backs up settings.json before touching it.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$REPO_ROOT/plugin"
CC_DIR="$HOME/.claude"

command -v jq >/dev/null || { echo "install: jq is required" >&2; exit 1; }

mkdir -p "$CC_DIR/commands" "$CC_DIR/plugins"

echo "Installing commands to $CC_DIR/commands/"
for f in "$PLUGIN_DIR"/commands/*.md; do
  cp "$f" "$CC_DIR/commands/"
done

echo "Linking plugin dir to $CC_DIR/plugins/vault-whisper"
ln -sfn "$PLUGIN_DIR" "$CC_DIR/plugins/vault-whisper"

chmod +x "$PLUGIN_DIR"/bin/*.sh "$PLUGIN_DIR"/statusline.sh

SETTINGS="$CC_DIR/settings.json"
if [[ -f "$SETTINGS" ]]; then
  BACKUP="$SETTINGS.vw-backup-$(date +%s)"
  cp "$SETTINGS" "$BACKUP"
  echo "Backed up settings to $BACKUP"
else
  echo '{}' > "$SETTINGS"
fi

TMP=$(mktemp)
jq '. + {
  hooks: ((.hooks // {}) + {
    UserPromptSubmit: ((.hooks.UserPromptSubmit // []) + [
      {
        hooks: [
          {
            type: "command",
            command: "~/.claude/plugins/vault-whisper/bin/chat-pull-hook.sh"
          }
        ]
      }
    ])
  }),
  statusLine: {
    type: "command",
    command: "~/.claude/plugins/vault-whisper/statusline.sh"
  }
}' "$SETTINGS" > "$TMP"
mv "$TMP" "$SETTINGS"
echo "Merged hook + statusLine into $SETTINGS"

cat <<EOF

Install complete.

Next steps:
  1. Restart your Claude Code session so it picks up the new commands,
     hook, and status line. (Commands are scanned at session startup.)
  2. Run /chat-setup <owner/repo> --init   (first user on a team)
     or   /chat-setup <owner/repo>          (joining an existing backend)
  3. Try /chat-send '#general' 'hello'
EOF
