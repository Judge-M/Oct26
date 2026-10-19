# START HERE — three SOC-manager briefs

Prepared 2026-10-18. Facilitator-only. **Current assignment: scripts and production handoff. No new audio was generated for this edition.**

## The decision to carry forward

Produce exactly three recordings: arrival, post-lunch restart, and halfway from post-lunch restart to ENDEX. Use one original adult female SOC-manager voice, professional, warm, grounded and conversational. These scripts are the current narration source. They supersede the seven-brief production plan, the male commander voice, and earlier opening drafts. The user requested a handoff for another AI to produce the audio.

The user's Jennifer Lawrence reference describes broad qualities: a warm lower-middle register, relaxed American delivery, a little natural vocal texture and understated personality. Create a distinct voice. Use the original-voice prompt below as the synthesis direction; an actor's recording is not a required input.

The speaker is the SOC manager within the exercise; EXCON remains her exercise-control call sign. Command retains patrol decisions. Her personality should come through as a thoughtful manager who knows her team: friendly on arrival, candid after lunch, focused as the end approaches. She asks real questions and makes room for uncertainty.

## Same-station paths

| Purpose | Full absolute path |
|---|---|
| Read first | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/START-HERE.md` |
| Canonical structured scripts | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/briefs.json` |
| Clean narration inputs | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/spoken/` |
| Performance sheets | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/production-sheets/` |
| Exact normalized transcript echoes | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/ANNOUNCE-TEXTS.json` |
| Content/parity checker | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/validate.py` |
| Write new clean masters | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/recordings/clean/` |
| Write new final WAVs | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/recordings/final/` |
| Write listening MP3s | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/recordings/mp3/` |
| Write production manifest and audio QA | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/recordings/PRODUCTION-MANIFEST.json` and `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/soc-manager-three-briefs/recordings/AUDIO-QA.md` |
| Existing local repository | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/` |
| Eventual repository destination, after integration | `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/handoff/audio-briefs/` |

Use these local files directly. A new clone will not contain this station's uncommitted work. Do not reapply old patches or reset the checkout. Existing repo files contain uncommitted seven-script revisions and user-supplied recordings; preserve them.

Current authority is this bundle. The older repository NEXT-AI-HANDOFF.md, MASTER-HANDOFF.md, REMOTE-SETUP-HANDOFF.md, original mirror, ZIPs and cue desk still describe earlier production decisions. They are historical references, not instructions to make seven recordings. Do not copy older operational handoffs into the deliverable; they may contain private connection details. This bundle contains no access credentials and does not authorize remote administration.

## The three cues

| Cue | Exact filename stem | Trigger | Words | Estimated speech at 140 wpm |
|---|---|---|---:|---:|
| 01 | `brief-01-arrival` | Arrival, before investigation | 192 | 82 s |
| 02 | `brief-02-post-lunch` | Actual post-lunch restart | 151 | 65 s |
| 03 | `brief-03-final-approach` | Midpoint from post-lunch restart to planned ENDEX | 168 | 72 s |

All length estimates include the exercise opener and full fiction notices. Budget natural pauses separately. Total estimated speech is 219 seconds; actual room pacing has not been measured.

For cue 03, let R be actual lunch restart and E be planned ENDEX: play at R + (E − R)/2. Illustrative only: a 13:00 restart and 15:00 ENDEX put cue 03 at 14:00. Do not hardcode those example times. If the agenda compresses so two cues would collide, have the organizer select one live transition rather than playing two back-to-back. The third cue is not ENDEX. The facilitator calls stand-down live; there is no fourth recording.

These are agenda cues, independent of evidence releases and tickets. Audio does not unlock, announce or prove delivery of evidence. Never imply teams have completed a stage, established disclosure or reached the synthesis ticket merely because a cue plays.

## Voice prompt — use for all three

> An original adult female SOC manager addressing her own analysts. Natural American English, warm lower-middle register, light natural vocal texture, clear diction, steady confidence, and an approachable conversational manner. She sounds experienced and engaged. A slight smile on the welcome and the line about tabs; thoughtful curiosity in questions; firmer focus in operational boundaries. Approximately 135–150 words per minute, varying naturally with sentence length. Short breaths and comfortable pauses between ideas. Deliver the words as an attentive colleague speaking to a room. Use one consistent voice across all three briefs.

Keep paragraph-level performance direction outside spoken text. Do not narrate headings, stage directions, filenames, timestamps, LO labels or trigger notes. Let questions rise naturally; let statements settle. Use contractions as written. Natural breaths are welcome; added words, ad-libs, invented incidents and dramatic sighs are not part of the transcript. The brief's human tone should come from phrasing, pace and attention to the listener.

Pronunciation: SOC = “sock”; EXCON = “ex-con”; LANTERN = “lantern”; Zulu = “zoo-loo.” Speak “zero-nine-three-zero” as the written time. The exact fiction notices remain audible and unhurried. There are no bracketed performance tags in the clean inputs.

## Produce and review

1. Read this handoff and all three clean texts. Check the selected voice can sustain natural questions and steady operational instructions.
2. Render a short arrival sample using the original female voice direction. Audition it; if needed adjust the voice before batching. Continue production within the user's authorized scope rather than imposing another mandatory approval gate. Do not reuse the older male clone or pitch-shift those takes into the new voice.
3. Generate all three from the exact clean inputs. With TTS, render at sentence or paragraph boundaries if long passages loop, truncate or flatten. Keep one voice and a consistent acoustic setting. Preserve any required provider watermark and record the tool/model/voice version used.
4. Keep clean masters. Make final WAVs at 48 kHz, mono, PCM16. Aim around −16 LUFS integrated with true peak at or below −1.5 dBTP; report actual measurements. Apply gentle leveling where useful. A clean SOC-room delivery is the default; optional comms texture must remain subtle. Avoid heavy filtering that removes the warmth of this voice.
5. Export optional MP3 listening copies with the same three stems. Never overwrite the user's original WAVs or the previous voice-refresh edition.
6. Compare each recording against its clean text. Check dropped/added words, repeated phrases, pronunciation, question intonation, missing notices, long dead pauses and abrupt cuts. ASR is a useful second check and may mishear words; do not label it human listening acceptance. Re-render defects rather than hiding them with music or static.
7. Record actual duration, sample format, integrated loudness, peak, voice/model, processing, text SHA-256, audio SHA-256 and review status in the production manifest. State any unperformed listening or browser checks explicitly. A file path, script or synthesis request alone is not a completed recording.
8. Deliver all three playable files, clean masters, matching transcripts, manifest, QA report, checksums and one current ZIP. Keep it facilitator-only, outside runtime/public. Return full paths for the organizer.

Local tool information is a starting point, not a dependency: `/home/ismaelrodriguez/apps/chatterbox/` contains a CPU Chatterbox installation and model. Its existing reference recordings and render scripts target the superseded male voice. Do not run them unchanged. There is no approved female reference bundled here. Use an original synthetic female voice or an appropriately authorized reference, depending on your tools. Inspect current disk space before adding models; this station had roughly 1.5 GB free at handoff preparation. Do not delete unrelated caches or change GPU drivers to complete narration.

## Live facilitation — outside the recordings

After the post-lunch cue, allow two minutes: 60 seconds for a cell's assessment with confidence, evidence and key uncertainty; 20 seconds for another cell's challenge; 20 seconds for a defense or revision; 20 seconds for specific facilitator feedback. Rotate speakers. Other cells compare with their own findings.

After cue 03, use the same two-minute structure for one containment recommendation, one alternative and a disruption/evidence-preservation tradeoff. Invite a challenge and a reasoned response. This exchange can use incomplete findings and does not depend on T20 being available.

An optional one-minute evidence-revision exchange can happen live once a cell has actually analyzed new evidence: 30 seconds before/new evidence/after, then 10 seconds each for challenge, response and feedback. If not ready, defer it to the AAR. It is not another audio asset.

Praise source citation, justified uncertainty and revisions supported by evidence. Keep feedback free of scored values. These are coaching exchanges, not new scores, submissions or unlock gates. Use the existing event runbook for any pause/resume; the audio does not operate the controller. The two core exchanges total four minutes; the optional revision adds one minute. Reconcile these and the recordings with the actual lunch/event agenda; earlier schedule arithmetic is not measured pacing.

## Scenario and spoiler boundaries

The repo is ground truth for scenario facts and release mechanics. This new bundle is ground truth for current voice, narration and cue count. All spoken content is fictional exercise material. The incoming watch starts at exercise 09:30Z. Patrol LANTERN is already in the field; disclosure is suspected; harm is not confirmed. Participants investigate read-only and recommend to the controller. Command decides patrol actions.

Do not add accounts, hosts, executable names, session IDs, document versions, sectors, movement windows, checkwords, addresses, request IDs, hashes, incident times or the scored remediation action. Do not turn an acknowledgement into proof of human reading. Preserve gaps in original delivery, token contents, attribution, collector coverage, unobservable runtime, uncollected systems and actual use of information. The scripts must not answer the investigation.

The protected 80-answer source and inherited forbidden-literal list are checked by validate.py. Lexical checks supplement semantic review; they cannot prove that narration is spoiler-free. Only the premise name and the two established opening safety statements receive documented exceptions.

Full source paths for fact checks:

- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/facilitator/ground-truth.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/ridge/scenario_narrative_v1.json`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/learning-objectives.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/facilitator-evidence-release.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/rehearsal/evidence/rehearsal-20261018/completed-rerun.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/participants/cells.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/facilitator/assessment-aar.md`
- `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/docs/schedule-model.md`

## Repository integration, if included in production

The existing offline player, JSON, markdown, runbook echoes and validator still assume seven assets. They have not been migrated by this scripts-only handoff. Do not claim that they are ready for these three recordings. The three clean text files in this bundle are the only narration input for this edition.

After rendering, integrate as one bounded task following `/home/ismaelrodriguez/Documents/Codex/2026-10-18/done-wrote-master-handoff-md-22/outputs/Oct26/AGENTS.md` and its required handoff reads. Preserve current uncommitted files and original recordings before edits. Update the active brief JSON, spoken texts, three production sheets, README, RUNBOOK, INJECTION-PLAN, FACILITATION, NEXT-AI-HANDOFF, player data and validator together; archive superseded active scripts rather than leaving seven selectable cues. Keep three agenda triggers and exact full-text announcement echoes. Do not change automatic evidence gates or scoring. Verify playback filenames match the three stems above. No controller connection is needed for audio production.

Run repository checks required by AGENTS.md if integrating there. Prior reports of 467 passing tests apply to earlier source states and are not new acceptance evidence. The training-binary tests require the documented real Git LFS bytes; follow BUILD-FIRST and verify the manifest. Do not treat a pointer as the binary or weaken checks. Source validation, audio QA, live acceptance and event readiness are distinct. Do not publish, push, merge or upload a facilitator package merely to finish production.

## Complete scripts — narration only

These are reproduced from the clean files and checked for exact parity. Read only each code block when narrating; titles are not spoken.

### 01 — Arrival — take the watch

```text
All stations, this is EXCON.

