> Historical baseline reference only. The expanded handoff is governed by README.md and docs/expanded-operations.md; specialist cells, Jira, reporting and approval gates are retired.

# Controller guide and staged injects

Keep this guide and the vault private. Read runtime/vault/controller-schedule.md
for the validated run's releases, responses, joint report and closure. Start the
ledger clock after all cells can access evidence. Scenario time begins at 09:30Z;
actual UTC and pause-aware elapsed time are recorded separately. Release is manual.
See docs/controller-ledger.md for exact clock, decision and export commands.

At start, read participant handover aloud. Ask each cell to name a reporter and to
locate its ticket and collection note. Coach tool usage without stating conclusions.
Log observed behaviors and elapsed times for assessment. Reward an early qualified
warning over a late unsupported claim of certainty.

| Inject | Command and evidence | Expected change |
|---|---|---|
| 1 | `python scripts/exercise.py release 1 --operator EXCON-A`; DLP body and hash | Establish v3 disclosure |
| 2 | `python scripts/exercise.py release 2 --operator EXCON-A`; late refresh and version comparison | Revise containment and current exposure |
| 3 | `python scripts/exercise.py release 3 --operator EXCON-A`; delayed inventory and comparator | Broaden collection without name-only compromise claims |

Use the generated schedule for planned elapsed releases and response deadlines.
Each actual release records UTC, elapsed time and operator in the control ledger.

After release, tell all cells to refresh the portal, verify the release manifest,
and read the command prompt. In Jira, post the command question manually to all
five tickets and link the same release URL. Do not attach future injects to Jira.
If delayed by a technical failure, freeze elapsed time and announce the revised
deadline. Record actual release UTC and elapsed time in the controller ledger.

## Action adjudication

Cells submit recommendations only. Record request ID, elapsed time, cited evidence,
benefit, availability cost, decision and effective exercise time. Apply the same rule
to all cells and announce approved changes on every ticket. Canonical evidence is
historical: do not edit logs when a proposed action is approved.

| Request | Default simulated response | Required follow-up |
|---|---|---|
| Isolate WS-17, preserve evidence | Approve after cell identifies lost clerk access; effective request+5 minutes | Controller confirms simulated isolation only; ask how they would verify and collect memory/disk |
| Revoke S-41 and other m.ellis sessions | Approve with helpdesk coordination; effective request+3 | Controller states simulated revocation, no new forensic export; distinguish control assertion from logged evidence |
| Reset password only | Acknowledge reset history; ask about existing sessions | Supply no invented successful containment |
| Block example egress address/domain | Approve as supplementary control; effective request+5 | Ask about alternate destinations and legitimate service impact |
| Collect WS-31 image/telemetry | Approve collection request; no result before ENDEX | Remains unresolved; collection order and owner required |
| Ask whether anyone read data or patrol was harmed | No corroborating report available | Preserve uncertainty; do not convert it into no-harm proof |
| Recommend reassessing exposed check-in information | Simulated command acknowledges risk and owns response | Participants do not direct patrols or design physical maneuvers |
| Wipe all workstations / revoke every enterprise account | Request proportionality and preservation justification | Do not reward blanket disruption unsupported by scope evidence |

If cells request containment before inject 2, I201 remains a historical 09:26 event,
predating their 09:30-or-later request. Explicitly explain this to avoid implying
that a newly approved revocation failed. The same timing rule applies to all logs.

If a cell stalls for 10 minutes, offer hint 1 from solutions; after another 10,
offer hint 2. Hint 3 is a recovery aid. Log hints for coaching context, not automatic
penalties. Ask the cell to reproduce the conclusion and explain its uncertainty.

At the generated investigation_end, stop investigation. Collect each cell contribution
by cell_handover and the hunting reporter’s JOINT ASSESSMENT on ticket 5 by joint_report. Export the fallback board
and Jira project work separately. Do not publish participant names, credentials,
comments or performance assessments to this public repository. Run AAR before reset.


## Participant and controller separation

The participant board serves only runtime/public. Do not copy facilitator files,
solutions, ground truth, or the private vault into that directory.
The participant schedule contains reporting milestones; the complete release
sequence is in runtime/vault/controller-schedule.md on the controller host.
Cell coaching prompts are in facilitator/cell-coaching.md, not participant assignments.

The complete ledger remains at runtime/control/ledger.json and in private exports.
Controller note text and host account names are excluded from the participant API.
Start/pause/resume records expose timing only, and release records expose only
the already released inject number. Decision text IS participant-visible:
write the acknowledgment there; keep coaching, planned developments, assessment
notes, and answers in a separate note event. Release/reset administration remains
host-only. A separate loopback-only facilitator panel is available on the controller host. See docs/admin-panel.md. It is not served by the participant service.
