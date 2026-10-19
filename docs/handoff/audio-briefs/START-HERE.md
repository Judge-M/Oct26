# Produce the two Operation Silent Ridge briefs

Current production handoff, 2026-10-19. Organizer/producer only. This checkout contains exactly two current scripts; no matching recordings ship yet. Earlier seven/three-brief designs and male-commander direction are superseded.

The original female speaker is the **watch floor supervisor in charge of Operation Silent Ridge**. The **S6 IT department flagged issues** and she brought separate teams in to assist the SOC's digital forensic investigation. She is warm, professional, confidently direct, lightly wry and urgent about possible risks to LANTERN's personnel and mission. Keep these stakes conditional; harm is unconfirmed and the exit does not announce a resolved incident.

The user's explicit 2026-10-19 direction removes all spoken exercise/fiction explanations, EXCON calls and old notices. Do not append them to audio. The project remains a fictional defensive CTF; organizer context stays outside narration. The operator represents her in the event. Recommendations go to command through that operator, not to real personnel or systems.

## Read and locate inputs

All paths below are relative to the checkout root, so a fresh machine needs no old chat, home directory or temporary clone. Resolve the actual root with `git rev-parse --show-toplevel`.

| Purpose | Repository path |
|---|---|
| Production handoff | docs/handoff/audio-briefs/NEXT-AI-HANDOFF.md |
| Canonical structured scripts | docs/handoff/audio-briefs/briefs.json |
| Introduction input | docs/handoff/audio-briefs/spoken/brief-01-introduction.txt |
| Exit input | docs/handoff/audio-briefs/spoken/brief-02-exit.txt |
| Per-brief performance sheets | docs/handoff/audio-briefs/brief-01-introduction.md and brief-02-exit.md |
| Full written echoes | docs/handoff/audio-briefs/ANNOUNCE-TEXTS.json |
| Local cue desk | docs/handoff/audio-briefs/player.html |
| Verify content | python docs/handoff/audio-briefs/validate.py |
| Write clean masters | docs/handoff/audio-briefs/recordings/clean/ |
| Write final WAVs and listening copies | docs/handoff/audio-briefs/recordings/final/ and recordings/mp3/ |
| Write manifest and audio QA | docs/handoff/audio-briefs/recordings/PRODUCTION-MANIFEST.json and recordings/AUDIO-QA.md |

Read README.md, REVIEW.md, RUNBOOK.md and INJECTION-PLAN.md in this directory. Use FACILITATION.md for optional live exchanges; do not prerecord participant answers. Follow repository AGENTS.md and required handoff reads when editing. Keep production bounded to briefs, with evidence, scoring, release dependencies and live event state unchanged.

## Two cues

Introduction: before investigation after teams assemble; stem `brief-01-introduction`, 264 words, about 113 seconds at 140 words/minute before pauses.

Exit: at the actual end of the assisting teams' assignment; stem `brief-02-exit`, 211 words, about 90 seconds before pauses. Play even with incomplete analysis. It hands existing case work to the next watch and releases teams; it does not end the underlying operation or add a report/approval gate.

Neither cue announces evidence release, unlocks tickets or operates the clock. There is no lunch, midpoint or additional recorded stand-down. Do not reuse old takes with different words or notices. Operator announcements use the full exact echoes, not summaries.

## Voice and performance

> An original adult female watch floor supervisor leading Operation Silent Ridge. Natural American English, warm lower-middle register, light vocal texture and clear diction. Professional, grounded, conversational and comfortably authoritative, with controlled urgency. She knows the stakes and expects people to think. Emphasize the potential risk to people and the mission without implying harm is confirmed. Let the words about timely findings land clearly. A small smile in the lightly wry lines; thoughtful curiosity around evidence; steady precision around operational instructions. She respects her analysts and takes responsibility for carrying their work to command. Approximately 135–150 words per minute, with natural breaths and short pauses between ideas. Keep one consistent voice and acoustic setting across both briefs.

Read the text as a person talking to colleagues. Let sentence rhythm vary; keep the wry lines understated. Do not add laughter, sighs, ad-libs or theatrical aggression. Performance notes and headings are not spoken. Pronounce **SOC** “sock,” **S6** “ess six,” and **LANTERN** “lantern.” Operation Silent Ridge is her operation, not a training title she is announcing. Do not supply a personal name, rank, threat actor or invented outcome.

## Production and acceptance

