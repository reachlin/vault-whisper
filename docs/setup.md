# vault-whisper setup

End-user setup guide. Two flows:

- **You are the first person on your team** → use `--init` to create a new backend repo.
- **Someone already set up the backend** → they give you the `owner/repo`, you just join.

## Prerequisites

- `gh` CLI installed and authenticated: `gh auth login`
- `jq` installed (`brew install jq` / `apt install jq`)
- Claude Code installed

## Installing the plugin

Until proper plugin distribution is wired up, copy or symlink the `plugin/` directory into Claude Code's plugin location:

```bash
mkdir -p ~/.claude/plugins
ln -s "$(pwd)/plugin" ~/.claude/plugins/vault-whisper
chmod +x ~/.claude/plugins/vault-whisper/bin/*.sh
chmod +x ~/.claude/plugins/vault-whisper/statusline.sh
```

Then merge `plugin/settings.example.json` into `~/.claude/settings.json` so the `UserPromptSubmit` hook and status line are registered.

## First user on a team — create the backend

```
/chat-setup reachlin/my-team-chat --init
```

This will:
1. Create `reachlin/my-team-chat` as a **private** repo on GitHub.
2. Open a sentinel issue `#general` in the new repo.
3. Write a `.vault-whisper.json` marker file via the Contents API.
4. Write your local config to `~/.config/vault-whisper/config.json`.
5. Subscribe you to the `#general` sentinel issue (you're auto-subscribed as the issue author).

All chat state (messages, rooms, etc.) lives under a **root folder** in the repo — default `chat/`. To use a different folder, pass `--root`:

```
/chat-setup reachlin/my-team-chat --init --root team-messages
```

The root is stored in the marker file, so other users joining don't need to specify it — they'll pick it up automatically.

Now invite your teammates to the repo as **collaborators** on GitHub (Settings → Collaborators). Without being collaborators they can't read or write the private repo.

When a teammate joins (`/chat-setup …`), they're added as an **assignee** on the sentinel issue. Assignment is how vault-whisper subscribes users to rooms (GitHub has no public "subscribe to issue" API, but assignees receive notifications for cross-reference events). The assignees list on the sentinel issue doubles as a visible "who is in this room."

## Joining an existing backend

Your teammate tells you "the chat repo is `reachlin/my-team-chat`." You run:

```
/chat-setup reachlin/my-team-chat
```

This will:
1. Verify the repo exists and has a vault-whisper marker file.
2. Read the list of rooms from the marker.
3. Write your local config.
4. Subscribe you to the `#general` sentinel issue.

If the repo doesn't exist or isn't a vault-whisper backend, the script will error and tell you exactly what to do.

## Sending your first message

```
/chat-send #general hello everyone
```

## Reading messages

On demand:

```
/chat-inbox
```

Automatic: if you merged `settings.example.json`, the `UserPromptSubmit` hook will drain unread messages into Claude's context before every prompt. You'll also see a `💬 N` indicator in the status line.

## Joining additional rooms

```
/chat-join #engineering
```

(Room creation — `/chat-create <room>` — is not yet implemented. For now, new rooms can be added by hand: open a sentinel issue, update the marker file's `rooms` object.)

## Where state lives

| What | Where |
|---|---|
| Per-user config | `~/.config/vault-whisper/config.json` (chmod 600) |
| Backend marker | `<backend-repo>/.vault-whisper.json` |
| Messages | `<backend-repo>/rooms/<room>/<timestamp>-<user>-<id>.json` |
| Sentinel issues | One per room, in the backend repo |
| Unread cache | GitHub's `/notifications` feed |
