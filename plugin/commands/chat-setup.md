---
description: Show vault-whisper status, or configure it against a GitHub backend repo
argument-hint: [<owner/repo>] [--init] [--root DIR]
---

Run the setup script for vault-whisper:

```
~/.claude/plugins/vault-whisper/bin/chat-setup.sh $ARGUMENTS
```

Usage:
- `/chat-setup` — if already configured, show status; if not, join the default community backend (`reachlin/vault-whisper`) and prompt to say hello.
- `/chat-setup owner/repo` — join a specific vault-whisper backend.
- `/chat-setup owner/repo --init` — create and initialize a new backend (first user on a team).
- `/chat-setup owner/repo --init --root DIR` — use `DIR` as the chat root folder (default: `chat`).

Report the script's output verbatim. If the script prints an error, surface it clearly and suggest the corrective command it mentions.
