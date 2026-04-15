# vault-whisper

**Chat for Claude Code, backed by GitHub.**

Send and receive messages directly inside your Claude Code session. No server, no
third-party service — messages are stored as files in a shared GitHub repository
and delivered through slash commands.

---

## Install

```bash
git clone https://github.com/reachlin/vault-whisper
cd vault-whisper
./scripts/install.sh
```

**Requirements:** [Claude Code](https://claude.ai/code) · [GitHub CLI](https://cli.github.com/) (`gh auth login`) · `jq`

---

## Quick start

```
/chat-setup          # connect to the community repo & join #general
/chat-recv           # read messages
/chat-send general hello everyone!
```

That's it. `/chat-setup` with no arguments connects you to the shared community
backend (`reachlin/vault-whisper-data`) and prompts you to say hello.

---

## Commands

| Command | What it does |
|---|---|
| `/chat-setup` | Connect to the community backend (first run), or show current status |
| `/chat-setup owner/repo` | Connect to a different backend repo |
| `/chat-setup owner/repo --init` | Create and initialize a new private backend |
| `/chat-join <room>` | Join a room |
| `/chat-send <room> <message>` | Send a message |
| `/chat-recv` | Read messages — shows last 3+ messages, new ones marked with `=>` |

---

## How it works

- Each message is a small JSON file committed to a folder in the backend repo
- `gh` handles all auth — no tokens to manage
- New messages are surfaced automatically at the start of each Claude Code prompt
- Works across any number of users sharing the same repo
