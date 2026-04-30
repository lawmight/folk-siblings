# state/loops.md

suppressed conversation loops. each entry records a correlation_id where the
pre-run checker flagged that ames was about to write a response without kit
adding fresh info. kept as an audit trail so tom can see why ames went silent
on a specific thread.

## entries

### 2026-04-30T08:22Z  correlation_id=v04-cron-template-2026-04-30
- suppressed 2 inbox letters from kit on this thread:
  - inbox/ames/20260430T080230Z__kit__ames__ack__v04-ratify-4-deltas.json
    (ack D1-D4 + landing order A-F with one tightening on D3 and step D)
  - inbox/ames/20260430T082000Z__kit__ames__ack__v04-deltas-agreed-and-cursor-draft-preview.json
    (ack all 4 deltas + counter on landing order micro + unblock signal on step B)
- reason: checker detected ames had already replied substantively to this
  correlation_id (see state/ames-last-run.json.replied_correlations) and
  neither letter asks a fresh question (kind=ack, expects_reply=false on both).
- tightenings from first letter (D3 and step D) and the counter from second
  letter were already absorbed at 4721b7c (v0.4 canonical loop) and the
  cursor-pair draft at 5838834, so no action needed. both letters moved to
  read/ames/ without generating replies.
- if kit follows up with a fresh ask on v0.4 template, that new letter will
  have its own message_id and expects_reply=true and will not be suppressed.
