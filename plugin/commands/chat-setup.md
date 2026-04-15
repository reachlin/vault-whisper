---
description: Configure vault-whisper to use a GitHub repo as its chat backend
argument-hint: <owner/repo> [--init]
---

Run the setup script for vault-whisper:

```
~/.claude/plugins/vault-whisper/bin/chat-setup.sh $ARGUMENTS
```

Usage:
- `/chat-setup owner/repo` — join an existing vault-whisper backend.
- `/chat-setup owner/repo --init` — create and initialize a new backend (first user on a team).

Report the script's output verbatim. If the script prints an error, surface it clearly and suggest the corrective command it mentions.
