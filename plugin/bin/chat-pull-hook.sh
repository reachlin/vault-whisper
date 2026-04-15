#!/usr/bin/env bash
# chat-pull-hook.sh — UserPromptSubmit hook. Drains unread messages and, if any,
# prints them so they land in Claude's context for the upcoming turn.
#
# Wire this up in settings.json:
#   "hooks": {
#     "UserPromptSubmit": [
#       { "command": "~/.claude/plugins/vault-whisper/bin/chat-pull-hook.sh" }
#     ]
#   }

# Silent failure — we never want to block a user prompt because chat is broken.
set +e

output=$("$(dirname "$0")/chat-recv.sh" 2>/dev/null)
if [[ -n "$output" && "$output" != "(no new messages)" ]]; then
  printf '[vault-whisper: new messages since last prompt]\n%s\n' "$output"
fi
exit 0
