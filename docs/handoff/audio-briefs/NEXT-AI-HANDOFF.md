# Next-AI handoff — produce the Silent Ridge briefs

**Start here. Facilitator-only. Prepared 2026-10-18.** This is the current production handoff, including the participant-response changes requested after the podcast assessment. The seven spoken scripts are already written and spoiler-checked. Your task is to produce the finished brief assets from them and retain the live facilitation layer; do not restart the scenario design.

## 1. Assignment and current status

Produce seven separate EXCON brief recordings from the approved spoken texts below, with a consistent calm watch-officer voice and restrained radio treatment. Also deliver clean transcripts, a production manifest and listening/technical QA results. The exact transcripts and full `announce` echoes must remain aligned. If your available tools cannot generate audio, finish the narration/production package and explicitly identify audio rendering as outstanding; do not report a script or placeholder as a recording.

Already implemented:

- Seven production sheets, seven clean spoken texts, structured source in `briefs.json`, exact full-text announcement commands, release-gated injection plan and controller-host runbook.
- An offline `player.html` cue desk, linked from `docs/presenter-landing.html`. It supports live reads and local recordings selected by the operator. No recordings currently ship with the package.
- Three live participant-response activities with peer challenge, response, feedback, timing, fallbacks and private observations. These are in `FACILITATION.md`, referenced throughout the package and in `facilitator/assessment-aar.md`.
- Spoiler/parity checks and a 467-test passing repository suite at the implementation revision. This is source validation, not audio listening acceptance, measured room pacing or event readiness.

Implementation commits: `b5633d5` (seven-brief package) and `ddd0d91` (participant-response activities), on local branch `docs/audio-briefs`. Base repo revision: `af63191bd6d2929b61b543b50c274fa2700c1c27`. These commits were not pushed to GitHub. A fresh remote clone alone will not contain this work. Later packaging commits may add this handoff without changing those scripts.

## 2. Same-station execution — exact paths

The user has confirmed the next AI will work on this same station. Use the existing local files directly. Do not clone another repo, apply patches to the already implemented branch, or depend on old temporary clones. No file upload or reconstruction from chat is needed.

| Purpose | Exact path |
|---|---|
| Read this first | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/NEXT-AI-HANDOFF.md` |
| Repository / command working directory | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/` |
| Authoritative production package | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/` |
| Clean narration inputs | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/spoken/` |
| Structured source | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/briefs.json` |
| Final recordings — create this directory | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/recordings/` |
| Dry masters, if produced | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/recordings/dry/` |
| Production manifest and audio QA — create these | `recordings/PRODUCTION-MANIFEST.json` and `recordings/AUDIO-QA.md`, under the authoritative package above |
| Existing offline playback page | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/player.html` |

Make edits and produce assets in that authoritative repo package. The working-folder copy below is a mirror/reference; do not develop two independent versions. After production, synchronize the approved package back to it with existing content preserved. Record any path that is genuinely missing before using backup recovery instructions.

Canonical origin: `https://github.com/Judge-M/Oct26`.

Local repository containing the implementation:

```text
/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/
```

Package relative to repo root:

```text
docs/handoff/audio-briefs/
```

A hash-verified working copy was also maintained at:

```text
/home/ismaelrodriguez/silent-ridge-audio-briefs/
```

Backup transfer artifacts, unnecessary for normal same-station execution, live beside `outputs/Oct26/`: `silent-ridge-audio-briefs.zip`, `audio-briefs.patch` (cumulative package commits), `facilitation-update.patch` (only the participant-response commit), and `SHA256SUMS.json`. Apply the cumulative patch to the matching base, or only the facilitation patch if `b5633d5` is already present; do not apply both to the same base. Extract the ZIP at `docs/handoff/audio-briefs/` for its repo-relative source links to resolve.

Treat `prior-art/` in the working folder as history. `MASTER-HANDOFF.md` is an unchanged inherited planning document with known stale details; this handoff plus REVIEW, FACILITATION, RUNBOOK and INJECTION-PLAN contain the accepted corrections. The original two/three-brief drafts must not replace the current seven.

## 3. Read in this order

