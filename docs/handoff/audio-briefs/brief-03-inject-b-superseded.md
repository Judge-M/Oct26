# Brief 03 — Movement-information comparison

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Invite comparison without revealing any version, changed field, retained field or movement detail.

**Trigger:** Observe T08 complete, T09 released and synchronized, and the version comparison visible. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO5, LO2; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 71 spoken words; approximately 30 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the clock in its existing running state for ordinary injects. For a technical interruption, use RUNBOOK.md; audio never changes controller state.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

**Participant response:** Once a cell has investigated one new release, consider activity B: explain the earlier assessment, new evidence and revised or retained conclusion. Use B once per event, not after each inject; playback alone does not establish readiness. See [FACILITATION.md](FACILITATION.md) for timing, clock handling and fallbacks. Coaching adds no scoring or unlock gate.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

Superseding movement information is now available. Compare it with the earlier record. Which details changed? Which, if any, remain relevant? Revisit the disclosure scope in your shared finding. Keep the comparison separate from assumptions about harm.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Comparison evidence is available; no field value is disclosed.
- Remaining relevance is a question, not a supplied conclusion.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Superseding movement information is now available. Compare it with the earlier record. Which details changed? Which, if any, remain relevant? Revisit the disclosure scope in your shared finding. Keep the comparison separate from assumptions about harm. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-03-inject-b-superseded.txt](spoken/brief-03-inject-b-superseded.txt).
