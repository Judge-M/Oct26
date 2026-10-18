# Brief 02 — Identity reassessment

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Prompt an evidence-based test of control efficacy without declaring whether the reset succeeded.

**Trigger:** Observe T06 complete, T07 released and synchronized, and the later authentication file visible. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO4; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 71 spoken words; approximately 30 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the clock in its existing running state for ordinary injects. For a technical interruption, use RUNBOOK.md; audio never changes controller state.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

Later authentication records are now available. Revisit your access assessment. Did the credential action contain the activity? What does the evidence establish about its effect? Carry the revised finding and its limits into the shared case.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Names the evidence family only.
- Asks about control efficacy without naming the required policy action or its result.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Later authentication records are now available. Revisit your access assessment. Did the credential action contain the activity? What does the evidence establish about its effect? Carry the revised finding and its limits into the shared case. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-02-inject-a-reset.txt](spoken/brief-02-inject-a-reset.txt).
