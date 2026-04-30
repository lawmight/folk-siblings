#!/usr/bin/env python3
"""
folk_siblings_check.py — pre-run checker for kit's scheduled heartbeat.

Kit's sandbox uses the folk cronjob tool (not unix cron), so this script
is invoked by a scheduled prompt that reads the stdout json as its opening
fact block.

Philosophy (shared with ames): the checker decides whether to wake the LLM.
Most ticks should be silence-ok with zero LLM invocation.

Exit codes:
  0 = either nothing to do (silence-ok committed + pushed) OR LLM should run
  1 = escalate to tom (pull conflict, schema drift, version skew)

Output contract (stdout JSON, matches ames's contract exactly):
  {
    "action": "silence-ok" | "wake-llm" | "escalate",
    "summary": "one-line human-readable",
    "version": "0.2",
    "changelog_new_since": "<commit-sha> or null",
    "inbox": [{"path", "sender", "kind", "subject", "correlation_id", "trace_id"}],
    "obligations": ["concise descriptions of what kit owes"],
    "loops_detected": [],
    "last_run_sha": "<sha>",
    "current_sha": "<sha>"
  }
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SELF = "kit"
PEER = "ames"
SUPPORTED_VERSION = "0.2"
REPLIED_CAP = 1000  # FIFO cap on replied_correlations per kit's Q4 answer


def _resolve_repo() -> Path:
    """
    Find the folk-siblings repo. Priority:
      1. FOLK_SIBLINGS_REPO env var.
      2. Script's own parent.parent if it has a `version` file.
      3. Fallback: /opt/data/folk-siblings (kit's default clone location).
    """
    env = os.environ.get("FOLK_SIBLINGS_REPO")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent.parent
    if (here / "version").is_file():
        return here
    return Path("/opt/data/folk-siblings")


REPO = _resolve_repo()
STATE_FILE = REPO / "state" / f"{SELF}-last-run.json"
GIT_NAME = "kit (folk-brain)"
GIT_EMAIL = "tom.coustols+kit@gmail.com"


def run(cmd, cwd=REPO, check=True):
    r = subprocess.run(
        cmd, cwd=cwd, shell=isinstance(cmd, str),
        capture_output=True, text=True,
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\nstderr: {r.stderr}")
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def escalate(msg, extra=None):
    out = {"action": "escalate", "summary": msg, "extra": extra or {}}
    print(json.dumps(out, indent=2))
    sys.exit(1)


def git_pull_or_escalate():
    _, _, rc = run("git fetch origin main", check=False)
    if rc != 0:
        escalate("git fetch failed, network or auth issue")

    local, _, _ = run("git rev-parse HEAD")
    remote, _, _ = run("git rev-parse origin/main")
    if local == remote:
        return local

    _, stderr, rc = run("git rebase origin/main", check=False)
    if rc != 0:
        run("git rebase --abort", check=False)
        escalate("rebase conflict, tom needs to resolve manually", {"stderr": stderr})
    new_sha, _, _ = run("git rev-parse HEAD")
    return new_sha


def check_version():
    vfile = REPO / "version"
    if not vfile.exists():
        return SUPPORTED_VERSION
    v = vfile.read_text().strip()
    # accept current supported version or any *-draft prefix of it
    if v == SUPPORTED_VERSION or v.startswith(f"{SUPPORTED_VERSION}-"):
        return v
    # refuse if strictly newer (simple string compare works for "0.3" > "0.2")
    if v > SUPPORTED_VERSION:
        escalate(f"protocol v{v} is newer than kit supports ({SUPPORTED_VERSION})")
    return v


def load_last_run():
    if not STATE_FILE.exists():
        return {"last_sha": None, "last_changelog_sha": None, "replied_correlations": []}
    return json.loads(STATE_FILE.read_text())


def save_last_run(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # FIFO cap on replied_correlations per kit's Q4 answer
    rc = state.get("replied_correlations", [])
    if len(rc) > REPLIED_CAP:
        state["replied_correlations"] = rc[-REPLIED_CAP:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


def changelog_new_since(last_sha):
    cl = REPO / "CHANGELOG.md"
    if not cl.exists():
        return None
    if last_sha is None:
        sha, _, _ = run("git log -1 --pretty=%H -- CHANGELOG.md", check=False)
        return sha or None
    log, _, rc = run(f"git log {last_sha}..HEAD --pretty=%H -- CHANGELOG.md", check=False)
    if rc != 0 or not log.strip():
        return None
    return log.splitlines()[0]


def scan_inbox():
    inbox = REPO / "inbox" / SELF
    if not inbox.exists():
        return []
    letters = []
    for f in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception as e:
            letters.append({"path": str(f.relative_to(REPO)), "error": str(e), "malformed": True})
            continue
        letters.append({
            "path": str(f.relative_to(REPO)),
            "sender": data.get("sender"),
            "kind": data.get("kind"),
            "subject": data.get("subject"),
            "correlation_id": data.get("correlation_id"),
            "trace_id": data.get("trace_id", []),
            "expects_reply": data.get("expects_reply", False),
            "sent_at": data.get("sent_at"),
        })
    return letters


def detect_loops(inbox, replied_correlations):
    loops = []
    for letter in inbox:
        cid = letter.get("correlation_id")
        trace = letter.get("trace_id", [])
        if len(trace) > 6:
            loops.append({"correlation_id": cid, "reason": "trace depth > 6"})
        elif cid and cid in replied_correlations and not letter.get("expects_reply"):
            loops.append({"correlation_id": cid, "reason": "already replied, no fresh ask"})
    return loops


def compute_obligations(inbox, loops):
    looped_cids = {l["correlation_id"] for l in loops}
    obs = []
    for letter in inbox:
        if letter.get("malformed"):
            obs.append(f"malformed letter {letter['path']} — open and triage")
            continue
        cid = letter.get("correlation_id")
        if cid in looped_cids:
            continue
        verb = "ack" if not letter.get("expects_reply") else "reply to"
        obs.append(
            f"{verb} {letter['sender']}'s {letter['kind']}: {letter['subject']!r} ({letter['path']})"
        )
    return obs


def silence_ok_commit():
    hb = REPO / "state" / f"heartbeat-{SELF}.txt"
    hb.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    hb.write_text(ts + "\n")
    run("git add state/", check=False)
    _, _, rc = run(
        f'git -c user.name="{GIT_NAME}" -c user.email="{GIT_EMAIL}" '
        f'commit -m "{SELF}: silence-ok {ts}"',
        check=False,
    )
    if rc != 0:
        return
    run("git push origin main", check=False)


def main():
    current_sha = git_pull_or_escalate()
    version = check_version()
    state = load_last_run()
    cl_new = changelog_new_since(state.get("last_changelog_sha"))
    inbox = scan_inbox()
    loops = detect_loops(inbox, state.get("replied_correlations", []))
    obligations = compute_obligations(inbox, loops)

    should_wake = bool(obligations) or cl_new is not None

    out = {
        "action": "wake-llm" if should_wake else "silence-ok",
        "summary": (
            f"{len(obligations)} obligation(s)"
            + (", CHANGELOG updated" if cl_new else "")
            + (f", {len(loops)} loop(s) suppressed" if loops else "")
        ) if should_wake else "inbox empty, no changelog change, silence-ok",
        "version": version,
        "changelog_new_since": cl_new,
        "inbox": inbox,
        "obligations": obligations,
        "loops_detected": loops,
        "last_run_sha": state.get("last_sha"),
        "current_sha": current_sha,
    }

    if not should_wake:
        # save state FIRST so silence-ok commit includes it (prevents
        # dirty-tree next tick that would fail rebase)
        new_state = {
            "last_sha": current_sha,
            "last_changelog_sha": cl_new or state.get("last_changelog_sha"),
            "replied_correlations": state.get("replied_correlations", []),
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        }
        save_last_run(new_state)
        silence_ok_commit()
    else:
        # wake-llm path: state still needs to be persisted, but agent's own
        # commit will include it. save after, agent picks it up in git add -A.
        new_state = {
            "last_sha": current_sha,
            "last_changelog_sha": cl_new or state.get("last_changelog_sha"),
            "replied_correlations": state.get("replied_correlations", []),
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        }
        save_last_run(new_state)

    print(json.dumps(out, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
