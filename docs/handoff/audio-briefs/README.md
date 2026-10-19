# Operation Silent Ridge — two watch-floor briefs

Two narration-ready scripts: an introduction and an exit handover. An original female **watch floor supervisor in charge of Operation Silent Ridge** brings separate teams into a digital forensic investigation after the **S6 IT department flags issues**. She is professional, warm, lightly wry and urgent about evidence that could affect Patrol LANTERN. Risks to people, the mission, systems and evidence remain conditional; harm and resolution are not invented.

The spoken scripts stay entirely within the situation. The user's 2026-10-19 direction replaces the earlier spoken exercise notices and EXCON framing. Organizer-facing scenario context stays in these documents. The underlying project remains a fictional defensive CTF. The operator represents the supervisor and simulated command; narration authorizes no external action.

Start with [the production handoff](NEXT-AI-HANDOFF.md). Open [the offline cue desk](player.html) for live reading or locally selected recordings. No matching audio ships yet. Prior three- and seven-brief takes are superseded; do not load them as these cues.

| Asset | Trigger | Words | Estimated speech |
|---|---|---:|---:|
| [Introduction](brief-01-introduction.md) | Teams assembled, before investigation | 264 | 113 s |
| [Exit](brief-02-exit.md) | Actual end of the teams' assignment | 211 | 90 s |

Timing assumes 140 words/minute before extra pauses. Neither cue is tied to a ticket or release; the exit can occur with unresolved findings. There is no lunch, midpoint or additional recorded stand-down cue. The exit releases the assisting teams while the operation may continue.

References: [RUNBOOK](RUNBOOK.md), [cue/release boundaries](INJECTION-PLAN.md), [optional live coaching](FACILITATION.md), [review and canon](REVIEW.md), [validation](VALIDATION.md), [structured scripts](briefs.json), [clean inputs](spoken/), [full normalized echoes](ANNOUNCE-TEXTS.json), [recording destination](recordings/README.md).

Keep this package, presenter page and checkout on the operator machine; distribute only approved participant surfaces and runtime/public. “Facilitator-only” describes event distribution and does not make a public GitHub repository secret. Credentials, real rosters, live state and private production connection notes do not belong here.

From the checkout root:

```bash
python docs/handoff/audio-briefs/validate.py
python -m unittest discover -s tests
```

Keep JSON, clean text, production sheets, handoff appendices, runbook echoes and embedded player data synchronized. CI runs the content/parity checker on Linux and Windows. Validation does not connect to or modify an event. No runtime or image source is changed by this package.
