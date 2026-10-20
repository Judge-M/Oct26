# Participant rehearsal rerun 3 — 2026-10-20

This was a fresh, browser-only participant run against the event machine after the participant-flow improvements in PR [#222](https://github.com/Judge-M/Oct26/pull/222). A newly registered team used IRIS to claim work, CTFd to unlock the explicit walkthroughs and submit answers, Wazuh Discover to query the prepared telemetry view, and the browser-local correlation and capstone workspaces to structure the final assessment.

No generated password or private registration/retrieval link appears in this report or its screenshots.

## Result

- 20 of 20 ticket stages completed.
- 80 of 80 questions accepted through the participant UI.
- Every explicit walkthrough reduced its question from four points to one point, producing the expected assisted score of 80.
- The stock CTFd scoreboard rendered the team in first place with 80 points after its normal client-side load.
- The integration outbox drained to zero; all 80 findings, 80 point awards, 20 ticket closures, and the final assessment were delivered exactly once.
- The activity reached its intended terminal state at `00:09:44`: **LIMITED DISCLOSURE CONFIRMED — IMMEDIATE CONTAINMENT REQUIRED**.
- The final assessment cleanly separates confirmed facts, unsupported claims, unresolved collection gaps, and required containment.
- After the final deployment refresh, the completed state and 80-point scoreboard survived service recreation. The event was then paused with `event_ready: true`, one provisioned team, three desktops, 20 tickets, and zero pending synchronization updates.

This was an accelerated assisted rehearsal. It validates functionality, gating, scoring, evidence publication, and narrative transitions. It is not evidence that a beginner team will naturally occupy six hours; that still requires a participant run that does not immediately buy every level-3 hint.

## Improvements verified

1. The private handout now explains that all three desktops have the complete toolbox while giving each desktop a suggested starting role and work split.
2. The question page keeps unanswered work in a current section and moves completed findings into collapsed history, with direct navigation to both sections.
3. The midpoint release uses a prominent `NEW EVIDENCE RELEASED · PHASE 3 AVAILABLE` badge. Acknowledging it collapses the narrative detail but leaves the badge and jump link visible.
4. The process-to-network correlation board persists participant notes and requires an explicit cross-source review check.
5. The capstone workspace keeps confirmed, not established, unresolved, and recommended-action reasoning separate before T20 submission.
6. Wazuh opens directly in Discover with the `silent-ridge-*` view and the absolute incident range instead of the write-oriented setup wizard.

## Defect found and corrected during this run

The first version of the direct Wazuh link included an explicit `_a` column-state object. It worked after navigating to Discover inside Wazuh, but a fresh hard load could fail with `columns is not iterable` and leave only the Wazuh shell visible. The shortcut now supplies only the global incident time and empty query state, allowing the provisioned Discover view to provide its own valid column metadata. A fresh isolated tab opened the view successfully with the correct data view and time range.

The remaining read-only Wazuh warning was also corrected. The dashboard now predefines the exact `silent-ridge-timed` default index in its deployed configuration, so the plugin no longer tries to write that preference into the global tenant. A fresh isolated participant session rendered `silent-ridge-*`, 499 records, and the correct incident window with no 403 toast or unauthorized console entry. The participant role remains read-only; no write permission was added.

That deployment exposed a separate rerun-only defect in external TLS mode: the certificate generator attempted to validate the installed public edge certificate as though it were the private-CA participant certificate. Reruns now preserve and validate the existing private Wazuh CA, dashboard, manager, indexer, and admin material, then reinstall the configured public edge pair idempotently. Incomplete private material fails closed. The corrected update completed from a verified recovery backup and returned the live event to `PROVISIONED_PAUSED` with `event_ready: true`.

## Question-by-question method and explanations

The authored prompts, answers, evidence source, explanation, investigative importance, and limitation for all 80 questions are recorded in the [canonical full browser walkthrough](../../rehearsal-20261019/team-01/WALKTHROUGH.md). This rerun repeated those same 80 UI submissions after the participant-flow changes; the content and accepted values were unchanged.

For every question, the participant:

1. claimed the owning ticket in IRIS;
2. read the coached tool and evidence route;
3. unlocked Help level 3, accepting the visible 75% point cost;
4. correlated the named source rather than treating the requested value as a complete incident conclusion;
5. submitted only the requested value; and
6. verified that the answer published its finding and limitation back to the shared case.

The ticket-level completion captures below are from this rerun. Each capture was taken only after all four questions in that ticket were accepted and the ticket closure was visible to the shared workflow.

| Ticket | Investigation purpose | Questions | Current-run evidence |
|---|---|---:|---|
| T01 | Trace the plan-v3 request and upload path | T01-Q1–Q4 | [complete](screenshots/t01-complete.jpg) |
| T02 | Resolve the external destination and compare conversations | T02-Q1–Q4 | [complete](screenshots/t02-complete.jpg) |
| T03 | Reconstruct the viewer download | T03-Q1–Q4 | [complete](screenshots/t03-complete.jpg) |
| T04 | Correct and investigate persistence timing | T04-Q1–Q4 | [complete](screenshots/t04-complete.jpg) |
| T05 | Recover and compare cached brief content | T05-Q1–Q4 | [complete](screenshots/t05-complete.jpg) |
| T06 | Separate session refresh from password authentication | T06-Q1–Q4 | [complete](screenshots/t06-complete.jpg) |
| T07 | Test what the password reset did and did not revoke | T07-Q1–Q4 | [complete](screenshots/t07-complete.jpg) |
| T08 | Audit document and roster access | T08-Q1–Q4 | [complete](screenshots/t08-complete.jpg) |
| T09 | Compare the superseding movement brief | T09-Q1–Q4 | [complete](screenshots/t09-complete.jpg) |
| T10 | Test a benign comparator before widening scope | T10-Q1–Q4 | [complete](screenshots/t10-complete.jpg) |
| T11 | Keep the WS-31 lead unresolved where collection ends | T11-Q1–Q4 | [complete](screenshots/t11-complete.jpg) |
| T12 | Map collection coverage and gaps | T12-Q1–Q4 | [complete](screenshots/t12-complete.jpg) |
| T13 | Inspect acquired process-log records | T13-Q1–Q4 | [complete](screenshots/t13-complete.jpg) |
| T14 | Normalize task and process timestamps once | T14-Q1–Q4 | [complete](screenshots/t14-complete.jpg) |
| T15 | Reconstruct the memory process tree | T15-Q1–Q4 | [complete](screenshots/t15-complete.jpg) |
| T16 | Join process identity to network activity | T16-Q1–Q4 | [complete](screenshots/t16-complete.jpg) |
| T17 | Inspect static binary configuration without execution | T17-Q1–Q4 | [complete](screenshots/t17-complete.jpg) |
| T18 | Bound what the relay acknowledgment establishes | T18-Q1–Q4 | [complete](screenshots/t18-complete.jpg) |
| T19 | Verify the payload match and delivery metadata | T19-Q1–Q4 | [complete](screenshots/t19-complete.jpg) |
| T20 | State the final bounded assessment and actions | T20-Q1–Q4 | [complete](screenshots/t20-complete.jpg) |

## Key visual checkpoints

- [Midpoint evidence release remains visible after acknowledgment](screenshots/midpoint-release-acknowledged.jpg)
- [Completed process-to-network correlation board](screenshots/correlation-workspace.jpg)
- [Prepared Wazuh Discover view with an exercise query](screenshots/wazuh-prepared-discover-query.jpg)
- [Fresh Wazuh participant view after the read-only preference fix](screenshots/28-wazuh-discover-no-errors.jpg)
- [Completed capstone assessment workspace](screenshots/capstone-assessment-workspace.jpg)
- [Definitive final incident assessment](screenshots/final-assessment.jpg)
- [Final CTFd scoreboard with 80 points](screenshots/scoreboard.jpg)

## Remaining recommendations

- Run one beginner team without immediately unlocking level-3 hints to measure real difficulty, ambiguity, and duration.
- Retain the strong uncertainty language and final room-wide outro cue; they prevent participants from converting evidence gaps into unsupported certainty and avoid dozens of devices playing the same media independently.
