# Operation Silent Ridge — audio brief package

Seven spoiler-checked EXCON scripts for live reading or later recording. Four injects follow **observed automatic releases**, in any release order. This package contains scripts and production notes; final mixed audio is not included.

For another AI producing the finished briefs, start with [NEXT-AI-HANDOFF.md](NEXT-AI-HANDOFF.md): current decisions, all seven exact scripts, source hashes and production acceptance.

Open [the offline cue desk](player.html) to read or play locally loaded recordings. Start with [RUNBOOK.md](RUNBOOK.md) for the delivery checks and [REVIEW.md](REVIEW.md) for corrections to the inherited plan.

[FACILITATION.md](FACILITATION.md) adds three participant-response activities: a two-minute interim update with peer challenge, one minute explaining an evidence-driven revision, and a two-minute containment recommendation with an alternative, tradeoff and feedback. They use the existing facilitated allowance and add no scoring, submission or ticket-unlock requirements.

| File | Purpose |
|---|---|
| [01 · Opening tasking](brief-01-opening-task.md) | Orientation seam before normal event start; ~71 s. |
| [02 · Identity reassessment](brief-02-inject-a-reset.md) | Observed T07 release after T06; ~30 s. |
| [03 · Movement-information comparison](brief-03-inject-b-superseded.md) | Observed T09 release after T08; ~30 s. |
| [04 · Scope lead and coverage](brief-04-inject-c-unresolved.md) | Observed T11 release after T10; ~33 s. |
| [05 · Payload verification](brief-05-inject-d-payload.md) | Observed T19 release after T01 and T05; ~33 s. |
| [06 · Command decision support](brief-06-command-decision.md) | Observed T20 release after T07/T09/T11/T19; ~49 s. |
| [07 · ENDEX stand-down](brief-07-endex-standdown.md) | Organizer-declared end of investigation, before AAR; ~27 s. |
| [INJECTION-PLAN.md](INJECTION-PLAN.md) | Event gates, simultaneous releases, consolidated fallback. |
| [RUNBOOK.md](RUNBOOK.md) | State-path checks, all exact announce echoes, failure handling, private ledger template. |
| [FACILITATION.md](FACILITATION.md) | Participant prompts, timing, rotating peer challenges, feedback, fallbacks and private rehearsal observations. |
| [REVIEW.md](REVIEW.md) | Source reconciliation, plan corrections, remaining deck/start issues. |
| [VALIDATION.md](VALIDATION.md) | Actual checks and limitations. |
| [NEXT-AI-HANDOFF.md](NEXT-AI-HANDOFF.md) | Current production assignment, complete narration appendix, facilitation requirements and QA. |
| [MASTER-HANDOFF.md](MASTER-HANDOFF.md) | Unchanged inherited planning input; REVIEW records corrections. |
| [briefs.json](briefs.json) / [spoken/](spoken/) | Canonical structured text and clean voice/TTS inputs. |
| [validate.py](validate.py) | Read-only spoiler, parity, release and packaging checker. |

Timing estimates use 140 words per minute and include both mandatory fiction notices. Add room for breaths, squelch and closing chime. Rehearse actual reads. Keep the static bed optional and quiet; the text echo carries the entire spoken script, not a summary.

Every production sheet includes role, trigger, learning objective, clock behavior, voice notes, script, accuracy checklist and the paired explicit-state `ridge.cli announce` command. Only the script/echo is intended for participants. Keep metadata, trigger tables, this page and the full repository on the operator machine; serve participants only approved participant surfaces and `runtime/public`.

Sources: [ground truth](../../../facilitator/ground-truth.md), [learning objectives](../../learning-objectives.md), [release mechanism](../../facilitator-evidence-release.md), [schedule model](../../schedule-model.md), and [completed rerun](../../rehearsal/evidence/rehearsal-20261018/completed-rerun.md). The schedule is planning arithmetic; audio injects have no fixed elapsed times.

Run checks from the repository root:

```bash
python docs/handoff/audio-briefs/validate.py
python -m unittest discover -s tests
```

For a standalone copy, pass the checked-out repo to `validate.py --repo /path/to/Oct26`. When editing, keep `briefs.json`, seven spoken texts, seven production sheets, runbook echoes and player embedded data synchronized; the validator detects drift. No command here sends messages or changes runtime state during validation.
