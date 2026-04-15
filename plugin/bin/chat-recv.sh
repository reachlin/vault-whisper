#!/usr/bin/env bash
# chat-inbox.sh — fetch and print unread messages across all joined rooms.
#
# Usage:
#   chat-inbox.sh [room] [n]      Print last n messages from room (defaults: all rooms, 3).
#   chat-inbox.sh --peek          Print unread messages without marking read.
#   chat-inbox.sh --count         Print just the unread count (for statusline).

source "$(dirname "$0")/_common.sh"

MODE="read"
COLOR="auto"
FILTER_ROOM=""
MIN_MESSAGES=3

while [[ $# -gt 0 ]]; do
  case "$1" in
    --peek) MODE="peek"; shift ;;
    --count) MODE="count"; shift ;;
    --color) COLOR="always"; shift ;;
    --no-color) COLOR="never"; shift ;;
    -h|--help)
      cat <<'EOF'
chat-inbox.sh — fetch and print unread messages.

  chat-inbox.sh [room] [n]      Show last n messages from room (defaults: all rooms, 3).
  chat-inbox.sh --peek          Print unread without marking read.
  chat-inbox.sh --count         Print unread count (for statusline).
  chat-inbox.sh --color         Force ANSI color on message bodies.
  chat-inbox.sh --no-color      Force colors off.

Default color mode is auto (on when stdout is a TTY, else off).
EOF
      exit 0
      ;;
    --) shift; break ;;
    -*) echo "chat-inbox: unknown flag: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$FILTER_ROOM" ]]; then
        FILTER_ROOM=$(vw_room_slug "$1")
      elif [[ "$1" =~ ^[0-9]+$ ]]; then
        MIN_MESSAGES="$1"
      else
        echo "chat-inbox: unexpected argument: $1" >&2; exit 1
      fi
      shift
      ;;
  esac
done

vw_check_tools
vw_check_auth
vw_load_config

# Resolve auto → always/never based on whether stdout is a terminal.
if [[ "$COLOR" == "auto" ]]; then
  if [[ -t 1 ]]; then COLOR="always"; else COLOR="never"; fi
fi

if [[ "$COLOR" == "always" ]]; then
  VW_BG=$'\033[44;97m'      # blue background, bright white — message body
  VW_ROOM=$'\033[1;96m'     # bold bright cyan — room header
  VW_RESET=$'\033[0m'
else
  VW_BG=""
  VW_ROOM=""
  VW_RESET=""
fi

