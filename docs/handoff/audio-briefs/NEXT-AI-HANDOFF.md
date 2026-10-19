# Audio-production handoff

The existing introduction recording is already included at `recordings/brief-01-introduction.wav`. Produce the missing outro recording using the text byte-for-byte from:

- `spoken/brief-02-exit.txt`

The speaker is **Faye Maxwell, SOC supervisor for Operation Silent Ridge**. Use one consistent adult female voice with natural American English, clear diction, grounded authority and controlled urgency. The performance should sound like a supervisor speaking to trusted analysts, not an announcer or trailer narrator.

Pronunciation guidance:

- SOC: “sock”
- S6: “ess six”
- LANTERN: “lantern”
- Zulu: “zoo-loo”
- WS-17 / WS-31: “double-u ess seventeen / thirty-one”
- S-41: “ess forty-one”
- req-72: “reck seventy-two”
- CEDAR: “cedar”

Introduction direction: brisk and focused, with measured emphasis on the potential risk to people, mission, systems and evidence. Do not imply confirmed harm.

Conclusion direction: identify Faye by name, then deliver the confirmed disclosure and residual CEDAR exposure with measured gravity. Slow for evidentiary limits and the unresolved WS-31 lead. Make containment directions crisp. Close with calm authority, not celebration.

Do not add, omit or paraphrase words. Do not speak headings, production notes, exercise framing or EXCON terminology. Do not append music, sound effects or ad-libs unless the organizer separately approves them.

Output stem:

- `brief-02-exit`

Put candidate outro recordings outside the repository for listening review. Only accepted final outro audio should be added in a later, clearly labeled change. Do not replace or edit the included introduction unless the organizer explicitly requests it.

Reject any source directory containing earlier three-brief, seven-brief, midpoint, post-lunch, generic handover or superseded voice materials. Validate the repository package before production:

```bash
python docs/handoff/audio-briefs/validate.py
```
