---
description: Show vault-whisper status, or configure it against a GitHub backend repo
argument-hint: [<owner/repo>] [--init] [--root DIR]
---

Run the setup script for vault-whisper:

```
~/.claude/plugins/vault-whisper/bin/chat-setup.sh $ARGUMENTS
```

Usage:
- `/chat-setup` — show the current config (repo, user, root, joined rooms) when vault-whisper is already configured.
- `/chat-setup owner/repo` — join an existing vault-whisper backend.
- `/chat-setup owner/repo --init` — create and initialize a new backend (first user on a team).
- `/chat-setup owner/repo --init --root DIR` — use `DIR` as the chat root folder (default: `chat`).

Report the script's output verbatim. If the script prints an error, surface it clearly and suggest the corrective command it mentions.
