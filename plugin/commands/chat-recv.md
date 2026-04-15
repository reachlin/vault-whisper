---
description: Fetch and display unread chat messages across joined rooms
---

Run the recv script with ANSI color forced on so the message body renders with the blue background:

```
~/.claude/plugins/vault-whisper/bin/chat-recv.sh --color
```

The script prints a room header line (`#room  yyyy-mm-dd`), then each message as `=> hh:mm:ss <user> <body>` for new messages and `   hh:mm:ss <user> <body>` for history. Always shows at least 3 recent messages. New messages are marked with `=>`. The message body is shown with a blue background and white text via ANSI escape codes. If there are no new messages it prints `(no new messages)`.

Report the script's output verbatim so the terminal can render the colors.
