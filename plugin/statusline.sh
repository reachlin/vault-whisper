#!/usr/bin/env bash
# statusline.sh — prints vault-whisper unread count for Claude Code's status line.
#
# Cheap: caches the count for 15s in a tmp file so it doesn't hit the GitHub API
# on every status redraw.

CACHE="${TMPDIR:-/tmp}/vault-whisper-unread.cache"
CACHE_TTL=15

now=$(date +%s)
if [[ -f "$CACHE" ]]; then
  mtime=$(stat -f %m "$CACHE" 2>/dev/null || stat -c %Y "$CACHE" 2>/dev/null || echo 0)
  age=$((now - mtime))
  if (( age < CACHE_TTL )); then
    cat "$CACHE"
    exit 0
  fi
fi

count=$("$(dirname "$0")/bin/chat-recv.sh" --count 2>/dev/null || echo 0)

if [[ "$count" -gt 0 ]]; then
  out="💬 $count"
else
  out=""
fi

printf '%s' "$out" > "$CACHE"
printf '%s' "$out"