Morning, everyone. I'm your SOC manager for Silent Ridge. Get settled, and let's take the watch.

We're picking up at zero-nine-three-zero Zulu, exercise time. Patrol LANTERN is already in the field. We suspect its movement details have been disclosed. No harm is confirmed. We need a careful assessment of what happened and what needs attention.

Your evidence comes from endpoints, network traffic, identity records, document services, and security monitoring exports. Work together. Share the source behind a finding, your confidence in it, and the uncertainty that still matters.

If another cell sees it differently, hear them out. Changing your mind when the evidence changes is part of the job. I'd rather you raise a useful question early than leave the next cell guessing.

Keep this read-only. Preserve the evidence. Do not contact, track, or direct real personnel. No attack is required. Send recommendations to the controller. Command decides any patrol response.

All right. Let's get to work.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 02 — Post-lunch — rebuild the shared picture

```text
All stations, this is EXCON.

Welcome back, everyone. Let's get our heads back in the room.

Before we disappear into our own tabs, take a moment with the shared findings. What can you support? What are you still assessing? What remains open? Check the evidence currently available to you.

Give another cell a short update: your strongest finding, the source behind it, and the uncertainty that matters most. Let them challenge one claim. Walk them through your reasoning, and revise it if you need to.

If you're stuck, say where. Someone else may have the piece you're missing. Agree your next useful step together.

Keep the investigation read-only, and send recommendations to the controller. Let's keep each other in the picture.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```

### 03 — Final approach — defend the assessment

```text
All stations, this is EXCON.

All right, everyone. Let's bring the pieces together.

We've still got time to do useful work. Start shaping the assessment you can defend with the evidence you have.

What can you support as disclosed? What remains unproven? If you can't establish something yet, say so. I need to understand how sure you are, and why.

Recommend a proportionate containment response. Explain the evidence behind it, an alternative you considered, and the tradeoff for disruption or evidence preservation. What would change your mind?

Another cell will challenge your reasoning. Give them room to do that. Work through the challenge, and revise the assessment if it changes your view.

Keep this read-only. Send your technical assessment to the controller. Command decides any patrol response.

Keep talking to each other. Let's make the remaining time count.

Good hunting. EXCON, out.

All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person.
OPERATION SILENT RIDGE — EXERCISE ONLY.
```
