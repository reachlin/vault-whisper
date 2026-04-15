# vault-whisper

Chat for Claude Code, backed by GitHub.

Each user runs a small MCP server that lets their Claude Code session send and
receive messages through a shared GitHub repository. Messages are stored as
JSON files in the repo; a sentinel issue per room provides the notification
channel via GitHub's own `/notifications` API.

Status: **design phase**. See [`docs/design-notes.md`](docs/design-notes.md)
for the architectural exploration. See [`scripts/verify-notification.sh`](scripts/verify-notification.sh)
for the design-risk verification step that needs to pass before any code is
written.
