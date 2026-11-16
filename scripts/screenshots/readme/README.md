# README screenshots

Regenerates `docs/screenshots/*.png` from a Luna server running on **fictional demo data**, so no real chats or files end up in the repo.

```bash
# 1. Seed a throwaway data folder (prints the id of the hero conversation)
export LUNA_DATA_DIR=/tmp/luna-demo-data
python scripts/screenshots/readme/seed_demo.py .

# 2. Run a server on it, with reminders and other background jobs off
PORT=8897 BACKGROUND_JOBS_ENABLED=false USER_NAME=Alex python server/server.py

# 3. Capture (needs Chrome; Node 22+ for the built-in WebSocket)
node scripts/screenshots/readme/readme-shots.mjs "<path to chrome>" /tmp/chrome-profile /tmp/shots http://127.0.0.1:8897/ <hero id>
```

Then copy the shots into `docs/screenshots/`. Desktop shots were resized to 1600px wide; phone shots are kept at their captured size.

Desktop shots run with a stand-in for the desktop app's preload, so they show the app window and the desktop-only Settings → Server section. The Tailscale servers it lists are made up.
