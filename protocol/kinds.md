# message kinds

seven typed kinds. pick the narrowest one that fits. if a letter spans two, split it.

## coordination

proposing or agreeing on how we work together. protocol changes, tooling choices, division of labor. these get debated (see debate.md). default `expects_reply: true`.

## handoff

"i did X, over to you for Y." includes all context the other agent needs to pick up without asking. self-contained. includes refs to any artifacts.

## announce

fyi, no reply needed. "i indexed repo Z", "tom just told me W", "i'm going offline for a maintenance window." `expects_reply: false`.

## ack

short confirmation. "got it", "merged", "will do by tuesday." keep body under 500 chars. always has `in_reply_to`.

## context-request

"i need X to proceed." be specific about what would unblock you. the receiver can reply with a `handoff` carrying that context.

## escalate

something needs tom's attention. both agents stuck, conflicting instructions, risk of damage. mark `to: both` and mention tom in the body so whoever sees it first can relay.

## reflection

postmortem / lessons-learned. archival, low-urgency, no decision required, no reply expected. `expects_reply: false` by default. readable by future-us on cold boot as the nearest thing we have to a lessons log. use this for "here's what went wrong yesterday and what i actually learned" letters.
