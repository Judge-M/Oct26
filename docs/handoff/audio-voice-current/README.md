# Current voice — SOC-manager narration

Facilitator-only. This folder holds **only the current approved voice** and its renders.
Earlier voice attempts (commander/male and the prior female clone) are intentionally excluded.

## Contents

| File | Description |
|---|---|
| `reference_new.wav` | Reference clip for the current voice (clean solo window, ~11 s). |
| `reading-01.wav` | Rendered reading of the first opening draft. |
| `reading-02.wav` | Rendered reading of the revised opening draft (with the "we need to move" urgency pass). |
| `reading-02.txt` | Source text for `reading-02.wav`. |
| `render_voice.py` | Renderer used on the GPU station (Chatterbox, CUDA, chunked). |

## Voice / production notes

- Engine: Resemble AI Chatterbox (open source, full 500M English model). Every file carries the
  automatic Resemble PerTh watermark.
- Settings: `cfg_weight=0.3`, `exaggeration=0.4`, `temperature=0.9`.
- Chunking: paragraph-boundary chunks ≤55 words (model caps at ~1000 speech tokens ≈ 40 s).
- Pronunciation layer (applied to TTS input only): SOC→"sock", EXCON→"ex-con", LANTERN→"lantern",
  S6→"S six", IT→"I T", Zulu→"zoo-loo", `zero-nine-three-zero` as written.
- Output: 48 kHz mono PCM-16, peak-normalized to about −1 dBFS.

## Not included

- Audio rendered with the superseded voices (excluded on purpose).
- Loudness-finalized / MP3 variants and the breath-pause treatment (added later, not yet applied here).
- Human listening acceptance (not performed).

## Exit brief render (for review)

- `exit-brief.wav` — the exit brief (main's `brief-02-exit` text) rendered in the current voice.
- `exit-brief.reading-input.txt` — the exact text fed to the TTS engine (canonical text plus a
  pronunciation layer: IP read digit-by-digit, Zulu times as military digits, CEDAR/AMBER/BLUE
  de-shouted to words, past-tense "read" respelled "red").
