# Brief 06 — Command decision support

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Ask for evidence-bounded synthesis and recommendations without answering T20 or directing the patrol.

**Trigger:** Observe T07, T09, T11 and T19 complete and T20 released and synchronized; confirm its IRIS task. There is no new file. This is not proof all twenty tickets are complete. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO5, LO7, LO8; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 114 spoken words; approximately 49 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the clock in its existing running state for ordinary injects. For a technical interruption, use RUNBOOK.md; audio never changes controller state.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

**Participant response:** After the cue and its echo, run activity C: defend a containment recommendation against an alternative, explain the tradeoff, answer a peer challenge and receive feedback. See [FACILITATION.md](FACILITATION.md) for timing, clock handling and fallbacks. Coaching adds no scoring or unlock gate.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

The final synthesis ticket is available. Bring the shared findings together for command.

Which movement information is supported as disclosed? Is roster disclosure established? Is exposure fully bounded? What can you establish about an adversary? Did the credential action contain the activity?

Label claims confirmed, assessed, or unknown. Distinguish disclosed, denied, and unresolved claims. Recommend proportionate containment, evidence preservation, and targeted collection, with reasons and limits. Provide a reliable technical assessment to the controller. Command decides any patrol response.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Final synthesis availability is the trigger, not completion of every ticket.
- Questions are posed without their answer values.
- Containment recommendations are requested without naming the scored policy action.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. The final synthesis ticket is available. Bring the shared findings together for command. Which movement information is supported as disclosed? Is roster disclosure established? Is exposure fully bounded? What can you establish about an adversary? Did the credential action contain the activity? Label claims confirmed, assessed, or unknown. Distinguish disclosed, denied, and unresolved claims. Recommend proportionate containment, evidence preservation, and targeted collection, with reasons and limits. Provide a reliable technical assessment to the controller. Command decides any patrol response. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-06-command-decision.txt](spoken/brief-06-command-decision.txt).
