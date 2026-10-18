# Brief 07 — ENDEX stand-down

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Close the investigation and invite reflection without inventing a completed assessment or resolving any gap.

**Trigger:** At the organizer-declared end of investigation, immediately before the after-action review. May occur with incomplete tickets; never wait indefinitely for T20. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO8; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 62 spoken words; approximately 27 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** The organizer ends investigation and pauses through the event runbook; verify paused mode. Playback itself does not stop answers.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

**Participant response:** Carry observations from activities A–C into the AAR. Invite cells that have not spoken and recognize evidence-bounded uncertainty; do not run late investigative cues after ENDEX. See [FACILITATION.md](FACILITATION.md) for timing, clock handling and fallbacks. Coaching adds no scoring or unlock gate.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

Exercise ends. ENDEX. Stand down. Cease investigation. Preserve the shared findings for the after-action review. Bring one supported finding, one remaining uncertainty, and one improvement. Well done.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- ENDEX is an organizer seam, independent of ticket completion.
- No claim that every answer or report was recorded.
- Reflection preserves uncertainty.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Exercise ends. ENDEX. Stand down. Cease investigation. Preserve the shared findings for the after-action review. Bring one supported finding, one remaining uncertainty, and one improvement. Well done. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-07-endex-standdown.txt](spoken/brief-07-endex-standdown.txt).
