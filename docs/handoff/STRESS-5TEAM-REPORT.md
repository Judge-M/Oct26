# 5-team AI stress test — final report

Date: 2026-09-30. Host: `DESKTOP-T5PF26O`, Windows, Docker Desktop 29.8.0.
Runtime: `work/runtime-stress`, 5 teams, started explicitly.
Branch: `fix/bounded-http-503-reset`.

**Verdict: the serving infrastructure is sound and was never the bottleneck.
Every problem the five teams hit was in the participant write path or in content
design. Two teams were locked out entirely — and in both cases the first
diagnosis ("the product is broken") was wrong, and the real cause was partly my
own test harness.**

## 1. Result

| Team | Correct | Incorrect | Tickets |
|---|---|---|---|
| team-05 | 56 | 2 | 15 |
| team-04 | 12 | 1 | 3 |
| team-01 | 8 | 5 | 2 |
| team-02 | 0 → **4** | 0 | 0 → 1 |
| team-03 | **0** | 0 | 0 |
| **Total** | **80 / 80** | 8 | **20 / 20** |

Verified natively, not from local state:

- **80 answers** recorded; **80 finding comments** and **20 closed tasks** in IRIS
- **80 `Awards` rows** in CTFd, correctly attributed: `{team5: 56, team4: 12, team1: 8, team2: 4}`
- **outbox 100% drained** (20 ticket, 20 ownership, 80 finding, 80 point, 20 close)

**The exercise was completed — all 80 questions, all 20 tickets — by five
competing AI teams with zero infrastructure failures.**

## 2. Two teams scored zero. Both diagnoses were wrong.

This is the most important part of the report.

### team-02: 100% claim failure, concluded "the claim lifecycle is broken"

Its report said a team can be permanently locked out and that it needed an
organizer-side fix. **The product was fine. The bug was mine.** The participant
client I wrote scraped the concurrency token with a generic regex and fell back
to `0`:

```python
gens = re.findall(r'value="(\d+)"', html)   # first digit anywhere on the page
gen = gens[0] if gen else '0'               # always 0
```

The real page renders a **per-ticket** generation inside that ticket's own claim
form (`ridge/web.py:22`). A browser sends the right value; my client sent `0`
for any ticket whose generation had advanced, producing a 409 indistinguishable
from real contention. With the parser corrected, **team-02 scored 4/4
immediately.**

### team-03: concluded "the exercise is unwinnable, both write paths are dead"

It reported zero `<form>`, zero `csrf_token`, zero `generation` and zero `nonce`
on the pages, and concluded the templates had regressed. **The forms are
conditionally rendered** (`ridge/web.py:22` gates the claim form on
`t.status=='available' and t.iris_id`). By the time it looked, all 20 tickets
were complete, so no claim form existed — correct behaviour, misread as breakage.

**The genuine finding underneath:** a participant who holds nothing and has
nothing available gets a page with **zero interactive controls and no
explanation**. That is indistinguishable from a broken deployment, and two teams
independently reached that conclusion. This is a real robustness gap.

## 3. Real product findings, ranked

### 3.1 Answer-format grading is the largest source of lost points

Across teams, **8 incorrect submissions and at least 6 of them were pure format
errors, not wrong facts:**

- team-01: `v3` and `plan-v3` rejected where bare `3` was expected; full ISO
  `2026-10-15T09:06:00Z` rejected where `09:06:00` was wanted
- team-04: `explicit session revocation` rejected where `session revocation` was
  expected
- team-05: full ISO timestamp and full file path where a directory was wanted

team-01 said it plainly: *"The hardest part was answer formatting, not
analysis."* The generic footer only covers times. A question asking for a
"target directory" whose evidence field holds a full path is genuinely ambiguous.
**Recommendation:** normalise answers before hashing (strip `v` prefix, accept
ISO or bare time, compare basenames), and state the expected format per
question rather than in a global footer.

### 3.2 The CTFd login rate limit is undeclared and cost real work

`HTTP 429` on `POST /login` — hit by 4 of 5 teams. team-05 and team-04 each lost
a submission to it. The repo already knows the limit (`load.py` hardcodes
`CTFD_LOGIN_INTERVAL_S = 6.1` for "10 POST /login per 60s/IP") but it is not
surfaced to participants, so every new client rediscovers it. `getting-started.md`
does not mention it.

### 3.3 Claim contention returns one opaque 409 for four conditions

`Ticket unavailable, another team claimed it, or exercise paused.` covers: already
holding a ticket, ticket taken, ticket not yet prepared in IRIS, and stale
generation. team-01 saw it told "another team claimed it" when nothing had been.
With 5 teams competing this cost real turns.

### 3.4 The hint ladder has no ladder

