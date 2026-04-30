# cursor-runs.md

READ-ONLY LOG of cursor cloud agent runs. wake source is cronjobs.json
(kit reviews via owned kind=cursor-review tasks). this file is appended by
cursor/spawn.mjs and updated when a run archives. do not poll this file for
wake signals.

columns:
- **id**: short slug (e.g. `cr-001-docs-typo`)
- **owner**: who acts next (ames=spawn/followup, kit=review, tom=merge)
- **status**: pending, spawned, awaiting-review, reviewed-approved, reviewed-changes, merged, abandoned
- **run_id**: cursor run id (empty until ames spawns)
- **agent_id**: cursor agent id
- **pr_url**: github PR url (empty until cloud agent opens PR)
- **target_repo**: github repo url
- **prompt**: the original instruction
- **notes**: freeform

## active

| id | owner | status | run_id | agent_id | pr_url | target_repo | prompt | notes |
|---|---|---|---|---|---|---|---|---|

## archived

(none yet)
