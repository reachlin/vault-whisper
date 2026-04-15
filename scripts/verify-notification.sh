#!/usr/bin/env bash
# verify-notification.sh
#
# Verifies the design assumption behind vault-whisper:
#
#   When a commit whose message contains "#N" is created via the GitHub
#   Contents API, GitHub generates a "cross-referenced" timeline event on
#   issue #N. That event is what subscribers of issue #N see in their
#   /notifications feed, so confirming the event exists confirms the entire
#   notification path the chat app will rely on.
#
# Single-account test: GitHub does not notify you about your own activity,
# so we cannot check /notifications directly with one account. Instead we
# inspect the issue's timeline for the cross-reference event, which is
# exactly what would trigger notifications for *other* subscribers.
#
# Usage:
#   ./scripts/verify-notification.sh                 # uses current repo (gh repo view)
#   ./scripts/verify-notification.sh owner/repo      # uses given repo
#
# Requires: gh (authenticated), jq.

set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Repo: $REPO"

command -v jq >/dev/null || { echo "jq is required"; exit 1; }

cleanup_issue=""
cleanup_path=""
cleanup() {
  if [[ -n "$cleanup_issue" ]]; then
    echo "Cleaning up: closing issue #$cleanup_issue"
    gh issue close "$cleanup_issue" --repo "$REPO" >/dev/null 2>&1 || true
  fi
  if [[ -n "$cleanup_path" ]]; then
    echo "Cleaning up: deleting test file $cleanup_path"
    sha=$(gh api "repos/$REPO/contents/$cleanup_path" -q .sha 2>/dev/null || true)
    if [[ -n "$sha" ]]; then
      gh api -X DELETE "repos/$REPO/contents/$cleanup_path" \
        -f message="cleanup: remove verification test file" \
        -f sha="$sha" >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup EXIT

# 1. Create a sentinel test issue.
echo
echo "Step 1: creating test issue..."
issue_json=$(gh issue create \
  --repo "$REPO" \
  --title "vault-whisper notification verification (auto-test)" \
  --body "Sentinel issue created by scripts/verify-notification.sh. Safe to close." \
  --json number,url 2>/dev/null || \
  gh api "repos/$REPO/issues" \
    -f title="vault-whisper notification verification (auto-test)" \
    -f body="Sentinel issue created by scripts/verify-notification.sh. Safe to close." \
    --jq '{number: .number, url: .html_url}')

# `gh issue create --json` prints the URL on its own line in some versions; normalize.
issue_number=$(echo "$issue_json" | jq -r '.number // empty')
if [[ -z "$issue_number" ]]; then
  # Fall back to the most recent issue we own with this title.
  issue_number=$(gh api "repos/$REPO/issues?state=open&per_page=20" \
    --jq '[.[] | select(.title=="vault-whisper notification verification (auto-test)")][0].number')
fi
cleanup_issue="$issue_number"
echo "  issue #$issue_number"

# 2. Create a commit via the Contents API whose commit message references the issue.
echo
echo "Step 2: creating commit via Contents API that references #$issue_number..."
test_path="verification/test-$(date -u +%Y%m%dT%H%M%SZ).json"
cleanup_path="$test_path"
content_b64=$(printf '{"verification": true, "ts": "%s"}' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | base64 | tr -d '\n')

gh api -X PUT "repos/$REPO/contents/$test_path" \
  -f message="verify: notification path test (refs #$issue_number)" \
  -f content="$content_b64" \
  -f branch="main" >/dev/null
echo "  committed: $test_path"

# 3. Poll the issue timeline for a cross-referenced event.
echo
echo "Step 3: polling issue timeline for cross-reference event..."
found=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  sleep 2
  events=$(gh api -H "Accept: application/vnd.github+json" \
    "repos/$REPO/issues/$issue_number/timeline?per_page=100" 2>/dev/null || echo "[]")
  count=$(echo "$events" | jq '[.[] | select(.event=="referenced" or .event=="cross-referenced")] | length')
  echo "  attempt $attempt: $count cross-reference event(s) found"
  if [[ "$count" -ge 1 ]]; then
    found=1
    break
  fi
done

echo
if [[ "$found" -eq 1 ]]; then
  echo "PASS: GitHub generated a cross-reference event on issue #$issue_number."
  echo "      The notification path is viable. Subscribers to a sentinel issue"
  echo "      will be notified when a commit references it."
  exit 0
else
  echo "FAIL: no cross-reference event appeared on issue #$issue_number after 20s."
  echo
  echo "      Possible causes:"
  echo "      - Commits created via the Contents API may not trigger cross-references"
  echo "        the same way pushed commits do. Try pushing a real commit instead."
  echo "      - Repository permissions or branch protection."
  echo "      - GitHub processing delay longer than 20s (rare)."
  echo
  echo "      Inspect manually: gh issue view $issue_number --repo $REPO --web"
  exit 1
fi
