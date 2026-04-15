#!/usr/bin/env bash
# chat-inbox.sh — fetch and print unread messages across all joined rooms.
#
# Usage:
#   chat-inbox.sh                 Print unread messages, mark them read.
#   chat-inbox.sh --peek          Print unread messages without marking read.
#   chat-inbox.sh --count         Print just the unread count (for statusline).

source "$(dirname "$0")/_common.sh"

MODE="${1:-read}"

vw_check_tools
vw_check_auth
vw_load_config

# For each room in config, list commits to its folder since last_seen_commit,
# fetch the new files, print them, and advance last_seen_commit.
total_unread=0
output=""

while IFS= read -r room; do
  [[ -z "$room" ]] && continue
  folder=$(jq -r --arg r "$room" '.rooms[$r].folder // empty' "$VW_CONFIG")
  last_seen=$(jq -r --arg r "$room" '.rooms[$r].last_seen_commit // empty' "$VW_CONFIG")
  [[ -z "$folder" ]] && continue

  # Get commits touching this folder, newest first.
  commits_json=$(gh api "repos/$VW_REPO/commits?path=$folder&per_page=50" 2>/dev/null || echo "[]")

  # Collect commit SHAs up to (but not including) last_seen.
  if [[ -n "$last_seen" && "$last_seen" != "null" ]]; then
    new_shas=$(echo "$commits_json" | jq -r --arg last "$last_seen" '
      [.[] | .sha] as $all
      | ($all | index($last)) as $i
      | if $i == null then $all else $all[:$i] end
      | .[]
    ')
  else
    # First-time read: show the most recent 20 to avoid flooding.
    new_shas=$(echo "$commits_json" | jq -r '.[:20] | .[].sha')
  fi

  # Reverse so we print oldest-first (chat order).
  new_shas_ordered=$(echo "$new_shas" | awk '{a[NR]=$0} END{for(i=NR;i>0;i--) print a[i]}')

  latest_sha=$(echo "$commits_json" | jq -r '.[0].sha // empty')

  # For each new commit, find the files it added under this folder and fetch them.
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    files=$(gh api "repos/$VW_REPO/commits/$sha" --jq \
      '.files[] | select(.status=="added") | .filename' 2>/dev/null || true)
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      [[ "$f" != $folder/* ]] && continue
      content=$(gh api "repos/$VW_REPO/contents/$f" --jq .content 2>/dev/null | base64 -d 2>/dev/null || true)
      [[ -z "$content" ]] && continue
      from=$(echo "$content" | jq -r '.from // "?"')
      body=$(echo "$content" | jq -r '.body // ""')
      ts=$(echo "$content" | jq -r '.ts // ""')
      output+="[$ts] #$room <$from> $body"$'\n'
      total_unread=$((total_unread + 1))
    done <<< "$files"
  done <<< "$new_shas_ordered"

  # Advance last_seen in config (unless --peek or --count).
  if [[ "$MODE" != "--peek" && "$MODE" != "--count" && -n "$latest_sha" ]]; then
    vw_update_config ".rooms[\"$room\"].last_seen_commit = \"$latest_sha\""
  fi
done < <(jq -r '.rooms | keys[]' "$VW_CONFIG")

# Mark notifications read (best-effort, scoped to our repo).
if [[ "$MODE" == "read" && $total_unread -gt 0 ]]; then
  gh api "notifications?participating=false" --jq \
    ".[] | select(.repository.full_name==\"$VW_REPO\") | .id" 2>/dev/null \
    | while read -r thread_id; do
        [[ -n "$thread_id" ]] && gh api -X PATCH "notifications/threads/$thread_id" >/dev/null 2>&1 || true
      done
fi

if [[ "$MODE" == "--count" ]]; then
  echo "$total_unread"
  exit 0
fi

if [[ $total_unread -eq 0 ]]; then
  echo "(no new messages)"
else
  printf '%s' "$output"
fi
