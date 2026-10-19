# Validation record

`validate.py` verifies:

- Exactly two canonical spoken scripts and production sheets exist.
- No audio files or voice-rendering scripts are present.
- The introduction contains no answer-key spoilers or spoken exercise framing.
- The conclusion matches the canonical final assessment and contains its required limits and actions.
- Structured JSON, announcement echoes, word counts and SHA-256 hashes match the canonical spoken files.
- Every local link in the cue desk resolves.
- The cue desk has no network calls.

Validation cannot replace human review of timing, pronunciation or final produced audio. Any later recording change requires a separate listening-acceptance record.
