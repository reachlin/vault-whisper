---
description: Fetch and display unread chat messages across joined rooms
---

Run the recv script with color enabled:

```
~/.claude/plugins/vault-whisper/bin/chat-recv.sh --color
```

The script prints a room header line (`#room  yyyy-mm-dd`), then each message as `=> hh:mm:ss <user> <body>` for new messages and `   hh:mm:ss <user> <body>` for history. Always shows at least 3 recent messages. New messages are marked with `=>`. If there are no new messages it prints `(no new messages)`.

Do NOT echo the output again as text — the bash tool block already shows it once with ANSI colors rendered. Your only response should be a brief note if there are new messages (e.g. "New messages in #general") or nothing at all.
