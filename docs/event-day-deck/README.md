# Event-day presentation

Use `event-day-deck.pptx` for the room presentation. It contains 15 slides:

- slide 1: holding/title slide;
- slide 2: embedded opening brief, set to play automatically;
- slides 3–14: the participant story and setup walkthrough;
- slide 15: embedded closing brief, set to play automatically.

Stop on slide 14 after the opening walkthrough. Advance to slide 15 only when
the exercise is ending. Play each video once over the room presentation system,
not separately on participant devices.

`event-day-deck.pdf` is the no-video fallback. `event-day-deck.pptd` and the
files under `pages/` are the editable source for the 13 visual slides. PPTD does
not support embedded video, so the final PowerPoint is assembled from the PDF
render plus the two accepted MP4 files.

## Rebuild the PowerPoint

Requirements:

- Windows with desktop Microsoft PowerPoint;
- Poppler `pdftoppm` on `PATH`, or the bundled Codex desktop runtime;
- the accepted intro and outro MP4 files.

From the repository root:

```powershell
.\scripts\build_event_day_deck.ps1 `
  -IntroVideo 'C:\path\to\introbrief.mp4' `
  -OutroVideo 'C:\path\to\outrobrief.mp4'
```

The script renders the 13-source-slide PDF, keeps the square videos centered on
the widescreen canvas, embeds both MP4s in the PowerPoint and enables automatic
playback. The committed PowerPoint uses Git LFS because its embedded videos make
it larger than GitHub's normal file limit.
