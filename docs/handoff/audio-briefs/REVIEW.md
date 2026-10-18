# Handoff review and implementation decisions

Reviewed 2026-10-18 against `Judge-M/Oct26` main commit `af63191bd6d2929b61b543b50c274fa2700c1c27` (fetched and matched before drafting). Scope: the audio script/production package and its operator-only presenter entry point. No controller state or runtime was changed.

## What is retained

Seven moments: opening, four independent evidence cues, final synthesis availability, ENDEX. The automatic release chain is confirmed by [facilitator-evidence-release.md](../../facilitator-evidence-release.md), [the completed rerun](../../rehearsal/evidence/rehearsal-20261018/completed-rerun.md), and `expanded/author.py`. Calm EXCON delivery, cooperative findings, evidence limits and the exact fiction notices are preserved.

The inherited [MASTER-HANDOFF.md](MASTER-HANDOFF.md) is carried forward unchanged as provenance. **This review, the revised injection plan, and RUNBOOK.md govern this implementation where they correct it.**

## Corrections that affect delivery

| Handoff assumption or conflict | Implemented decision |
|---|---|
| Four injects presented as a sequential story | Play each only after its own observed release. T19 may precede T07/T09/T11. Cue numbers are identifiers. |
| “Each team owns two tickets” | That was the serialized rerun's execution map. Current teams claim available tickets dynamically, one active ticket at a time; no cue names a fixed team owner. |
| T20 implies “all evidence lines have converged” | T20 requires only T07, T09, T11 and T19. It does not certify all twenty tickets complete or every lead exhausted. |
| Existing opening claimed to pass spoiler discipline | It named the reset time, a protected answer. The new opening omits the reset, viewer and all incident-chain times. It states only the allowed handover time. |
| Inject titles supply reset failure, benign status, or payload confirmation | Neutral titles and questions carry the task without declaring those results. Comparator evidence is earlier work, not a second newly released file at T11. |
| “Session revocation” offered in command guidance despite the forbidden list | Omitted from speech and echo: this is a scored answer. Request a reasoned containment recommendation. |
| Connection/acknowledgement limitation stated as the answer to a live question | Ask teams to separate transmission evidence from human-receipt/intent claims; never supply a ticket's yes/no answer in speech. |
| 15–25 second cues plus full spoken notice at 140 wpm | Actual estimates are 30–33 seconds per inject, 49 seconds for synthesis, 27 seconds for ENDEX, and 71 seconds opening. Notices stay in every cue. Total speech is about 4 min 33 sec; sound cues and pauses add time. |
| “Text echo” was an abbreviated paraphrase | Echo the complete spoken script with whitespace normalized only. All copies are checked for parity and the actual 4,000-character CLI limit. |
| “Your assessment is recorded” at ENDEX | Do not assert unverified persistence or full completion. Ask teams to preserve shared findings and prepare for reflection. |
| Single-segment fallback could precede release | Consolidate only verified ready cues; defer locked ones and avoid replaying already-delivered cues. Evidence publication remains automatic. |
| A real-time schedule or automatic audio scheduler exists | No scheduler added. The private runbook ledger controls duplicate avoidance and release verification. |
| Legacy handover implies hunting reporter ownership/report gates | Do not impose those on the expanded IRIS/CTFd workflow. Issued schedule deadlines may support facilitated command updates; findings publish automatically from accepted answers. |

## Source accuracy and remaining boundaries

- **Deck ordering defect confirmed:** `docs/event-day-deck/pages/03_story.page` says the viewer ran after the reset. Ground truth places it before. The opening is order-neutral. This package does not edit the presentation source or its exported PDF/PPTD; correcting and re-exporting those together remains a separate presentation task. Existing slide wording also exposes more than these scripts do: these briefs cannot make the whole event deck spoiler-free.
- The completed rerun reports 20 stages, 80 answers and zero pending deliveries, but serialized team identities. The separate Team 3 walkthrough also records live submissions. Neither is thirty humans investigating concurrently; no live-room pacing claim is made here.
- The rerun records a deployment-start certificate guard issue. This documentation package neither repairs nor bypasses it. Use the normal deployment readiness gates before event start.
- The public repo cannot enforce secrecy. Facilitator-only means controlled distribution: participants receive only the published participant tree and approved surfaces. No private runtime state is part of this package.
- Audio recording and radio mixing are a separate step, as specified in the original handoff. The package is usable immediately for live reads; the offline cue desk accepts later local recordings and shows no fabricated audio links.

## Spoiler review

Every script and its echo avoids protected identifiers, discovery timestamps, paths, versions, addresses, clock offset and field values. The validator checks the handoff literal list plus all 80 accepted-answer entries from the pinned rerun (with reviewed premise/safety exceptions). It checks every speech representation, the release dependencies, exact notices and echo length. Generic `LANTERN` is the allowed premise; generic `no` appears only in the opening's “No harm is confirmed” and “No attack is required.” Other numeric answers do not appear in speech.

Semantic review: no brief declares the reset ineffective, a comparator benign, a body identical, roster access denied, the unresolved host cleared/compromised, or an adversary known. No brief resolves original delivery, token contents, human attribution/reading, collection-gap activity, uncollected systems, or actual use. The opening has no clock-offset hint. Command questions remain questions; recommendations never become patrol orders.

See [VALIDATION.md](VALIDATION.md) for measured check results and limitations. This is a source/content delivery, not an event-readiness certification.

## Participant-response follow-up

The supplied podcast assessment identifies a remaining distinction between hearing a dispatch and defending an analysis. [FACILITATION.md](FACILITATION.md) now supplies three live activities: an interim update with cross-cell challenge, one evidence-revision explanation, and a final recommendation defended against an alternative. Each has a response scaffold, timed challenge/response, specific feedback and an incomplete-evidence fallback.

The five minutes of exchanges use the existing facilitated allowance alongside inject/synthesis dispatches. They introduce no new audio cue, answer, scoring criterion, submission, simulated outcome or controller behavior. Cells and spokespeople rotate; private observation notes feed the existing AAR. Readiness is based on the issued update deadline and actual evidence analysis, not an invented inject minute or a fixed team assignment. Human rehearsal is still needed to measure participation, pacing and whether the exchanges help.
