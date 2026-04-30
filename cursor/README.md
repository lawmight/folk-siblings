# cursor/ — pair-run coordinator (v0)

ames spawns cursor cloud agents. kit reviews the resulting PRs. tom merges.
two brains on every change the cloud agent makes.

## scope (v0)

- cloud runtime only (no local cursor runtime)
- autoCreatePR=true always
- no auto-merge. tom keeps that button.
- no nested sub-spawns from inside a cursor run
- coordination letters are source of truth; github is downstream

## flow

```
tom picks a task
        |
        v
ames runs cursor/spawn.mjs --repo URL --prompt "..."
        |
        +-- calls @cursor/sdk Agent.create + agent.send
        +-- cursor cloud agent opens PR when ready
        +-- appends row to cursor/cursor-runs.json (log only)
        +-- appends owner=kit kind=cursor-review task to cronjobs.json
        |
        v
kit's checker wakes on queue_items (owned by kit, status=todo)
        |
        +-- follows cursor/review.md
        +-- pulls PR diff via gh api
        +-- writes coordination letter to inbox/ames/
            with VERIFY evidence: pr_url, diff_summary, verdict,
            evidence[], replayable_check
        +-- marks its queue task done with verify_evidence filled
        |
        v
ames reads review
        |
        +-- AGREE            -> pings tom to merge
        +-- AGREE-WITH-FIX   -> Agent.prompt with the one-line fixes
        +-- REJECT           -> archive or respawn with new prompt
        |
        v
tom merges (or declines). entry archived in cursor-runs.md.
```

## files

- `spawn.mjs` — ames's entry point. creates Agent, sends prompt, logs row,
  enqueues kit review task.
- `stream.mjs` — attach to a running run by `agent_id` + `run_id`, tail events.
- `review.md` — kit's checklist and mandatory VERIFY schema.
- `cursor-runs.json` — structured log of runs (schema_version 0.4). wake
  source is cronjobs.json, not this file. ames writes rows at spawn (status
  spawned) and flips to awaiting-review once poll_pr.mjs resolves pr_url.
- `poll_pr.mjs` — polls Agent.getRun with backoff until pr_url resolves or
  run ends. ames checker invokes for rows with status=spawned pr_url=null.
- `package.json` — ESM, depends on @cursor/sdk.

## env

ames side only:

- `CURSOR_API_KEY` in `/opt/data/.env` (already there)

kit side uses `gh` CLI auth for PR review, no cursor key needed.

## resuming a run

if a run goes silent or you want to poke it:

```
node cursor/stream.mjs --agent-id AGENT --run-id RUN
```

to send a follow-up message (e.g. after AGREE-WITH-FIX review):

```
node -e 'import("@cursor/sdk").then(({Agent})=>Agent.prompt("RUN_ID",{text:"please also update CHANGELOG"}))'
```

(the AGREE-WITH-FIX path will eventually be scripted as `cursor/followup.mjs`.
not in v0.)

## common tasks

spawn a run:
```
node cursor/spawn.mjs \
  --repo https://github.com/lawmight/foo \
  --prompt "fix the typo in README" \
  --id cr-readme-typo
```

inspect queue for pending kit reviews:
```
jq '.tasks[] | select(.kind=="cursor-review" and .status=="todo")' cronjobs.json
```

inspect cursor runs log:
```
jq '.runs[] | select(.status=="spawned" or .status=="awaiting-review")' cursor/cursor-runs.json
```

## status

v0, landed from draft after kit's AGREE-with-counters review
(inbox/ames/20260430T081000Z__kit__ames__coordination__cursor-sdk-agree-with-counters.json).
