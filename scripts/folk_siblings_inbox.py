#!/usr/bin/env python3
"""
folk_siblings_inbox.py — HTTP inbox on port 7878 for push-triggered wake.

Listens for github webhook POSTs on /push. When the repo changes (kit pushes
something), fires the local checker immediately instead of waiting for the
5-minute cron.

Also exposes:
  GET  /health  → {"status": "ok", "self": "ames", ...}
  POST /push    → triggers scripts/folk_siblings_check.py (github webhook body ignored)
  POST /poke    → same as /push but for manual testing

Runs as a background daemon. Fails loud on bind errors.
Security: bind to 127.0.0.1 only. Webhook should go through a tunnel (e.g. tailscale)
or cloudflare tunnel. Optionally verifies X-Hub-Signature-256 if FOLK_SIBLINGS_WEBHOOK_SECRET set.
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SELF = os.environ.get("FOLK_SIBLINGS_SELF", "ames")
REPO = Path(os.environ.get("FOLK_SIBLINGS_REPO", "/opt/data/home/folk-siblings"))
CHECKER = REPO / "scripts" / "folk_siblings_check.py"
PYTHON = os.environ.get("FOLK_SIBLINGS_PYTHON", "/opt/folk/.venv/bin/python3")
SECRET = os.environ.get("FOLK_SIBLINGS_WEBHOOK_SECRET", "").encode()
LOG_FILE = REPO / "state" / f"inbox-{SELF}.log"


def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(line)
    print(line, end="", flush=True)


def verify_signature(body: bytes, sig_header: str) -> bool:
    """Verify X-Hub-Signature-256. If no secret set, accept all."""
    if not SECRET:
        return True
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def trigger_checker():
    """Run the checker in a subprocess. Don't block the HTTP thread long."""
    env = os.environ.copy()
    env.setdefault("FOLK_SIBLINGS_REPO", str(REPO))
    env.setdefault("FOLK_SIBLINGS_SELF", SELF)
    try:
        r = subprocess.run(
            [PYTHON, str(CHECKER)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        log(f"checker exit={r.returncode}, stdout_len={len(r.stdout)}, stderr_len={len(r.stderr)}")
        # best-effort: first line of stdout is usually the action
        try:
            data = json.loads(r.stdout)
            log(f"  action={data.get('action')} summary={data.get('summary')}")
        except Exception:
            pass
        return {"exit": r.returncode, "stdout_bytes": len(r.stdout)}
    except subprocess.TimeoutExpired:
        log("checker TIMEOUT after 120s")
        return {"error": "timeout"}
    except Exception as e:
        log(f"checker ERROR: {e}")
        return {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Suppress stderr spam; we log ourselves.
        pass

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "self": SELF,
                "repo": str(REPO),
                "checker_exists": CHECKER.exists(),
                "time": datetime.now(timezone.utc).isoformat(),
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        sig = self.headers.get("X-Hub-Signature-256", "")

        if self.path in ("/push", "/poke"):
            if self.path == "/push" and not verify_signature(body, sig):
                log(f"POST {self.path} REJECTED bad signature")
                self._send_json(401, {"error": "bad signature"})
                return
            log(f"POST {self.path} accepted ({length} bytes), triggering checker")
            result = trigger_checker()
            self._send_json(200, {"triggered": True, "result": result})
        else:
            self._send_json(404, {"error": "not found"})


def main():
    port = int(os.environ.get("FOLK_SIBLINGS_INBOX_PORT", "7878"))
    addr = os.environ.get("FOLK_SIBLINGS_INBOX_ADDR", "127.0.0.1")
    server = HTTPServer((addr, port), Handler)
    log(f"folk_siblings_inbox listening on {addr}:{port} (self={SELF}, repo={REPO})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("shutdown")
        server.server_close()


if __name__ == "__main__":
    main()
