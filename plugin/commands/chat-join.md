---
description: Join an existing chat room in the configured backend
argument-hint: <room>
---

Run the join script:

```
~/.claude/plugins/vault-whisper/bin/chat-join.sh $ARGUMENTS
```

The room must already exist in the backend's marker file. On success prints `joined #<room> (issue #<n>)`.
