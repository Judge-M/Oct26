# Audio delivery runbook — operator only

Use the existing [event-day commands](../../event-day-commands.md) and [release runbook](../../facilitator-evidence-release.md). The cue desk has no controller connection, scheduler or uploader.

## Before delivery

Verify participant access, the issued agenda and the existing runtime state through the event runbook. Keep production metadata and this repository off participant listeners. Open player.html offline for live scripts, or load the exact matching local filenames. Select only one clean/final/MP3 set; the last selected matching stem replaces the previously loaded file. No audio is bundled.

The introduction is delivered before investigation starts. The exit is delivered when the organizer closes the teams' assignment, regardless of ticket completion. “Me” in the story means the organizer/controller; the supervisor takes technical recommendations to command. Patrol decisions remain with command. Preserve the read-only and evidence-handling boundaries. The scripts do not grant permission to scan, execute recovered material or carry out containment.

## Verify the existing state path

On the private controller host, from the matching repo, replace the placeholder with the actual existing runtime database. Do not initialize or guess a default database.

```bash
RIDGE_STATE='/absolute/path/to/actual-runtime/state/state.sqlite'
test -f "$RIDGE_STATE" || { echo 'Existing event database not found'; exit 1; }
python -m ridge.cli --state "$RIDGE_STATE" status
python -m ridge.cli --state "$RIDGE_STATE" diagnostics
```

EXCON in the CLI is the audit actor, not a spoken character name or a credential. Every announcement uses the same verified explicit state path. Before retrying an uncertain delivery, inspect announcements and the private ledger to prevent duplicate cues.

## Select one cue at its agenda seam

Read/play the complete script, post its full written echo, inspect controller status and verify it on a participant surface. A play click or CLI success alone does not prove the room heard it or saw the echo. If audio fails, read the same text live.

### 01 — Introduction — Operation Silent Ridge

At the opening, after the assisting teams assemble and before investigative work begins. Independent of ticket completion or evidence release.

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All right, everyone. Thanks for coming in. We need to move. I'"'"'m the watch floor supervisor in charge of Operation Silent Ridge. The S6 IT department has flagged issues that need a closer look. I'"'"'ve brought your teams in to assist our SOC with the digital forensic investigation. We'"'"'re investigating a suspected disclosure of movement details for Patrol LANTERN, already in the field. No harm is confirmed. If those details reached someone outside our control, they could anticipate the patrol'"'"'s movements. That could put people and the mission at risk. A rushed response could also disrupt essential systems or damage evidence. We need to move quickly and be able to defend our decisions. Establish what happened, what information may have been exposed, and which systems need further attention. Bring me significant findings as soon as you can support them, with the uncertainty alongside. Command needs a reliable picture while it can still act on it. You'"'"'ll have endpoint, network, identity, document-service, and security monitoring records to work from. Give me the source behind a finding, your confidence in it, and what you still can'"'"'t establish. A good hunch earns another look. A finding needs evidence. You'"'"'re separate teams, but I need one shared picture. Share your findings. Challenge each other'"'"'s reasoning. If your favorite theory doesn'"'"'t hold up, let it go. That'"'"'s progress. Keep the investigation read-only and the original evidence untouched. Don'"'"'t scan external systems or run programs recovered from evidence. Bring technical recommendations to me. I'"'"'ll coordinate with command; patrol decisions stay with them. All right. Show me what the evidence supports.'
```

### 02 — Exit — investigation handover

At the actual end of the assisting teams' investigative assignment, as work stops and the existing shared case is handed over. Independent of ticket completion; do not play at a midpoint or only because a synthesis ticket unlocks.

```bash
python -m ridge.cli --state "$RIDGE_STATE" announce --operator EXCON --text 'All right, everyone. We'"'"'re closing your teams'"'"' assignment to Operation Silent Ridge. I need command to see anything that could affect LANTERN'"'"'s safety. Put it up front, with the evidence and uncertainty beside it. A critical finding buried in your notes won'"'"'t help the next watch. Before you disappear, leave the next watch a case they can actually follow. Record your findings and source references in the shared case. Make clear what you can support, how confident you are, and what remains unresolved. Loose ends belong in the handover. They don'"'"'t get to vanish because we'"'"'re out of time. Leave the open leads and collection limits visible, with the next useful step for whoever picks them up. Set out your recommended defensive steps, the evidence behind them, an alternative you considered, and the impact on operations or evidence preservation. I'"'"'ll take those recommendations to command. Close out your investigative work at this handover. Preserve the evidence, your working notes, and the shared case record. Further collection and operational action will be coordinated through me. Thank you for the work you'"'"'ve put into this. I'"'"'ll take the difficult questions to command. Make sure I'"'"'ve got your evidence with me. Your teams can stand down from this assignment. I'"'"'ll take it from here.'
```

## Mode and failure handling

Keep the core paused during the opening. Start only through the event runbook's readiness gates and verify running mode; audio does not start the event. At the actual close, stop investigation, pause through supported operations, verify paused mode and preserve findings for the AAR. The exit does not imply that the incident is contained or all tickets are complete.

For a technical intervention, first pause through the supported operation and verify status:

```bash
python -m ridge.cli --state "$RIDGE_STATE" mode paused --operator EXCON-A
python -m ridge.cli --state "$RIDGE_STATE" status
python -m ridge.cli --state "$RIDGE_STATE" diagnostics
```

Use the existing recovery runbook. Resume only through normal readiness gates. Do not bypass certificates/preflight, manually release evidence, edit receipts or alter scores. Audio production and source validation require no live event connection.

## Private delivery ledger

Actual receipts, event timestamps and participant observations stay in private runtime records, outside GitHub. Recover the ledger after interruption; reloading the page does not begin a new event.

| Cue | Agenda/mode verified | Spoken delivery | Echo visible | Failure or deferral |
|---|---|---|---|---|
| Introduction | | | | |
| Exit | | | | |

Optional analytical exchanges remain live; use FACILITATION.md. They add no recordings, scores, submissions or ticket gates. Pause/resume for discussions only under the event runbook and verify the observed modes.
