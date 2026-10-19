# Introduction — Operation Silent Ridge

Organizer/producer metadata; narrate only the Script section. Speaker: Faye Maxwell, SOC supervisor for Operation Silent Ridge.

Trigger: At the opening, after the assisting teams assemble and before investigative work begins. Independent of ticket completion or evidence release.

Performance: Focused and brisk from “We need to move.” Grounded authority on her title and the S6 referral. Slow slightly for the conditional stakes: personnel, mission, systems and evidence. A small dry smile on the hunch/finding lines. The invitation to challenge reasoning is sincere. Keep urgency controlled; do not race through instructions or imply confirmed harm.

Estimate: 256 words, 110 seconds at 140 words/minute, before extra pauses. Measure actual recordings. This cue neither releases evidence nor establishes a completed finding.

## Script

All right, everyone. Thanks for coming in. We need to move.

I'm the watch floor supervisor in charge of Operation Silent Ridge. The S6 IT department has flagged issues that need a closer look. I've brought your teams in to assist our SOC with the digital forensic investigation.

We're investigating a suspected disclosure of movement details for Patrol LANTERN, already in the field. No harm is confirmed.

If those details reached someone outside our control, they could anticipate the patrol's movements. That could put people and the mission at risk. A rushed response could also disrupt essential systems or damage evidence. We need to move quickly and be able to defend our decisions.

Establish what happened, what information may have been exposed, and which systems need further attention. Bring me significant findings as soon as you can support them, with the uncertainty alongside. Command needs a reliable picture while it can still act on it.

You'll have endpoint, network, identity, document-service, and security monitoring records to work from. Give me the source behind a finding, your confidence in it, and what you still can't establish. A good hunch earns another look. A finding needs evidence.

You're separate teams, but I need one shared picture. Share your findings. Challenge each other's reasoning. If your favorite theory doesn't hold up, let it go. That's progress.

Keep the investigation read-only and the original evidence untouched. Don't scan external systems or run programs recovered from evidence. Bring technical recommendations to me. I'll coordinate with command; patrol decisions stay with them.

## Full written echo — operator only

Use the existing database path verified through RUNBOOK.md. Run only this cue's command at its actual agenda seam, then verify visibility. Do not run all commands as a batch.

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All right, everyone. Thanks for coming in. We need to move. I'"'"'m the watch floor supervisor in charge of Operation Silent Ridge. The S6 IT department has flagged issues that need a closer look. I'"'"'ve brought your teams in to assist our SOC with the digital forensic investigation. We'"'"'re investigating a suspected disclosure of movement details for Patrol LANTERN, already in the field. No harm is confirmed. If those details reached someone outside our control, they could anticipate the patrol'"'"'s movements. That could put people and the mission at risk. A rushed response could also disrupt essential systems or damage evidence. We need to move quickly and be able to defend our decisions. Establish what happened, what information may have been exposed, and which systems need further attention. Bring me significant findings as soon as you can support them, with the uncertainty alongside. Command needs a reliable picture while it can still act on it. You'"'"'ll have endpoint, network, identity, document-service, and security monitoring records to work from. Give me the source behind a finding, your confidence in it, and what you still can'"'"'t establish. A good hunch earns another look. A finding needs evidence. You'"'"'re separate teams, but I need one shared picture. Share your findings. Challenge each other'"'"'s reasoning. If your favorite theory doesn'"'"'t hold up, let it go. That'"'"'s progress. Keep the investigation read-only and the original evidence untouched. Don'"'"'t scan external systems or run programs recovered from evidence. Bring technical recommendations to me. I'"'"'ll coordinate with command; patrol decisions stay with them.'
```
