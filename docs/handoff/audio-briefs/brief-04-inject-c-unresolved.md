# Brief 04 — Scope lead and coverage

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Prompt scope testing against actual coverage without identifying either host or deciding the lead.

**Trigger:** Observe T10 complete, T11 released and synchronized, and the late inventory visible. The comparator belongs to earlier work; do not announce it as newly released. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO6, LO5; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 77 spoken words; approximately 33 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the clock in its existing running state for ordinary injects. For a technical interruption, use RUNBOOK.md; audio never changes controller state.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

Further inventory evidence is now available. Test the host lead against the comparator already supplied. What does a name match establish? What collection would support a stronger conclusion? Record coverage limits before clearing or implicating any system. Share the revised scope assessment.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Only the late inventory is newly released.
- The comparator is not labelled benign in participant speech.
- Does not clear, implicate or identify the unresolved host.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Further inventory evidence is now available. Test the host lead against the comparator already supplied. What does a name match establish? What collection would support a stronger conclusion? Record coverage limits before clearing or implicating any system. Share the revised scope assessment. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-04-inject-c-unresolved.txt](spoken/brief-04-inject-c-unresolved.txt).
