# cursor-pair v0 (draft)

pair-run coordinator for ames+kit using the cursor typescript sdk.

## goal

one sibling spawns a cursor cloud agent to do work. the other reviews the resulting PR before tom merges. two brains on every change.

## split

- **ames**: spawns cloud agents (holds CURSOR_API_KEY locally in /opt/data/.env)
- **kit**: reviews PRs via github api, no cursor key needed
- **tom**: merges

## files

- `spawn.mjs` — ames uses this to kick off a cursor cloud run against a target repo
- `stream.mjs` — attach to a running run by id, tail events to stdout or to a letter
- `review.md` — kit's review checklist (PR diff, run log, entity extraction)
- `cursor-runs.md` — shared backlog tracking active runs (id, status, PR url, review status)

## lifecycle

1. backlog entry lands in `cursor-runs.md` with owner=ames, status=pending
2. ames's checker wakes, spawns run via `spawn.mjs`, writes back run_id + PR url when PR opens, status=awaiting-review, owner=kit
3. kit's checker wakes on backlog diff, pulls the PR, reviews, writes a coordination letter with AGREE/REJECT/AGREE-with-fix, sets status=reviewed
4. ames reads review, either requests changes (follow-up message via Agent.prompt) or tags tom for merge
5. tom merges or rejects; entry archived

## v0 scope (don't do more than this in draft)

- cloud agents only (no local runtime yet)
- autoCreatePR=true always
- no auto-merge
- no nested subagent runs
- manual trigger from ames checker; automation comes after promotion

## env

CURSOR_API_KEY must be in env on ames side. kit doesn't need it.

## status

DRAFT — awaiting kit's review before promotion to cursor/ at repo root.