1. Audition a short introduction sample for warmth, natural phrasing and controlled urgency, adjust if needed, and continue the authorized production work. Use one original synthetic female voice or an appropriately authorized reference. Do not promise an actor's exact voice. Keep required provider/model watermarking.
2. Render both exact clean texts with a consistent voice and acoustic setting. Chunk at sentence/paragraph boundaries if needed to prevent truncation or repetition. Keep performance notes, headings and metadata unspoken. Urgency comes from focus and emphasis; do not race through the stakes or turn conditional risk into a confirmed outcome.
3. Preserve clean masters. Export final 48 kHz mono PCM16 WAVs with the exact two stems and optional matching MP3s. Aim around −16 LUFS integrated and true peak at or below −1.5 dBTP. Report actual duration, format, loudness, peak and processing. A clean watch-floor delivery is the default; heavy filtering/static/chimes should not mask warmth or words.
4. Check every recording against its source for omissions, added/repeated words, pronunciation, pauses, cut-off tails, clipping and natural delivery. Confirm old exercise notices are absent. ASR can help, but state its limits and do not call it human listening acceptance. Do not describe files or requested synthesis as completed audio.
5. Deliver two playable finals, clean masters, listening copies, exact transcripts, a production manifest, QA and checksums. Record source-text/audio SHA-256, voice/model/settings, pronunciation substitutions, processing, actual measurements and review status. State unperformed checks explicitly. Keep private references, access details and unrelated recordings out of public artifacts.
6. Test local file matching and playback in player.html if tools permit, including stopping the other cue. If browser policy prevents it, record the limit; do not claim playback acceptance. Update VALIDATION.md and README with actual recording readiness. Run the content checker and required repository checks for edits.

## Canon and boundaries

The S6 referral and supervisor role are user-authored framing. Do not invent how S6 detected the issues or alter any evidence. Preserve suspected disclosure, patrol already in the field and harm unconfirmed. Read-only and original-evidence boundaries remain explicit. Technical recommendations are not authorization to contain systems or direct the patrol.

Do not narrate scored hosts, accounts, sessions, executables, document versions, sectors/windows/checkwords, addresses, hashes, request IDs, incident times or the scored remedy. Preserve the intentional gaps listed in REVIEW.md. Lexical audit checks all 80 answer entries and inherited forbidden literals but supplements semantic review. The package remains facilitator-only during event distribution, despite public source hosting.

Ground truth and mechanics remain in facilitator/ground-truth.md, participants/handover.md and docs/facilitator-evidence-release.md. Learning objectives are in docs/learning-objectives.md. The answer audit uses docs/rehearsal/evidence/rehearsal-20261018/completed-rerun.md. AAR stays in facilitator/assessment-aar.md. No live event connection, deployment, push or merge is required just to render audio.

## Complete narration scripts

Only these script blocks are spoken. They match the clean files and JSON exactly.

### 01 — Introduction — Operation Silent Ridge

```text
All right, everyone. Thanks for coming in. We need to move.

I'm the watch floor supervisor in charge of Operation Silent Ridge. The S6 IT department has flagged issues that need a closer look. I've brought your teams in to assist our SOC with the digital forensic investigation.

We're investigating a suspected disclosure of movement details for Patrol LANTERN, already in the field. No harm is confirmed.

If those details reached someone outside our control, they could anticipate the patrol's movements. That could put people and the mission at risk. A rushed response could also disrupt essential systems or damage evidence. We need to move quickly and be able to defend our decisions.

Establish what happened, what information may have been exposed, and which systems need further attention. Bring me significant findings as soon as you can support them, with the uncertainty alongside. Command needs a reliable picture while it can still act on it.

You'll have endpoint, network, identity, document-service, and security monitoring records to work from. Give me the source behind a finding, your confidence in it, and what you still can't establish. A good hunch earns another look. A finding needs evidence.

You're separate teams, but I need one shared picture. Share your findings. Challenge each other's reasoning. If your favorite theory doesn't hold up, let it go. That's progress.

Keep the investigation read-only and the original evidence untouched. Don't scan external systems or run programs recovered from evidence. Bring technical recommendations to me. I'll coordinate with command; patrol decisions stay with them.

All right. Show me what the evidence supports.
```

### 02 — Exit — investigation handover

```text
All right, everyone. We're closing your teams' assignment to Operation Silent Ridge.

I need command to see anything that could affect LANTERN's safety. Put it up front, with the evidence and uncertainty beside it. A critical finding buried in your notes won't help the next watch.

Before you disappear, leave the next watch a case they can actually follow. Record your findings and source references in the shared case. Make clear what you can support, how confident you are, and what remains unresolved.

Loose ends belong in the handover. They don't get to vanish because we're out of time. Leave the open leads and collection limits visible, with the next useful step for whoever picks them up.

Set out your recommended defensive steps, the evidence behind them, an alternative you considered, and the impact on operations or evidence preservation. I'll take those recommendations to command.

Close out your investigative work at this handover. Preserve the evidence, your working notes, and the shared case record. Further collection and operational action will be coordinated through me.

Thank you for the work you've put into this. I'll take the difficult questions to command. Make sure I've got your evidence with me.

Your teams can stand down from this assignment. I'll take it from here.
```
