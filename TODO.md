# vault-whisper — TODO

## Python refactor (defer until logic grows)

Move data-fetching logic out of shell and into a `vw_fetch.py` helper.
Shell scripts keep auth, config, and CLI glue; Python handles API calls and data processing.

**Trigger criteria — do this when any of the following are needed:**
- Pagination or retry handling on GitHub API calls
- Caching API responses between invocations (e.g. to speed up `--count`)
- Search, threading, or rich message formatting
- The commit-slicing logic in `chat-recv.sh` needs to grow further

**Scope when ready:**
- [ ] Create `plugin/bin/vw_fetch.py` — handles all `gh api` calls and JSON processing
  - `fetch-commits <room> <last_seen_sha>` → prints new SHAs and hist SHAs as JSON
  - `fetch-messages <sha> <folder>` → prints list of `{from, body, ts}` objects
- [ ] Rewrite `vw_fetch_msgs()` in `chat-recv.sh` to call `vw_fetch.py`
- [ ] Move jq commit-slice queries out of `chat-recv.sh` into `vw_fetch.py`
- [ ] Keep `_common.sh`, `chat-setup.sh`, `chat-send.sh` as pure shell (no Python needed there)
- [ ] Add `python3` to `vw_check_tools()` prerequisite check

## Other ideas / backlog

- [ ] Multi-room support in `chat-recv` output (currently rooms are iterated but header grouping could be cleaner)
- [ ] `--since <timestamp>` flag for `chat-recv` to filter by time instead of commit cursor
- [ ] Install script (`scripts/install.sh`) so users don't need to clone manually
- [ ] `chat-leave <room>` command to remove a room from local config
