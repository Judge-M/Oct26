> Historical baseline reference only. The expanded handoff is governed by README.md and docs/expanded-operations.md; specialist cells, Jira, reporting and approval gates are retired.

# Five cooperative investigation assignments

All five cells investigate the same incident. Every cell can read and comment on
all tickets. The owning cell maintains its status and final assessment.
Assign an analyst, evidence recorder, and reporter; combine roles as needed.

| Ticket | Specialist cell | Initial sources | Assignment |
|---|---|---|---|
| 1 | Network | network/ | Assess network activity and possible data movement. |
| 2 | Endpoint | endpoint/ | Reconstruct endpoint activity and assess affected systems. |
| 3 | Identity | identity/ | Assess account and authentication activity. |
| 4 | Server and data | server/ | Assess access to documents and potential exposure. |
| 5 | Threat hunting | hunting/ | Investigate scope across systems and document coverage gaps. |

Use the collection context to understand each source and its limitations.
Develop your own hypotheses, cite supporting and contradicting evidence, and
ask other cells for corroboration. Keep facts separate from assessments.
Do not execute files or connect to addresses found in evidence.

Every cell posts its initial report by elapsed minute {{initial_report}}.
Respond to command messages as they arrive. Comment on at least one other cell's
ticket with useful evidence and identify a next collection step.

## Joint assessment ownership

The hunting reporter coordinates the joint assessment on ticket 5.
Each cell contributes by minute {{cell_handover}}, linking ticket and comment IDs,
facts, confidence, unresolved questions, and defensive priorities.
The hunting reporter posts JOINT ASSESSMENT by minute {{joint_report}}.
Record unresolved disagreements rather than forcing consensus.
Only published controller acknowledgments establish simulated action status.