Levels 1 and 2 are byte-identical boilerplate across all 80 questions. Level 2
("apply clock correction only to device_time") is actively misleading on binary
analysis and server-log questions where no clock correction exists. Only level 3
is question-specific — and it states the answer outright, so a team that gives up
reads the answer instead of learning.

### 3.5 A page with no controls is indistinguishable from a broken page

See §2. Recommend an explicit empty state: "You hold no ticket. Available: T11,
T20. The exercise is complete." rather than a bare read-only list.

### 3.6 Cross-ticket hint bleed and a self-correcting hint

team-04 found a T07 hint referring to "the T06 answer", and T07-Q2's hint points
at the wrong value (`09:03`) before correcting itself. Confusing.

### 3.7 Non-ASCII mojibake in rendered pages

All five agents reported `\uFFFD` where an em-dash belongs
(`T11 � Investigate...`, `Help level 3 � explicit walkthrough`). Likely a charset
declaration in the participant templates.

### 3.8 Scoreboard reported empty despite 80 awards

team-03 and team-04 both saw `Scoreboard is empty` while the native `Awards`
table held 80 rows. The `clear_standings` cache invalidation may not be reaching
the scoreboard view, or the standings cache is not refreshed after bulk awards.
**Worth verifying on event day — a leaderboard that reads empty to participants
is a visible failure.**

## 4. Content defects found and fixed during this test

Live play exposed four route defects my static audit missed or mis-called:

| Q | Defect | Status |
|---|---|---|
| T12-Q2, T12-Q3 | I reported these as "unreachable, needs an author". **Wrong** — `server/collection.txt` states `collection unavailable 09:14–09:18 UTC`. My audit searched for `09:14:00`; the file writes `09:14–09:18`. | **fixed** |
| T07-Q1 | Answer is in the named file but the ticket's `selection` (`data.action:session_refresh`) doesn't surface it — the reset is a separate action. A failure mode my audit could not detect by construction. | **fixed** |
| T07-Q2, T07-Q4, T01-Q1 | Cross-source hops never stated. | **fixed earlier** |

**Six of 80 questions now carry route supplements.** All 80 answers unchanged.

## 5. Infrastructure metrics — see `STRESS-5TEAM-METRICS.md`

148 samples over 17.5 min, 19 containers:

- participant endpoint latency: IRIS p50 **16 ms**, CTFd p50 **31 ms**, p95 < 50 ms
- **zero non-2xx across 444 probes**
- outbox max depth **3**, drained 100%
- peak all-container memory **4.77 GiB**, host reserve **67.5%**
- disk growth **0.30 GiB**

**The serving layer was never the problem.**

### Capacity, with a correction

Earlier receipts recorded the host as 31.7 GiB RAM. **That was my measurement
error — the host has 63.7 GiB**, already the README's "comfortable" tier. The
binding constraint is the **Docker memory cap**, not the hardware:

| Teams | Required by model | vs 15.5 GiB cap | vs 31.2 GiB cap |
|---|---|---|---|
| 2 | 12.3 GiB | fits | fits |
| 5 | 19.2 GiB | **refused** | fits |
| 10 | 31.2 GiB | **refused** | exactly at the limit, zero headroom |

**Ten teams is feasible on this hardware only with the cap raised**, and at the
current cap it sits exactly on the model's own requirement. Nothing in the repo
records what the cap should be — a reproducibility hazard for the rehearsal.

## 6. Honest limits

- **No human ever played.** Five AI agents made HTTP requests. Nobody used
  Guacamole, ran Autopsy, or opened a desktop. The N2/F03 desktop-usability gate
  **remains open**, and the ~2 GiB/desktop-with-case peak is still untested.
- **Not a capacity rehearsal.** 5 teams, one host, one run. No 10-team claim.
- **Answers came from walkthrough hints**, which the scenario permits. This
  measures plumbing, not human solvability. The beginner rehearsal is unrun.
- **No restart, failover, backup or restore** during the run.
- **Scoring was first-mover dominated**: team-05 took 15 uncontended tickets
  early. That is a property of this run, not a defect.
- **Two teams' results reflect my harness's bugs**, so their scores understate
  what those teams would have achieved with a correct client.

## 7. Recommended next steps

1. Normalise grading and state expected format per question (§3.1) — biggest
   win, affects every participant.
2. Fix or document the CTFd login rate limit (§3.2).
3. Add an empty state to both queue pages (§3.5).
4. Distinguish the four 409 conditions (§3.3).
5. Verify the scoreboard renders 80 awards (§3.8) before event day.
6. Realise the hint ladder, or collapse it to one honest level (§3.4).
7. **Run the desktop usability pass with a human** — the only open gate that
   matters for event day.