1. This document, then [REVIEW.md](REVIEW.md) for corrected assumptions.
2. [FACILITATION.md](FACILITATION.md) and [RUNBOOK.md](RUNBOOK.md) for how the brief prompts turn into participant decisions.
3. [INJECTION-PLAN.md](INJECTION-PLAN.md), [briefs.json](briefs.json) and the seven `brief-*.md` production sheets.
4. [VALIDATION.md](VALIDATION.md) for actual checks and limits.
5. Repo ground truth: `facilitator/ground-truth.md`; mechanics: `docs/facilitator-evidence-release.md`; objectives: `docs/learning-objectives.md`; current team workflow: `participants/cells.md`; scoring: `facilitator/assessment-aar.md`.
6. For the answer-key audit: `docs/rehearsal/evidence/rehearsal-20261018/completed-rerun.md`; for narrative wording: `ridge/scenario_narrative_v1.json`. The schedule model is planning arithmetic, not observed pacing.

If editing the repo, first follow its `AGENTS.md` and required handoff reads. Keep this work bounded to brief production; do not repair deployment, change scoring or rewrite evidence as a side task.

## 4. Design intent from the assessment

The user’s podcast assessment asks whether this feels like investigating an incident or completing eighty questions. The accepted response is stronger facilitation and participant reasoning, while preserving the forensic content.

The opening establishes uncertainty. The injects invite revised assessments when evidence changes. The final cue requests an evidence-bounded recommendation. Participants must then explain, defend or revise their own conclusions; the platform's pre-authored findings and EXCON's recordings must not do that reasoning for them.

Do not add a villain, fictional harm, a branching outcome, new tickets, a leaderboard reward, or a facilitator-supplied solution to create excitement. A defensible change in confidence and justified uncertainty are valid dramatic outcomes. Technical test passes do not establish that the exercise is fun.

## 5. Seven assets and release gates

The controller publishes follow-up evidence automatically. EXCON observes verified delivery, then reads/plays the corresponding cue and posts its full echo. The table is an asset index, not a compulsory narrative sequence.

| Cue | Filename stem | Dependent/seam | Completed prerequisites | Speech estimate | LO |
|---|---|---|---|---|---|
| 01 | `brief-01-opening-task` | Opening seam | Organizer seam | ~71 s | LO2, LO7, LO8 |
| 02 | `brief-02-inject-a-reset` | T07 | T06 | ~30 s | LO4 |
| 03 | `brief-03-inject-b-superseded` | T09 | T08 | ~30 s | LO5, LO2 |
| 04 | `brief-04-inject-c-unresolved` | T11 | T10 | ~33 s | LO6, LO5 |
| 05 | `brief-05-inject-d-payload` | T19 | T01, T05 | ~33 s | LO2, LO5 |
| 06 | `brief-06-command-decision` | T20 | T07, T09, T11, T19 | ~49 s | LO5, LO7, LO8 |
| 07 | `brief-07-endex-standdown` | ENDEX seam | Organizer seam | ~27 s | LO8 |

Release files: T07 → `identity/late-auth.csv`; T09 → `server/version-comparison.csv`; T11 → `hunting/late-inventory.csv`; T19 → `network/dlp-body.txt` and `network/dlp-metadata.json`; T20 → no new file.

Cues 02–05 can occur in any observed release order. T19 can arrive first. Teams claim work dynamically; the rehearsal's team assignments are not an event-day roster. T20 unlock does not imply all twenty tickets are complete. ENDEX happens at the organizer's actual closing seam, even if T20 remains locked; in that case omit cue 06.

Before an inject, require prerequisites complete, dependent present in controller status, pending deliveries zero, healthy diagnostics, and the real IRIS task plus named participant files visible. Do not manually copy vault files or trigger evidence by audio. No fixed elapsed inject times and no clock-correction announcement.

Full state-path selection, commands, announcement verification and duplicate-avoidance ledger are already in RUNBOOK. Production does not require connecting to or modifying a live event.

## 6. Keep the participant-response layer live

These activities supplement the seven recordings. They are not three more prerecorded answers. Use the exact prompts, response scaffolds and feedback examples in FACILITATION.

