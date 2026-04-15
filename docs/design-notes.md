# vault-whisper — design notes

Notes from the initial design conversation. Captures the options considered,
why each was rejected or accepted, and the design we plan to verify and build.

## Goal

A chat app that lives inside Claude Code. Each user, while using `claude` in
their terminal, can talk to other users — DMs and rooms. Integration is via
an MCP server (and possibly a `UserPromptSubmit` hook + status line for
inbound message surfacing). No new infrastructure to host if at all possible.

## Options considered

### 1. Build our own MCP server + relay (rejected for v1)

- MCP server per user, persistent WebSocket to a small relay.
- Relay handles fan-out, persistence, optional E2E.
- **Why rejected:** every piece (auth, identity, persistence, notifications,
  ops) has to be built and run. The relay is small but it's still
  infrastructure we'd own forever.

### 2. Wrap an existing chat backend — Matrix (rejected as too heavy)

- Matrix is the strongest open-protocol option: federated, free homeservers
  (matrix.org), full HTTP API, real E2E support, mature client libraries
  (`matrix-nio`, `matrix-js-sdk`).
- Each user gets a real Matrix account; MCP server is a thin Matrix client
  exposing `chat_send`, `chat_inbox`, etc.
- Receive path: long-poll `/sync` in a background task, write events to a
  local SQLite inbox, surface via tool / hook / status line.
- **Why rejected:** still requires a background sync loop, account
  registration, a custom inbox table, and either trusting matrix.org or
  self-hosting Synapse. Heavy for what we want.

Other backends briefly considered and rejected:

- **IRC** — trivial but no persistence, no identity, no notifications.
- **Zulip** — nice threading, but ties us to one org, not federated.
- **Discord / Slack / Telegram** — bot APIs are shaped for bots-in-rooms,
  not bots-as-users. DMs between two Claude Code users get awkward and
  often violate ToS.

### 3. GitHub as backend (chosen direction)

The pivot that made everything click: **every Claude Code user already has a
GitHub account and a `gh` token**. So identity, auth, and persistence are
solved for free. Notifications are solved too — GitHub already maintains a
per-user unread inbox at `GET /notifications`.

Within the GitHub-backed family, three sub-designs were considered:

#### 3a. Issues + comments (messages = comments)

- Room = GitHub issue. Message = comment on that issue. DM = private
  2-person issue.
- `chat_inbox()` is literally `GET /notifications` — GitHub *is* the
  inbox.
- Identity = GitHub username. `@mentions` give us real notifications and
  email/mobile push for free.
- ~150 LOC, can be entirely stateless (no background process — just poll
  on `UserPromptSubmit`).
- **Downsides:** message body is a markdown string (no structure),
  attachments are awkward, users can silently edit/delete history via the
  GitHub UI, and the issue grows to thousands of comments.

#### 3b. Files + commits (messages = commits to files)

- Room = folder. Message = file, sent via a git commit.
- Naive single-file design dies on concurrency (two writers → push race).
  Salvaged by a **per-sender file layout**: `rooms/general/alice.jsonl`,
  `rooms/general/bob.jsonl` — no two writers ever touch the same file.
- **Wins:** host-independent (works on Gitea, GitLab, self-hosted, even a
  bare repo on a server), real cryptographically-signable history,
  full offline access via `git clone`.
- **Loses on everything else:** no notifications (GitHub doesn't notify on
  commits the way it does on @mentions), every send is `pull && commit
  && push` (~1–3s, requires a working tree), repo bloats, edits require
  force-push which breaks every other clone.
- The moment you give up notifications, you've thrown away the lightness
  that made GitHub appealing in the first place.

#### 3c. Files + sentinel issue (chosen)

The hybrid that fixes the file-design's biggest problem.

- **Storage:** one folder per room, one file per message, unique path so
  writers never collide:
  ```
  rooms/
    general/
      2026-04-15T10-30-00Z-alice-a3f.json
      2026-04-15T10-30-04Z-bob-7c1.json
    dm-alice-bob/
      2026-04-15T11-02-15Z-alice-9d2.json
  ```
