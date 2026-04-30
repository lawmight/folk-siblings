# kit's review checklist

when `cursor-runs.md` has an item with `owner=kit` and `status=awaiting-review`:

## 1. pull context

- `gh pr view <pr_url> --json files,additions,deletions,body,commits`
- `gh pr diff <pr_url>` for the actual diff
- if needed, tail the run log: `node ../../draft/cursor-pair-v0/stream.mjs --agent-id AGENT --run-id RUN`

## 2. review pass (from sibling-agent-channel skill, "reviewing peer-authored draft")

- constants vs docstring cross-check
- directory/path drift
- answer open questions explicitly
- steelman before counter
- propose landing order

## 3. output

write a coordination letter back to ames with one of:
- AGREE: ready for tom to merge. set status=reviewed-approved in cursor-runs.md
- AGREE-with-fix: list the one-line fixes, ames sends follow-up via Agent.prompt. status=reviewed-changes
- REJECT: cite evidence, ames decides abandon or re-spawn. status=reviewed-changes

set `expects_reply: true` — ames needs to act.

## 4. don't

- don't merge. tom holds that button in v0.
- don't close or comment on the PR directly without writing the letter first (letter is the source of truth, github is downstream)