| Activity | Trigger | Timebox and behavior |
|---|---|---|
| A — interim command update | Issued first-update deadline, independent of releases | 60 s participant assessment; 20 s another cell challenges; 20 s defense/revision; 20 s specific feedback. |
| B — evidence revision | A cell has investigated one verified release | 30 s before/new evidence/after; 10 s challenge; 10 s response; 10 s feedback. Once per event, not after every inject. |
| C — recommendation | After verified T20 availability and cue 06 | 60 s recommendation, alternative and tradeoff; 20 s challenge; 20 s defense/revision; 20 s feedback. |

Live facilitator prompts (retain as live interaction, outside the seven recordings):

- **A:** “Incoming watch, give command a sixty-second update. State your current assessment and confidence, cite the evidence, name the most important uncertainty, and recommend the next defensive or investigative step. Another cell will challenge one claim. Use only evidence currently available to you.”
- **B:** “What did you assess before this evidence arrived? What does the new evidence support now? Explain what changed in the claim or confidence, and what still cannot be established. If your conclusion stayed the same, explain why.”
- **C:** “Give command one proportionate containment recommendation and one alternative. Explain the evidence supporting your choice, the expected benefit, the disruption or evidence-preservation tradeoff, and what additional evidence would change your recommendation. A second cell will challenge the choice. These are recommendations to simulated command; do not carry out the actions.”

Rotate cells and spokespeople. Other cells compare with their own evidence and prepare a question. Praise source citation, a justified revision or restraint; do not reveal a scored value or resolve a gap in feedback. No new score, report submission or unlock gate.

A and C supply two active cross-cell briefings. B may precede A if analysis is ready first. If B is not ready, defer it to the AAR. If T20 stays locked, omit cue 06 and use C's generic incomplete-assessment fallback before ENDEX, or defer to discussion of preserved findings in the AAR at the hard stop. Never pretend unavailable evidence arrived or resume investigation after ENDEX.

The three exchanges total five minutes. Inject/synthesis speech is about 175 seconds: together about 7 minutes 55 seconds within the existing ten-minute facilitated allowance, leaving roughly two minutes for transitions and sound cues. Opening belongs to orientation; ENDEX to the AAR seam. Do not add a second ten-minute recap. These figures are unmeasured budgets.

For live exchanges the organizer pauses and verifies elapsed-clock mode through the event runbook, then resumes at the timebox end through normal readiness gates even if the briefing is incomplete. The recordings/player do not operate the controller. Keep private observations out of GitHub.

## 7. Canon and spoiler constraints

The premise is a cooperative defensive investigation into suspected disclosure of fictional Patrol LANTERN's movement details. Incoming watch starts at exercise time 09:30Z; no harm is confirmed. Investigation is read-only. Do not contact real personnel, execute evidence, or direct the patrol. The controller plays simulated command.

The scripts do not supply protected workstations, executables, accounts, sessions, versions, sector/window/check-in values, addresses, request IDs, hashes, discovery times or the scored remediation action. They ask questions without giving the ticket answers. LANTERN and the opening handover time are allowed premise information. The opening remains neutral about reset/viewer ordering.

Intentional gaps stay unresolved: original delivery path, token contents, human attribution/reading, activity within collection gaps, unobservable host runtime, uncollected systems and actual use of the disclosed information. Do not turn a connection or acknowledgement into proof of a person reading a payload. Do not equate one denied request with universal absence of disclosure.

The exact notices already close every script:

> All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
>
> OPERATION SILENT RIDGE — EXERCISE ONLY.

Keep them audible. Opening and closing EXCON language stays intact. Do not speed-read the notices to meet the older 15–25 second inject targets.

The current validator includes the inherited forbidden literals and all eighty accepted-answer entries, with documented premise/safety exceptions. A lexical pass still needs semantic review. The appendix here is the production text, not the ground-truth answer key.

## 8. Voice and audio production

Established voice direction: one calm, clipped, unhurried watch officer. Urgency through brevity, not shouting. Slight downward line endings. Approximately 140 words per minute; maintain question intonation where the script asks a question. Read EXCON as “ex-con”, ENDEX as “end-ex”, and the handover time as written. Do not narrate filenames, trigger notes, tables, code or headings.