# Helper: fetch messages from a list of SHAs (oldest-first) for a given room/folder.
# Outputs formatted message lines. Also sets VW_LAST_DATE to the date of the last message.
# Usage: room_msgs=$(vw_fetch_msgs "$shas" "$folder" "$room" "$prefix")
VW_LAST_DATE=""
vw_fetch_msgs() {
  local shas_ordered="$1" folder="$2" room="$3" prefix="$4"
  local _result=""
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    local files
    files=$(gh api "repos/$VW_REPO/commits/$sha" --jq \
      '.files[] | select(.status=="added") | .filename' 2>/dev/null || true)
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      [[ "$f" != $folder/* ]] && continue
      local content
      content=$(gh api "repos/$VW_REPO/contents/$f" --jq .content 2>/dev/null | base64 -d 2>/dev/null || true)
      [[ -z "$content" ]] && continue
      local from body ts
      from=$(echo "$content" | jq -r '.from // "?"')
      body=$(echo "$content" | jq -r '.body // ""')
      ts=$(echo "$content" | jq -r '.ts // ""')
      VW_LAST_DATE="${ts%%T*}"
      local time
      time="${ts#*T}"; time="${time%%Z*}"
      _result+="${prefix}${time} <$from> ${VW_BG}${body}${VW_RESET}"$'\n'
    done <<< "$files"
  done <<< "$shas_ordered"
  echo -n "$_result"
}

# For each room in config, list commits to its folder since last_seen_commit,
# fetch the new files, print them, and advance last_seen_commit.
total_unread=0
new_output=""
total_shown=0

while IFS= read -r room; do
  [[ -z "$room" ]] && continue
  [[ -n "$FILTER_ROOM" && "$room" != "$FILTER_ROOM" ]] && continue
  folder=$(vw_room_folder "$room")
  last_seen=$(jq -r --arg r "$room" '.rooms[$r].last_seen_commit // empty' "$VW_CONFIG")

  # Get commits touching this folder, newest first.
  commits_json=$(gh api "repos/$VW_REPO/commits?path=$folder&per_page=50" 2>/dev/null || echo "[]")

  # Collect new commit SHAs (after last_seen).
  if [[ -n "$last_seen" && "$last_seen" != "null" ]]; then
    new_shas=$(echo "$commits_json" | jq -r --arg last "$last_seen" '
      [.[] | .sha] as $all
      | ($all | index($last)) as $i
      | if $i == null then $all else $all[:$i] end
      | .[]
    ')
    # Collect historical commit SHAs (at and after last_seen, for padding).
    hist_shas=$(echo "$commits_json" | jq -r --arg last "$last_seen" '
      [.[] | .sha] as $all
      | ($all | index($last)) as $i
      | if $i == null then [] else $all[$i:] end
      | .[]
    ')
  else
    # First-time read: show the most recent 20 to avoid flooding.
    new_shas=$(echo "$commits_json" | jq -r '.[:20] | .[].sha')
    hist_shas=""
  fi

  # Reverse new_shas so we print oldest-first (chat order).
  new_shas_ordered=$(echo "$new_shas" | awk '{a[NR]=$0} END{for(i=NR;i>0;i--) print a[i]}')

  latest_sha=$(echo "$commits_json" | jq -r '.[0].sha // empty')

  # Fetch new messages (marked with "=>").
  room_new=$(vw_fetch_msgs "$new_shas_ordered" "$folder" "$room" "=> ")
  new_count=$(echo -n "$room_new" | grep -c '^' || true)
  total_unread=$((total_unread + new_count))
  total_shown=$((total_shown + new_count))

  # Advance last_seen in config (unless --peek or --count).
  if [[ "$MODE" == "read" && -n "$latest_sha" ]]; then
    vw_update_config ".rooms[\"$room\"].last_seen_commit = \"$latest_sha\""
  fi

  # Pad with historical messages if we haven't reached MIN_MESSAGES yet.
  room_old=""
  if [[ $total_shown -lt $MIN_MESSAGES && -n "$hist_shas" ]]; then
    need=$((MIN_MESSAGES - total_shown))
    # Take the most recent `need` historical SHAs and reverse to oldest-first.
    hist_shas_limited=$(echo "$hist_shas" | head -n "$need" | awk '{a[NR]=$0} END{for(i=NR;i>0;i--) print a[i]}')
    room_old=$(vw_fetch_msgs "$hist_shas_limited" "$folder" "$room" "   ")
    old_count=$(echo -n "$room_old" | grep -c '^' || true)
    total_shown=$((total_shown + old_count))
  fi

  # Collect per-room output with a header line (room name + date + counts).
  room_combined="${room_old}${room_new}"
  if [[ -n "$room_combined" ]]; then
    room_date=$(echo "$commits_json" | jq -r '.[0].commit.committer.date // "" | .[0:10]')
    room_msg_count=$(echo -n "$room_combined" | grep -c '^' || true)
    if [[ $new_count -gt 0 ]]; then
      room_stats="  (${room_msg_count} msgs, ${new_count} new)"
    else
      room_stats="  (${room_msg_count} msgs)"
    fi
    new_output+="${VW_ROOM}#${room}  ${room_date}${room_stats}${VW_RESET}"$'\n'
    new_output+="$room_combined"$'\n'
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

if [[ "$MODE" == "count" ]]; then
  echo "$total_unread"
  exit 0
fi

if [[ $total_unread -eq 0 && $total_shown -eq 0 ]]; then
  echo "(no new messages)"
else
  printf '%s' "$new_output"
  if [[ $total_unread -eq 0 ]]; then
    echo "(no new messages — showing recent history)"
  fi
fi
