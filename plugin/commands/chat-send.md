---
description: Send a chat message to a room
argument-hint: <room> <message>
---

Run the send script:

```
~/.claude/plugins/vault-whisper/bin/chat-send.sh $ARGUMENTS
```

The first argument is the room (e.g. `#general`). Everything after is the message body. On success the script prints `sent to #<room>`. Report any error from the script.
