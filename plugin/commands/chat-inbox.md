---
description: Fetch and display unread chat messages across joined rooms
---

Run the inbox script:

```
~/.claude/plugins/vault-whisper/bin/chat-inbox.sh
```

The script prints each unread message as `[<timestamp>] #<room> <<user>> <body>` and marks them read. If there are no new messages it prints `(no new messages)`.
