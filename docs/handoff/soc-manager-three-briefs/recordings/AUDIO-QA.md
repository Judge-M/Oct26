# Audio QA — SOC-manager briefs (3)

Produced 2026-10-18. Voice: original adult female SOC manager, **Jennifer Lawrence voice clone**
(Chatterbox full model, GPU render on station 192.168.1.193). Engine: Resemble AI Chatterbox
(open source); every file carries the automatic Resemble **PerTh** watermark.

## Files

| Cue | Stem | Clean master | Final WAV | MP3 | Duration | Format |
|---|---|---|---|---|---|---|
| 01 | brief-01-arrival | recordings/clean/brief-01-arrival.wav | recordings/final/brief-01-arrival.wav | recordings/mp3/brief-01-arrival.mp3 | 66.74 s | WAV PCM16, 48 kHz, mono |
| 02 | brief-02-post-lunch | recordings/clean/brief-02-post-lunch.wav | recordings/final/brief-02-post-lunch.wav | recordings/mp3/brief-02-post-lunch.mp3 | 46.90 s | WAV PCM16, 48 kHz, mono |
| 03 | brief-03-final-approach | recordings/clean/brief-03-final-approach.wav | recordings/final/brief-03-final-approach.wav | recordings/mp3/brief-03-final-approach.mp3 | 54.14 s | WAV PCM16, 48 kHz, mono |

## Technical checks performed (PASS)

- Playable WAV: `pcm_s16le`, 48 kHz, mono, 16-bit — verified with ffprobe (no 64-bit-float file).
- No clipping: true peak at or below −1.5 dBTP on all three finals.
- Loudness: integrated −16.5 / −16.3 / −16.4 LUFS (2-pass loudnorm) — consistent set, on target.
- Source parity: each render uses the canonical `spoken/*.txt`; pronunciation layer applied to the
  TTS input only (`SOC`→"sock", `EXCON`→"ex-con", `LANTERN`→"lantern", `Zulu`→"zoo-loo",
  `zero-nine-three-zero` as written). Canonical texts byte-identical (`validate.py` PASS).
- Text hashes, word counts and echoes match `briefs.json` / `ANNOUNCE-TEXTS.json` after the opener
  change (opener "Exercise, exercise, exercise." removed).
- One voice and identical settings across all three (cfg 0.3 / exaggeration 0.4 / temperature 0.9).

## NOT performed — outstanding

- **Human listening acceptance.** No ASR is installed on this station, so no automated word-check and
  no human ear-pass was done. A person must compare each file against its clean text: dropped/added
  words, repeated phrases, question intonation, the two fiction notices, dead pauses, abrupt cuts.
- Browser playback in the repo cue desk (the existing player still assumes the seven old assets and
  has not been migrated to these three).
- Room pacing / event readiness.

Per the handoff: a file path or synthesis request is not a completed recording — these are rendered,
measured and playable, but listening acceptance remains the reviewer's step.
