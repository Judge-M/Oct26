# F04 Receipt (independent slice) — Duration model + scripted walkthrough evidence

Date: 2026-09-20. Branch: `feat/f04-duration-model`. Base: `main` (N4 merge).
Test count: **250 passing** (240 on this base + 10 schedule/walkthrough).

## Blocked prerequisite (named per card)

F04 lists prerequisites **A02, C04, F03**. **F03 (capacity rehearsal at event
scale) is blocked** — it requires the event hardware, and this machine is not the
event host. Per the card's finish-and-stop rule, this turn completes only the
independent source/test work: scripted agent walkthroughs to catch broken tasks,
and the scheduling model. The **beginner rehearsal remains required** — bot
timings are not human duration evidence and this receipt does not claim
otherwise.

## What was built

- **`expanded/walkthrough.py`** — scripted full-content walkthrough. Drives all
  20 tickets / 80 questions in dependency order through the real mutation paths
  (`State.claim`/`State.answer`) against a live provisioned stack, verifies each
  ticket reaches `complete`, waits for the integration outbox to drain, and
  records per-question bot timings. Output explicitly labeled as bot evidence.
- **`expanded/schedule.py`** — event-day scheduling model wrapping
  `workload.py`'s makespan simulation. Facilitated segments (orientation 25 min,
  inject briefing 10 min), break (15 min) and AAR (30 min) are modeled and
  accounted **separately** from investigation activity (per the F04 card and
  `facilitator/assessment-aar.md`). `sensitivity()` rescales the authored
  65-minute allowance to show pace tolerance. Renders `docs/schedule-model.md`.
- **`tests/test_schedule.py`** — 10 tests: topological ordering + cycle
  detection, scaling floor/validation, separate segment accounting, window-fit
  flags, monotonicity, determinism.

## Scripted walkthrough results (live restored stack, event `silent-ridge-n1`)

Run against the N5-drill restored runtime (`work/n5-restore`), exercise RUNNING:

- **All 80 questions accepted** on first attempt with authored answers; all 20
  tickets reached `complete`; outbox drained to zero.
- Native effects verified: **80 CTFd credits** (one per question) and **80 IRIS
  finding receipts** under the current run id (plus one older-run receipt row
  from the N3 era). No broken task found.
- Bot wall time for the full content set: ~35 s of pure API time — this says
  the content is *mechanically intact*, nothing about human duration.

### Defect found and worked around (worth a follow-up)

A freshly unlocked ticket is `available` in state **before** its IRIS task
exists (`iris_id` is NULL until the worker delivers the `ticket:` outbox row).
A claim in that window fails with "Ticket is not available in IRIS". Humans hit
this only if they claim within seconds of an unlock (the UI already says to
reload), but it is a real transient. The walkthrough drains-and-retries; a
proper fix (defer `available` until delivery confirms) is a candidate small
task.

## Duration-gap analysis (the actual question: does content fill 4–5 h?)

Model output (`docs/schedule-model.md`, ten teams, authored 65-min allowance):

| Pace multiplier | Investigation makespan | Event total (incl. 80 min facilitated/breaks/AAR) | Fits 240–300 |
|---|---|---|---|
| 1.00x | 195 min | **275 min** | yes |
| 1.25x | 243 min | 323 min | NO |
| 1.50x | 294 min | 374 min | NO |

Findings:

1. **At authored pace the event day fits** the agreed 240–300 min window only
   when the facilitated segments are counted — investigation alone is 195 min.
   This matches the existing workload.md warning that authored content covers
   roughly half the target as *unaided investigation*.
2. **Slack is ~25 min.** Any pace slower than ~1.1x the authored allowance
   overruns the window. The 65-min ticket allowance is unmeasured; beginners
   plausibly run slower, but free walkthroughs on all 80 questions cut the
   other way. Only the rehearsal resolves this.
3. **Per-team imbalance is the bigger structural risk**: at authored pace the
   simulation assigns team-10 a single 65-minute ticket while team-01 carries
   195 min (dependency chain T06→T07→T20). In a 4–5 h event, low-load teams
   idle unless the facilitator routes them to released tickets or coached
   practice. Options, cheapest first:
   - **Facilitated structure (recommended, no new content):** orientation,
     inject briefings and AAR per the model, plus explicit reassignment norms
     once a team's queue is empty. Fits the window today at authored pace.
   - **Rebalance dependencies** so the long chain (T06/T07/T20) is not the
     makespan driver and per-team loads even out — a small content task.
   - **Add authored content** (~doubling, per workload.md) — only if the
     rehearsal shows teams finishing early; per the card this must be split
     into separate small content tasks with full provenance (answer, source,
     limitation, guide, tests, package inclusion).
4. **Do not** duplicate scoreable tickets to pad duration (card constraint,
   respected throughout).

## Acceptance-check status against the card

- "Run scripted agent walkthroughs first to catch broken tasks" — **done**
  (80/80 accepted live; one transient unlock-race defect found, named above).
- "A scheduling model plus rehearsal supports the agreed ten-team duration with
  AAR/breaks accounted separately" — **model done**; rehearsal outstanding and
  still required (worksheet already exists at `docs/rehearsal-worksheet.md`).
- "Record active/idle time and learning observations rather than claiming skill
  gains from a bot" — respected: no skill/duration claims from bot timings.
- Beginner rehearsal + any content additions: **not done here** (rehearsal
  needs participants; content additions await the rehearsal verdict or an
  explicit revised duration from the organizer).
