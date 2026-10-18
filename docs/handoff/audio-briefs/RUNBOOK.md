# Day-of audio cue runbook

Facilitator-only. Use with [facilitator-evidence-release.md](../../facilitator-evidence-release.md) and [event-day-commands.md](../../event-day-commands.md). The audio package does not provision, start, release evidence, submit answers, or recover the event.

## Before the room opens

1. Use the current event profile and deployment runbook. Verify participant access, a healthy worker and paused core. Rehearsal state must not be reused for a clean event.
2. Read [REVIEW.md](REVIEW.md). The source deck and existing exported deck still contain the reset/viewer ordering defect; use the corrected order-neutral opening script. A deck correction and re-export remain a separate presentation task.
3. Confirm the initial-update elapsed deadline from the issued schedule. The spoken opening points to that schedule; do not read a template placeholder. In the expanded ticket workflow, accepted answers publish findings automatically. Any command briefing is a facilitated exercise update, never an extra scoring/report gate. Do not import the legacy “hunting reporter on ticket 5” ownership model.
4. Keep the full checkout, this package and the presenter page on the operator machine. Only `runtime/public` and approved participant surfaces are distributed. “Facilitator-only” is a distribution rule; GitHub does not supply secrecy.
5. Open [player.html](player.html) offline. Each cue contains a live-read script. For recorded delivery, select locally produced files named exactly like the seven stems in `spoken/`, with `.wav`, `.mp3`, or `.ogg` extensions. Only loaded files get a player. Test output volume. No recording is included in this package.
6. Prepare the private cue ledger below. Track audio/live read and written echo separately. A play button and a zero-exit CLI command are not proof teams heard or saw the cue.

## Select and verify the state database

Run in the matching repository on the controller host. Replace this path with the actual runtime database from your event profile; do not guess, initialize, or use the CLI's default state path.

```bash
RIDGE_STATE='/absolute/path/to/actual-runtime/state/state.sqlite'
test -f "$RIDGE_STATE" || { echo 'Existing event database not found'; exit 1; }
python -m ridge.cli --state "$RIDGE_STATE" status
python -m ridge.cli --state "$RIDGE_STATE" diagnostics
```

Confirm the expected event's ticket roster, mode and elapsed time. All commands below use this same verified path. `EXCON` is the announcement actor; the release runbook uses `EXCON-A` for controller interventions. Neither is a credential. The short `python -m ridge.cli announce --operator EXCON --text ...` form parses but targets the default database: use the explicit-state form here.

## Observe, deliver, verify

Recheck `status` and `diagnostics` when teams complete prerequisites. A locked ticket is absent from `snapshot`; a dependent appearing there alone is insufficient. For an inject require: every prerequisite complete; dependent present; pending zero; healthy diagnostics; the corresponding IRIS task; and all listed files visible in the read-only participant tree. For 06 verify the task and prerequisites; no file is released.

Then play/read exactly the selected script, post its full echo below, check the new announcement in `status`, and confirm it appears on a participant surface. Mark both delivery steps in the ledger. Announce records an audit item rather than proving participant delivery. It is not an idempotent cue scheduler: before retrying after an uncertain response, inspect existing announcements and the ledger to avoid duplicates.

Cues 02–05 can arrive in any order. If several arrive together, verify each independently and play the ready, undelivered cues back-to-back in observed release order. If release order is indistinguishable use cue number as a tie-breaker. No extra “intelligence” claim and no forced 02→03→04→05 sequence. At T20 availability, deliver any pending prerequisite cues first, then 06, unless ENDEX has already been called. After ENDEX do not play late investigative cues.

## Per-cue commands — select one, never run as a batch

These are an index. Each command is separately gated; reading down the file does not establish eligibility.

### 01 — Opening tasking

At the orientation-to-investigation seam, after participant access and the issued schedule are checked, immediately before the organizer starts the event.

Release files: No new file.