- **Notification:** one **sentinel issue** per room. `#general` = issue
  #42. The issue body is just a marker; nobody comments on it.
- **Send is one API call:**
  ```
  PUT /repos/{owner}/{repo}/contents/rooms/general/{path}.json
  {
    "message": "alice: hi everyone (refs #42)",
    "content": "<base64-encoded JSON>",
    "branch": "main"
  }
  ```
  GitHub's Contents API creates the commit server-side — **no clone, no
  working tree, no `git pull` race.** The commit message contains `#42`,
  so GitHub auto-creates a "referenced" timeline event on issue #42, and
  every subscriber to that issue gets a notification.
- **Receive flow:**
  1. `GET /notifications` → "issue #42 had activity"
  2. `GET /repos/{o}/{r}/commits?path=rooms/general/&since={last_seen}` →
     list new commits with filenames
  3. `GET /repos/{o}/{r}/contents/rooms/general/{filename}` → fetch each
     new message
  4. `PATCH /notifications/threads/{id}` → mark read
- **Joining a room** = subscribing to its sentinel issue
  (`PUT /repos/{o}/{r}/issues/{n}/subscription`).

### Why 3c over 3a

Three real wins for files + sentinel over plain comments-as-messages:

1. **Structured messages.** JSON files carry `{from, to, type, body,
   reply_to, attachments, reactions, ...}` natively. Comments force
   everything into a markdown string and parse it back.
2. **Binary attachments are free.** Commit a PNG, a `.patch`, a tarball —
   it's just a file in the repo.
3. **Real, immutable, optionally signed history.** `git log
   rooms/general/` is the chat log. Signed commits = verifiable messages.
   Comments are mutable via the GitHub UI.

Cost: ~100 extra LOC of plumbing, one extra API round-trip on receive
(notification → fetch file vs. notification → comment-body-inline).

For a Claude-Code-shaped chat where messages may carry code blocks, tool
outputs, file diffs, or structured handoffs between sessions, the
structured-payload story is worth the extra plumbing.

## Design risks

The whole notification model rests on one assumption that needs a real test
before any code is written:

> When a commit whose message contains `#42` is pushed (or created via the
> Contents API), does GitHub generate a "cross-referenced" timeline event on
> issue #42, and does that event reach subscribers via `GET /notifications`?

Answering this is what `scripts/verify-notification.sh` is for. The script
makes a test issue, creates a commit referencing it via the Contents API
(the same path the real app will use), waits, and inspects the issue's
timeline for the cross-reference event. If the event is present, the
notification machinery will fire for any *other* subscribers (you don't
notify yourself about your own activity, so a single-account test cannot
verify `/notifications` directly).

Other open questions to resolve later:

- **Notification coalescing:** GitHub may batch notifications when many
  commits land quickly. Acceptable for chat (notification only says "go
  look") but worth measuring.
- **DM privacy in a shared repo:** all collaborators can read all rooms.
  Either accept this (Slack-equivalent trust model), or use a separate
  private repo per DM pair, or client-side encrypt message bodies.
- **Rate limits at scale:** 5000 req/hr/user is comfortable for one user
  in a few rooms. Polling `/notifications` with ETags is cheap.
- **GitHub Acceptable Use:** chat tied to a developer tool, low volume,
  on private repos — almost certainly fine. A public product generating
  millions of comments/commits would push the boundary.
- **Inbound message surfacing inside Claude Code:** the MCP push problem
  is the same regardless of backend. Plan: combine `chat_inbox` tool
  (manual), `UserPromptSubmit` hook (automatic, prepends unread to
  context), and a status line showing unread count.

## Next steps

1. Run `scripts/verify-notification.sh` and confirm the cross-reference
   event lands on the issue timeline.
2. If yes: sketch the MCP tool surface (`chat_send`, `chat_dm`,
   `chat_inbox`, `chat_join_room`, `chat_create_room`, `chat_history`,
   `chat_list_rooms`).
3. Pick a language (Python or Node) and build a minimal stateless MCP
   server that wraps `gh api`.
4. Add the `UserPromptSubmit` hook and status line.
5. Two-person dogfood test.
