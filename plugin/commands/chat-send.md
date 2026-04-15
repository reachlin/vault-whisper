---
description: Send a chat message to a room
argument-hint: [room] <message>
---

Run the send script:

```
~/.claude/plugins/vault-whisper/bin/chat-send.sh $ARGUMENTS
```

The room is optional — if omitted (or if the first word isn't a joined room), the message goes to the default room (`#general`). On success the script prints `sent to #<room>`. Report any error from the script.
