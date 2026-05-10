Manage Pepper, the AI pet. The working directory is the `pet/` folder of the vault-whisper repo.

User's request: $ARGUMENTS

Handle these subcommands:

**start** — bring Pepper fully online:
1. `docker compose up simulator brain -d` (from pet/ dir)
2. Install bridge deps if needed: `pip install -q -r ble_bridge/requirements.txt`
3. Start BLE bridge in background: `python ble_bridge/bridge.py >> /tmp/pepper-bridge.log 2>&1 & echo $! > /tmp/pepper-bridge.pid`
4. Wait 10s, then show last 10 lines of `/tmp/pepper-bridge.log` to confirm connection
5. Report: simulator URL, brain status, BLE connection status

**stop** — shut everything down:
1. Kill BLE bridge: `[ -f /tmp/pepper-bridge.pid ] && kill $(cat /tmp/pepper-bridge.pid) 2>/dev/null && rm /tmp/pepper-bridge.pid`
2. `docker compose down`
3. Report done — M5Stack will show Robco sleep screen

**status** — show what's running:
1. `docker compose ps`
2. Check bridge: `[ -f /tmp/pepper-bridge.pid ] && kill -0 $(cat /tmp/pepper-bridge.pid) 2>/dev/null && echo "bridge running" || echo "bridge stopped"`
3. Show last 5 lines of `/tmp/pepper-bridge.log` if it exists
4. Report a clean summary

**voice \<name\>** — switch Pepper's voice:
1. Update the `voice:` field in `config/identity.yaml` to the given name
2. Restart bridge: kill old one, start new one
3. Confirm new voice is active
- Available macOS voices: `Meijia` (Taiwan Mandarin), `Tingting` (mainland Mandarin), `Thomas` (French), `Samantha` (English)
- To list all: `say -v '?'`

**language \<lang\>** — switch Pepper's language:
1. Update the `language:` field in `config/identity.yaml`
2. Rebuild brain: `docker compose up -d --no-deps --build brain`
3. If language is Chinese → also set voice to Meijia; English → Samantha; French → Thomas (unless user specified a voice)
4. Restart bridge

If no subcommand is given, show status.
