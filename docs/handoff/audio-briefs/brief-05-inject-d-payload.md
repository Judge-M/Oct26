# Brief 05 — Payload verification

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Turn the size-based lead into a comparison task without supplying the match, version or human-receipt answer.

**Trigger:** Observe BOTH T01 and T05 complete, T19 released and synchronized, and both DLP files visible. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO2, LO5; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 78 spoken words; approximately 33 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the clock in its existing running state for ordinary injects. For a technical interruption, use RUNBOOK.md; audio never changes controller state.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

A transmitted body and its metadata are now available. Re-test the earlier transmission assessment against the body itself. Does it support the size-based lead? Separate evidence of transmission from claims about human receipt or intent. Update the shared finding with citations and limits.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Body and metadata are available; no matching result is supplied.
- Human receipt and intent remain claims that need independent support.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. A transmitted body and its metadata are now available. Re-test the earlier transmission assessment against the body itself. Does it support the size-based lead? Separate evidence of transmission from claims about human receipt or intent. Update the shared finding with citations and limits. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-05-inject-d-payload.txt](spoken/brief-05-inject-d-payload.txt).