Read/play [brief-01-opening-task.md](brief-01-opening-task.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Operation Silent Ridge. Exercise time, zero-nine-three-zero Zulu. Incoming watch, you have the watch. Patrol LANTERN is in the field. Disclosure of its movement details is suspected. No harm is confirmed. Do not assume the incident is over. Endpoint, network, identity, document-service, and security information and event management exports are staged. Establish what moved, how access was gained, and which systems remain affected. Label each claim confirmed, assessed with confidence, or unknown. Cite evidence. Share findings across cells for the joint assessment. Report even at low confidence. Your first command update is due at the elapsed mark in your issued schedule. Read-only investigation. Preserve the supplied evidence. Do not contact real personnel, track them, or direct them. No attack is required. Send defensive recommendations to the controller. Command decides any patrol response. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 02 — Identity reassessment

Observe T06 complete, T07 released and synchronized, and the later authentication file visible.

Release files: `identity/late-auth.csv`

Read/play [brief-02-inject-a-reset.md](brief-02-inject-a-reset.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Later authentication records are now available. Revisit your access assessment. Did the credential action contain the activity? What does the evidence establish about its effect? Carry the revised finding and its limits into the shared case. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 03 — Movement-information comparison

Observe T08 complete, T09 released and synchronized, and the version comparison visible.

Release files: `server/version-comparison.csv`

Read/play [brief-03-inject-b-superseded.md](brief-03-inject-b-superseded.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Superseding movement information is now available. Compare it with the earlier record. Which details changed? Which, if any, remain relevant? Revisit the disclosure scope in your shared finding. Keep the comparison separate from assumptions about harm. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 04 — Scope lead and coverage

Observe T10 complete, T11 released and synchronized, and the late inventory visible. The comparator belongs to earlier work; do not announce it as newly released.

Release files: `hunting/late-inventory.csv`

Read/play [brief-04-inject-c-unresolved.md](brief-04-inject-c-unresolved.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Further inventory evidence is now available. Test the host lead against the comparator already supplied. What does a name match establish? What collection would support a stronger conclusion? Record coverage limits before clearing or implicating any system. Share the revised scope assessment. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 05 — Payload verification

Observe BOTH T01 and T05 complete, T19 released and synchronized, and both DLP files visible.

Release files: `network/dlp-body.txt`, `network/dlp-metadata.json`

Read/play [brief-05-inject-d-payload.md](brief-05-inject-d-payload.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. A transmitted body and its metadata are now available. Re-test the earlier transmission assessment against the body itself. Does it support the size-based lead? Separate evidence of transmission from claims about human receipt or intent. Update the shared finding with citations and limits. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 06 — Command decision support

Observe T07, T09, T11 and T19 complete and T20 released and synchronized; confirm its IRIS task. There is no new file. This is not proof all twenty tickets are complete.

Release files: No new file.

Read/play [brief-06-command-decision.md](brief-06-command-decision.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. The final synthesis ticket is available. Bring the shared findings together for command. Which movement information is supported as disclosed? Is roster disclosure established? Is exposure fully bounded? What can you establish about an adversary? Did the credential action contain the activity? Label claims confirmed, assessed, or unknown. Distinguish disclosed, denied, and unresolved claims. Recommend proportionate containment, evidence preservation, and targeted collection, with reasons and limits. Provide a reliable technical assessment to the controller. Command decides any patrol response. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

### 07 — ENDEX stand-down

At the organizer-declared end of investigation, immediately before the after-action review. May occur with incomplete tickets; never wait indefinitely for T20.

Release files: No new file.

Read/play [brief-07-endex-standdown.md](brief-07-endex-standdown.md), then post:

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All stations, this is EXCON. Exercise, exercise, exercise. Exercise ends. ENDEX. Stand down. Cease investigation. Preserve the shared findings for the after-action review. Bring one supported finding, one remaining uncertainty, and one improvement. Well done. Good hunting. EXCON, out. All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person. OPERATION SILENT RIDGE — EXERCISE ONLY.'
```

## Clock and failure handling

Opening: keep the core paused while reading. Start through the documented `ridge.deploy start --profile ... --runtime ...` workflow and verify running mode only when its readiness gates pass. The recorded rerun reported a certificate/start guard issue; this package does not fix or authorize bypassing it.

Ordinary injects: leave the clock in its current running state. Short dispatches are part of play. For a longer facilitated discussion the organizer may pause through the event runbook and must verify the observed mode. Pausing elapsed time does not itself prove evidence delivery or revoke sessions.

Technical failure: pause before intervention using the supported controller operation, then inspect diagnostics:

```bash
python -m ridge.cli --state "$RIDGE_STATE" mode paused --operator EXCON-A
python -m ridge.cli --state "$RIDGE_STATE" status
python -m ridge.cli --state "$RIDGE_STATE" diagnostics
```

Require observed `mode: paused`. Follow the existing recovery runbook; let the worker synchronize and verify task/files again. Resume through the event deployment runbook after normal gates pass; do not change to running merely to bypass preflight or certificate checks. Do not manually copy evidence, award points, create duplicate tickets or edit delivery receipts.

ENDEX: the organizer ends investigation, pauses through the event runbook and checks paused mode. Preserve findings and use the normal AAR. If time expires before T20, omit 06 and record that its trigger was unmet. Never announce that all evidence, answers or assessments are complete solely because ENDEX was called. Backups and teardown remain governed by the event runbook.

## Private delivery ledger

Keep actual event timestamps and receipts in private runtime records, not GitHub. After interruption/restart, recover this ledger before playing cues. Do not treat a reloaded player page as a fresh event.

| Cue | Prerequisites/task/files verified at | Spoken delivered at | Echo visible at | Deferred/skipped reason |
|---|---|---|---|---|
| 01 | | | | |
| 02 | | | | |
| 03 | | | | |
| 04 | | | | |
| 05 | | | | |
| 06 | | | | |
| 07 | | | | |