Established processing guidance: optional opening squelch, high-pass near 200 Hz, gentle presence at 1–4 kHz, optional low static near −30 dB, and a two-tone closing chime. Keep every word intelligible. Prefer a clean voice master so the organizer can choose less treatment for a noisy room. Sound cues do not introduce any additional words or answer-like telemetry.

Suggested technical defaults for the next producer, not previously validated requirements: WAV PCM at 48 kHz, mono, with consistent gain and no clipping; optional MP3 listening copies. Keep dry masters separately from final radio versions. Measure and report actual format, peak/loudness, duration and sound-cue overhead; the existing estimates cover speech only. Do not claim measured values before rendering/listening.

Final playback basenames must exactly match the seven stems in section 5, with `.wav`, `.mp3` or `.ogg` extensions. The cue desk matches those names when the operator selects local files. It has no scheduler, autoplay or remote upload requirement. With dry and final masters, load only the intended set.

Keep the spoken wording unchanged for this production pass. For TTS pronunciation use provider pronunciation controls or a clearly documented pronunciation layer whose audible words match the script; do not silently rewrite the canonical transcript. If a substantive wording change becomes necessary, document why and synchronize `briefs.json`, spoken texts, production-sheet scripts, runbook echoes, player embedded data and this appendix before validation. Do not abbreviate the text echo.

## 9. Deliverables and acceptance

Produce a facilitator-only `recordings/` folder in the package, containing seven final files with matching basenames; put dry masters in `recordings/dry/` if produced. Deliver:

1. Seven real, playable final recordings, each mapped to its cue and release trigger; retain the existing clean transcripts and exact echoes.
2. A concise production manifest listing filenames, source-text hashes, actual durations/formats, voice/provider, applied processing and checksum for each output. State what was not produced or tested.
3. Listening QA: all words/notices present, questions remain questions, pronunciation consistent, no additions/omissions or clipping, transitions clean, static/chimes do not mask speech, gain consistent. Compare what is actually heard to the script, not only to the provider's success response.
4. Local playback QA in the cue desk where tools permit: all seven filenames recognized, chosen audio plays, other clips stop, no missing-file claim. If UI policy prevents it, record that limit and use supported file/audio checks; do not claim browser acceptance.
5. Updated package ZIP, checksums and README with the exact output location, completed checks and remaining work. If repo files change, make a bounded local commit and state whether anything was pushed. Do not publish or merge merely to complete production.

Run the existing content checker from repo root:

```bash
python docs/handoff/audio-briefs/validate.py
```

Standalone package form:

```bash
python validate.py --repo /path/to/matching/Oct26
```

Follow applicable repo checks for edits. Full suite: `python -m unittest discover -s tests`. A fresh checkout needs the documented LFS preparation before evidence-dependent tests. The prior suite required the real published training binary, verified against `assets/training-binary.json`; do not substitute a pointer, rebuild with a different hash or weaken the check. Container/image acceptance is separate and is not proved by these tests.

Do not leave the organizer with only a plan when your available tools can produce and verify the assets. If rendering is unavailable, deliver the full narration-ready bundle and name the exact missing capability without calling the audio complete.

## 10. Known remaining issues outside production

- Deck source `docs/event-day-deck/pages/03_story.page` has the reset/viewer ordering defect; source and exported deck need a separate coordinated correction. The opening here avoids that ordering and the protected reset time. Other slide wording also reveals more than these scripts.
- The reviewed rerun recorded a deployment-start certificate guard issue. Do not bypass readiness/certificate checks as part of audio work.
- The successful browser reruns were not thirty people investigating concurrently. Room pacing, turn-taking, audio intelligibility and learning outcomes still need a human rehearsal.
- No final mixed audio was generated in the current implementation. This is the next producer's remaining task.
- “Facilitator-only” is a distribution rule, not secrecy supplied by public GitHub. Keep full repo, scripts with metadata and trigger tables away from participant listeners; participants get approved surfaces and released evidence only.

## 11. Exact narration appendix

These are the seven canonical spoken texts at implementation commit `ddd0d91`. Estimates exclude breaths and sound effects. Each source-text SHA-256 below is calculated from the UTF-8 `spoken/*.txt` file, including its final newline. Use the file bytes when verifying the hash. This appendix lets another AI read all approved words even if it receives only this handoff.

