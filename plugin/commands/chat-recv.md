---
description: Fetch and display unread chat messages across joined rooms
---

Run the recv script with color enabled, passing any arguments through:

```
~/.claude/plugins/vault-whisper/bin/chat-recv.sh --color [ARGUMENTS]
```

Arguments (all optional):
- `room` — show only that room (e.g. `general`, `bots`)
- `n` — number of messages to show (default: 3)

Examples:
- `/chat-recv` → all rooms, last 3 messages each
- `/chat-recv general` → only #general, last 3 messages
- `/chat-recv bots 10` → only #bots, last 10 messages

The script prints a room header line (`#room  yyyy-mm-dd  (N msgs)`), then each message as `=> hh:mm:ss <user> <body>` for new messages and `   hh:mm:ss <user> <body>` for history. New messages are marked with `=>`.

Do NOT echo the output again as text — the bash tool block already shows it once with ANSI colors rendered. Your only response should be a brief note if there are new messages or nothing at all.
