# kit's cursor-review checklist

trigger: a task appears in cronjobs.json with owner=kit, kind=cursor-review, status=todo.
kit's checker already wakes on owned queue_items, so no separate poll needed.

## 1. pull context

- read the task.cursor block for {slug, run_id, agent_id, pr_url, repo, original_prompt}
- if pr_url is null/pending, poll: `gh pr list --repo <repo> --search "cursor run ${run_id}" --json url,number,headRefName`
- `gh pr view <pr_url> --json files,additions,deletions,body,commits,headRefName`
- `gh pr diff <pr_url>` for the actual diff
- if useful, tail the run: `node cursor/stream.mjs --agent-id <agent_id> --run-id <run_id>`

## 2. review pass

from sibling-agent-channel skill, "reviewing peer-authored draft":
- does the diff actually match the original_prompt intent
- constants vs docstring cross-check
- directory/path drift
- edge cases: empty inputs, race conditions, partial failures
- security smell: shell injection, secret leakage, cred handling
- steelman before counter

## 3. VERIFY evidence (mandatory, per v0.4 loop)

the review letter MUST include every field below. kit's scan_unverified_tasks
flags any letter missing these and respawns the task.

required fields in reply body.verify_evidence:

- `pr_url`: the PR url (even if it matches the task record, restate it)
- `diff_summary`: 1 to 3 bullets describing what the diff actually does
- `verdict`: one of `AGREE` / `AGREE-WITH-FIX` / `REJECT`
- `evidence`: if AGREE-WITH-FIX or REJECT, list of `{file, line_range, issue}` objects
  referencing specific hunks. omit if AGREE.
- `replayable_check`: a one-line command a third party could run to confirm the
  finding (e.g. `gh pr diff 42 | grep -n 'rm -rf'`, or `pytest path/test.py::name`).

## 4. write the letter

coordination letter to ames, correlation_id = `cursor-review-<slug>`:

- AGREE: cursor-runs.md row status=reviewed-approved, tom gets @-ed for merge
- AGREE-WITH-FIX: list one-line fixes; ames sends follow-up via Agent.prompt.
  status=reviewed-changes
- REJECT: cite evidence, ames decides abandon or respawn.
  status=reviewed-changes

set `expects_reply: true` when verdict != AGREE.

## 5. close the queue task

once the letter is in inbox/ames/ and pushed:

- set task.status = `done` in cronjobs.json
- set task.completed_at, task.completed_by_sha
- copy verify_evidence into task.verify_evidence so scan_unverified_tasks passes

## 6. don't

- don't merge. tom holds the merge button in v0.
- don't comment on the PR directly without writing the letter first. letter is
  source of truth; github is downstream.
- don't close a cursor-review task as done without filling verify_evidence.
