# Event-gated injection plan

Facilitator-only. Read [REVIEW.md](REVIEW.md) for corrections to the inherited handoff. Four independent release cues, one opening, one synthesis cue, one stand-down. **The table is an asset index, not a mandatory play order.**

| Cue | Brief | Observed dependent | Completed prerequisites | Estimated speech | LO |
|---|---|---|---|---|---|
| 01 | [Opening tasking](brief-01-opening-task.md) | Start seam | Organizer seam | 71 s | LO2, LO7, LO8 |
| 02 | [Identity reassessment](brief-02-inject-a-reset.md) | T07 | T06 | 30 s | LO4 |
| 03 | [Movement-information comparison](brief-03-inject-b-superseded.md) | T09 | T08 | 30 s | LO5, LO2 |
| 04 | [Scope lead and coverage](brief-04-inject-c-unresolved.md) | T11 | T10 | 33 s | LO6, LO5 |
| 05 | [Payload verification](brief-05-inject-d-payload.md) | T19 | T01, T05 | 33 s | LO2, LO5 |
| 06 | [Command decision support](brief-06-command-decision.md) | T20 | T07, T09, T11, T19 | 49 s | LO5, LO7, LO8 |
| 07 | [ENDEX stand-down](brief-07-endex-standdown.md) | ENDEX seam | Organizer seam | 27 s | LO8 |

## Delivery gates

The controller releases evidence automatically. EXCON observes release, checks delivery, then plays or reads the cue and posts its full text echo. Do not copy vault files, close tickets manually, or release on a timer. For each dependent, require prerequisites complete, dependent present in `status` (locked tickets are omitted), pending zero, healthy diagnostics, and the real IRIS task and named participant files visible. T20 has no file.

T19 can arrive before 02–04. Ticket phases describe curriculum, not a barrier that forces all cells through the same order. Teams claim available work dynamically; the rehearsal team-to-ticket table is historical, not a fixed allocation.

Run on the controller host from the repository root, using the verified database:

```bash
python -m ridge.cli --state "$RIDGE_STATE" status
python -m ridge.cli --state "$RIDGE_STATE" diagnostics
```

See [RUNBOOK.md](RUNBOOK.md) for state-path checks, per-cue announce commands, delivery verification, simultaneous releases, and interruptions.

## Consolidated fallback

Prefer individual cues at their observed releases. If the organizer uses the schedule model's facilitated segment, queue only cues whose releases have already been verified and play those together. Defer any cue still locked; never say “now available” for unreleased evidence. Do not replay cues already delivered. Do not delay evidence publication to fit the segment. Treat the segment as a recap if all four cues have already played.

Keep 06 at observed T20 availability; play 07 at the actual ENDEX seam even if T20 never becomes available. No cue at clock-offset discovery. No fixed elapsed inject times: the authored schedule is arithmetic, and serialized browser completion is not thirty-person pacing evidence.

## Timing

At 140 words per minute these seven scripts total about 273 seconds of speech before sound cues and pauses. The full fiction disclaimer is spoken on every cue. Rehearse the read, playback volume and text visibility; the inherited 15–25 second inject targets cannot carry that mandatory wording plus the tasking at this pace.