### 01 — Opening tasking

Source: `spoken/brief-01-opening-task.txt` · 166 words · ~71 seconds.

SHA-256: `7a1bec5be8ffb075ea9735fe9a176ce1ea01b973e413627dbc26a7438db3793a`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

Operation Silent Ridge. Exercise time, zero-nine-three-zero Zulu. Incoming watch, you have the watch.

Patrol LANTERN is in the field. Disclosure of its movement details is suspected. No harm is confirmed. Do not assume the incident is over.

Endpoint, network, identity, document-service, and security information and event management exports are staged. Establish what moved, how access was gained, and which systems remain affected.

Label each claim confirmed, assessed with confidence, or unknown. Cite evidence. Share findings across cells for the joint assessment. Report even at low confidence. Your first command update is due at the elapsed mark in your issued schedule.

Read-only investigation. Preserve the supplied evidence. Do not contact real personnel, track them, or direct them. No attack is required. Send defensive recommendations to the controller. Command decides any patrol response.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 02 — Identity reassessment

Source: `spoken/brief-02-inject-a-reset.txt` · 71 words · ~30 seconds.

SHA-256: `46423f438b7aa3a2fffddabf62d8b68048f738727df064d9e69a49eed052ab1d`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

Later authentication records are now available. Revisit your access assessment. Did the credential action contain the activity? What does the evidence establish about its effect? Carry the revised finding and its limits into the shared case.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 03 — Movement-information comparison

Source: `spoken/brief-03-inject-b-superseded.txt` · 71 words · ~30 seconds.

SHA-256: `9b514eac58ed95f3ddead52b1a4ef169e9c3949965029da486234570f895c259`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

Superseding movement information is now available. Compare it with the earlier record. Which details changed? Which, if any, remain relevant? Revisit the disclosure scope in your shared finding. Keep the comparison separate from assumptions about harm.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 04 — Scope lead and coverage

Source: `spoken/brief-04-inject-c-unresolved.txt` · 77 words · ~33 seconds.

SHA-256: `d97cbce38ad6f43b3117e5aa8a32c3613dca586af47bf363b4e387ece95a0082`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

Further inventory evidence is now available. Test the host lead against the comparator already supplied. What does a name match establish? What collection would support a stronger conclusion? Record coverage limits before clearing or implicating any system. Share the revised scope assessment.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 05 — Payload verification

Source: `spoken/brief-05-inject-d-payload.txt` · 78 words · ~33 seconds.

SHA-256: `e889a7d13bf75eff7203fe23821178470021ec8f874475603bffdc89dbbcb91c`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

A transmitted body and its metadata are now available. Re-test the earlier transmission assessment against the body itself. Does it support the size-based lead? Separate evidence of transmission from claims about human receipt or intent. Update the shared finding with citations and limits.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 06 — Command decision support

Source: `spoken/brief-06-command-decision.txt` · 114 words · ~49 seconds.

SHA-256: `c68356d9404fb68b5018e4030f0bd51a9fc5628037eb2182e3149d1f3a153a49`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

The final synthesis ticket is available. Bring the shared findings together for command.

Which movement information is supported as disclosed? Is roster disclosure established? Is exposure fully bounded? What can you establish about an adversary? Did the credential action contain the activity?

Label claims confirmed, assessed, or unknown. Distinguish disclosed, denied, and unresolved claims. Recommend proportionate containment, evidence preservation, and targeted collection, with reasons and limits. Provide a reliable technical assessment to the controller. Command decides any patrol response.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 07 — ENDEX stand-down

Source: `spoken/brief-07-endex-standdown.txt` · 62 words · ~27 seconds.

SHA-256: `e98f7d88b2b8a986c0bd9761a42fcd0e460ad92fd7d87c40a9ecf9dfa06d48af`

```text
All stations, this is EXCON. Exercise, exercise, exercise.

Exercise ends. ENDEX. Stand down. Cease investigation. Preserve the shared findings for the after-action review. Bring one supported finding, one remaining uncertainty, and one improvement. Well done.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```
