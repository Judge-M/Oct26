# Operation Silent Ridge — Faye Maxwell narrative briefs

This is the complete approved narrative package. It contains exactly two spoken cues from **Faye Maxwell, SOC supervisor for Operation Silent Ridge**:

| Cue | Canonical script | Trigger | Estimate |
|---|---|---|---:|
| Introduction | [brief-01-introduction.txt](spoken/brief-01-introduction.txt) | Teams assembled, before investigation | 256 words / 110 s |
| Final assessment | [brief-02-exit.txt](spoken/brief-02-exit.txt) | 20/20 stages complete and final assessment visible | 508 words / 218 s |

Only the two files under `spoken/` are canonical production inputs. The Markdown performance sheets, JSON metadata and announcement echoes must match them. The existing [introduction WAV](recordings/brief-01-introduction.wav) remains available for facilitator-only room playback. The accepted opening and closing videos are embedded in [`docs/event-day-deck/event-day-deck.pptx`](../../event-day-deck/event-day-deck.pptx); standalone MP4 files are not distributed from this package.

The introduction stays entirely inside the narrative and does not identify the scenario as an exercise. The conclusion is intentionally spoiler-bearing and must not be delivered early: it follows the participant-page assessment **LIMITED DISCLOSURE CONFIRMED — IMMEDIATE CONTAINMENT REQUIRED**.

Start with [START-HERE.md](START-HERE.md). Producers should use [NEXT-AI-HANDOFF.md](NEXT-AI-HANDOFF.md). Facilitators can use the [cue desk](player.html), [runbook](RUNBOOK.md), [cue boundaries](INJECTION-PLAN.md) and [review notes](REVIEW.md).

Validation:

```bash
python docs/handoff/audio-briefs/validate.py
```

Superseded three-brief, seven-brief and previous voice-render packages must not be copied into this directory or merged from another branch.
