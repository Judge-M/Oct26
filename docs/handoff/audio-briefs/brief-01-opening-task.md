# Brief 01 — Opening tasking

Facilitator-only production sheet. The **Script** section and paired text echo are participant-safe; trigger notes stay private.

**Role / purpose:** Establish stakes and cooperative tasking without revealing the incident mechanism or discovery answers.

**Trigger:** At the orientation-to-investigation seam, after participant access and the issued schedule are checked, immediately before the organizer starts the event. See [RUNBOOK.md](RUNBOOK.md) for the complete release checks. Numbers identify assets; injects 02–05 may play in any observed release order.

**Learning objectives:** LO2, LO7, LO8; definitions in [learning-objectives.md](../../learning-objectives.md).

**Length:** 166 spoken words; approximately 71 seconds at 140 words per minute, plus pauses and sound cues. Time the actual read before recording. Full fiction notices are included in this estimate.

**Voice / processing:** Calm, clipped, unhurried watch officer. Read EXCON as “ex-con”; ENDEX as “end-ex” where present. Read the spelled-out export family naturally. Slight downward endings. Optional opening squelch; high-pass near 200 Hz, gentle presence at 1–4 kHz, optional static near −30 dB, two-tone closing chime. Preserve intelligibility; do not read production headings. Sound cues are outside the spoken script.

**Clock:** Keep the core paused for tasking. Start through the deployment runbook only after normal readiness gates pass. Do not bypass a failed start guard.

**Spoiler discipline:** No protected host, session, filename, version, address, incident timestamp, field value, or scored remediation answer is spoken. Evidence questions must remain questions. Do not improvise a result.

## Script

All stations, this is EXCON. Exercise, exercise, exercise.

Operation Silent Ridge. Exercise time, zero-nine-three-zero Zulu. Incoming watch, you have the watch.

Patrol LANTERN is in the field. Disclosure of its movement details is suspected. No harm is confirmed. Do not assume the incident is over.

Endpoint, network, identity, document-service, and security information and event management exports are staged. Establish what moved, how access was gained, and which systems remain affected.

Label each claim confirmed, assessed with confidence, or unknown. Cite evidence. Share findings across cells for the joint assessment. Report even at low confidence. Your first command update is due at the elapsed mark in your issued schedule.

Read-only investigation. Preserve the supplied evidence. Do not contact real personnel, track them, or direct them. No attack is required. Send defensive recommendations to the controller. Command decides any patrol response.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.

## Key facts carried

- Exercise time is the handover time, not the event wall clock.
- Disclosure is suspected and no harm is confirmed.
- Five export families, evidence citations, uncertainty, read-only work and command boundaries are explicit.
- The initial update references the issued elapsed deadline without inventing a minute.

## Text echo

Post the entire spoken script verbatim, with paragraph breaks normalized to spaces. Set `RIDGE_STATE` to the verified existing event database as described in [RUNBOOK.md](RUNBOOK.md). This command is for this cue only, after its trigger is verified:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Operation Silent Ridge. Exercise time, zero-nine-three-zero Zulu. Incoming watch, you have the watch. Patrol LANTERN is in the field. Disclosure of its movement details is suspected. No harm is confirmed. Do not assume the incident is over. Endpoint, network, identity, document-service, and security information and event management exports are staged. Establish what moved, how access was gained, and which systems remain affected. Label each claim confirmed, assessed with confidence, or unknown. Cite evidence. Share findings across cells for the joint assessment. Report even at low confidence. Your first command update is due at the elapsed mark in your issued schedule. Read-only investigation. Preserve the supplied evidence. Do not contact real personnel, track them, or direct them. No attack is required. Send defensive recommendations to the controller. Command decides any patrol response. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

Check the announcement in `status` and the participant view before marking this cue delivered. The spoken source is [spoken/brief-01-opening-task.txt](spoken/brief-01-opening-task.txt).
