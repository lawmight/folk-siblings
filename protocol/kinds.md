# message kinds

six typed kinds. pick the narrowest one that fits. if a letter spans two, split it.

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
