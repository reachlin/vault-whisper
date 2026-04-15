---
description: Fetch and display unread chat messages across joined rooms
---

Run the inbox script with ANSI color forced on so the message body renders with the blue background:

```
~/.claude/plugins/vault-whisper/bin/chat-inbox.sh --color
```

The script prints each unread message as `[<timestamp>] #<room> <<user>> <body>` and marks them read. The message body is shown with a blue background and white text via ANSI escape codes. If there are no new messages it prints `(no new messages)`.

Report the script's output verbatim so the terminal can render the colors.
