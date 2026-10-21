# Event-day room briefs

The room presentation is split into two short decks. Participant setup no longer
lives in the slides. The public registration page and private team handout are
the source of truth for logins, desktops, scoring, help, and troubleshooting.

## Opening brief

Use `opening-brief.pptx` in Microsoft PowerPoint or `opening-brief.odp` in
LibreOffice Impress. It contains five slides:

1. Operation Silent Ridge title;
2. the situation and mission;
3. the high-level claim, investigate, answer, share workflow;
4. the embedded introduction video, set to play automatically;
5. the participant landing-page address.

After the video, leave slide 5 projected while captains open:

```text
https://ctfd.cyberexperts.org/silent-ridge/register
```

## Closing brief

Use `closing-brief.pptx` in Microsoft PowerPoint or `closing-brief.odp` in
LibreOffice Impress. It contains three slides:

1. a neutral final-assessment holding slide;
2. the embedded outro video, set to play automatically;
3. an editable `And the winner is...` reveal.

Replace `[TEAM NAME]` before presenting, or keep the placeholder hidden until
the facilitator announces the winner live.

Play each video once over the room presentation system. Do not ask participants
to play either brief on their own devices.

## Compatibility

- The `.pptx` copies contain embedded MP4 media and are intended for Microsoft
  PowerPoint.
- The `.odp` copies contain the same embedded MP4 media in LibreOffice's native
  presentation format. Use these in LibreOffice Impress. Do not open the PPTX in
  LibreOffice and expect PowerPoint's media behavior to survive unchanged.
- The accepted source videos are under `media/` so the decks can be rebuilt.

## Rebuild both decks

Requirements:

- Windows with desktop Microsoft PowerPoint;
- LibreOffice at `C:\Program Files\LibreOffice\program\soffice.exe` when ODP
  output is required.

From the repository root:

```powershell
.\scripts\build_event_day_deck.ps1
```

To use replacement videos or a different registration address:

```powershell
.\scripts\build_event_day_deck.ps1 `
  -IntroVideo 'C:\path\to\introbrief.mp4' `
  -OutroVideo 'C:\path\to\outrobrief.mp4' `
  -LandingPage 'https://ctfd.cyberexperts.org/silent-ridge/register'
```

The old `event-day-deck.pdf`, `event-day-deck.pptd`, and `pages/` directory are
retained as design-source history. Do not present the old monolithic deck.
