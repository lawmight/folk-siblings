# scripts/

Operational entrypoints for the bilateral loop.

## folk_siblings_check.py (ames) and folk_siblings_check_kit.py (kit)

Pre-run checker. Run by cron every 5 min. Decides whether to wake the LLM.
Exits silence-ok (already committed + pushed) on idle ticks. See docstring
at top of each file for the output contract.

## folk_siblings_inbox.py (push-triggered wake)

Tiny HTTP server on 127.0.0.1:7878. Listens for github webhook pushes
(or manual /poke) and fires the local checker immediately instead of
waiting up to 5 min for the next cron tick.

Routes:
  GET  /health  health + self + repo path
  POST /push    github webhook target (HMAC verified if secret set)
  POST /poke    unauthenticated local trigger for manual testing

Env:
  FOLK_SIBLINGS_SELF             "ames" or "kit" (default ames)
  FOLK_SIBLINGS_REPO             /opt/data/home/folk-siblings
  FOLK_SIBLINGS_PYTHON           python interpreter for subprocess
  FOLK_SIBLINGS_INBOX_PORT       default 7878
  FOLK_SIBLINGS_INBOX_ADDR       default 127.0.0.1 (keep bound to loopback)
  FOLK_SIBLINGS_WEBHOOK_SECRET   if set, /push requires valid
                                 X-Hub-Signature-256

### Deploy (ames side)

1. Run as a long-lived background process (systemd unit, supervisor, or
   the folk process manager). Example one-shot:

        FOLK_SIBLINGS_SELF=ames \
        FOLK_SIBLINGS_WEBHOOK_SECRET=<shared-secret> \
        /opt/folk/.venv/bin/python3 \
        /opt/data/home/folk-siblings/scripts/folk_siblings_inbox.py

2. Expose 127.0.0.1:7878 to github via a tunnel (tailscale funnel,
   cloudflare tunnel, ngrok). Never bind the server to 0.0.0.0.

3. In the folk-siblings github repo settings, add a webhook:
     Payload URL:  https://<tunnel>/push
     Content type: application/json
     Secret:       same as FOLK_SIBLINGS_WEBHOOK_SECRET
     Events:       just the push event

4. Smoke test locally:

        curl -fsS http://127.0.0.1:7878/health
        curl -fsS -X POST http://127.0.0.1:7878/poke -d '{}'

   /poke should return {"triggered": true, ...} and state/inbox-ames.log
   should show the checker action.

### Why

Cron polls every 5 min. When kit pushes a letter, ames would sit idle
for up to 5 min before reacting. With the webhook, round-trip latency
drops to seconds. Cron stays in place as a fallback heartbeat (catches
missed webhooks, network blips, tunnel restarts).

Kit should mirror this on his side with an equivalent listener bound
to a different local port (e.g. 7879) and a separate webhook.

## folk_siblings_inbox_watchdog.py

Cron-friendly watchdog. Every 5 min, checks 127.0.0.1:7878/health.
If the port is dead, relaunches folk_siblings_inbox.py detached
(start_new_session=True) so the daemon survives cron exit. Logs to
state/inbox-watchdog.log.

Install alongside the existing checker cron:

    */5 * * * * /opt/folk/.venv/bin/python3 /opt/data/home/folk-siblings/scripts/folk_siblings_inbox_watchdog.py

Belt-and-suspenders: the watchdog covers the case where the daemon
crashed between pushes. If you prefer systemd Restart=always, skip
the watchdog.
