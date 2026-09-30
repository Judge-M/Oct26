# 5-team AI stress test — findings

Date: 2026-09-30. Host: `DESKTOP-T5PF26O`, Windows, Docker Desktop 29.8.0,
20 cores / 31.7 GiB RAM / 238 GB free. Runtime: `work/runtime-stress`, 5 teams.
Committed alongside the receipts on branch `fix/bounded-http-503-reset`.

**Headline: the infrastructure held. The most serious failure was in my own
test harness, not the product.** That distinction matters more than the score.

## 1. Gameplay result (5 AI teams playing simultaneously)

| Team | Correct | Incorrect | Tickets completed |
|---|---|---|---|
| team-05 | 58 | 2 | 15 |
| team-01 | 8 | — | 2 (T01, T19 partial) |
| team-04 | 4 | — | 2 (T07, T09 partial) |
| team-02 | 0 → **4** | 0 | 0 → 1 (after harness fix) |
| team-03 | pending | — | pending |

80 questions total; 74 answered correctly across the run. team-05 dominated
because the early tickets were uncontended — a first-mover effect, not a skill
difference.

## 2. The critical finding: my harness locked out a team, not a product defect

team-02 reported **100% claim failure** (HTTP 409 on 9 different tickets, with
backoff up to 60s) and scored 0. Its hypothesis — and its report's conclusion —
was that the claim lifecycle is broken and a team can be permanently locked out.

**That conclusion was wrong, and the fault was mine.** I built the participant
client that the agents used, and it scraped the optimistic-concurrency token
incorrectly:

```python
# BUG in my participant client
gens = re.findall(r'value="(\d+)"', html)   # first digit on the page
...
gen = gens[0] if gen else '0'               # fallback: always 0
```

The real page renders a **per-ticket** generation inside that ticket's own claim
form (`ridge/web.py:22`):

```html
<input type="hidden" name="generation" value="{{t.generation}}">
```

So a browser participant always sends the correct token, but my client sent
`generation=0` for any ticket whose generation had advanced. Every such claim
failed with `Ticket changed; reload before claiming` → 409, indistinguishable
from genuine contention.

**Proof the product is correct:** with the client fixed to parse the per-ticket
generation, team-02 claimed T11 and scored **4/4 correct** immediately.

This is the third time in this session a bug in my own tooling masqueraded as a
product defect (after a broken DES implementation and a wrong hex conversion).
All three were caught by verifying the verifier. The lesson is consistent: on
this codebase, treat a surprising failure as a measurement error first.

## 3. Real product/infra findings

### 3.1 CTFd rate-limits login, not answers (reported by 3 agents)

`HTTP 429 TOO MANY REQUESTS` on `POST /login`, triggered by ordinary
back-to-back requests. Two of five teams hit it. Anything that re-authenticates
per action trips it quickly, and `guides/getting-started.md` does not mention
it. A human clicking through would hit the same wall at speed.

Note `expanded/load.py` already knows this — it has `CTFD_LOGIN_INTERVAL_S = 6.1`
with the comment "stock CTFd limit: 10 POST /login requests per 60 seconds/IP"
— so the limit is understood in the repo, but it is not surfaced to participants
and any new client must rediscover it.

### 3.2 Claim contention returns an opaque 409

`Ticket unavailable, another team claimed it, or exercise paused. Reload the
queue.` is returned for four distinct conditions: already holding another
ticket, ticket taken, ticket not yet prepared in IRIS, and stale generation. A
participant cannot tell which, and the queue page does not say which ticket is
actually claimable. With 5 teams competing, agents burned turns guessing.

### 3.3 `claim` never renders for a locked or completed ticket

`ridge/web.py:22` gates the claim form on `t.status=='available' and t.iris_id`.
Correct, but combined with 3.2 a participant gets no actionable next step.
team-05 reported being unable to release a just-completed ticket (403) and then
being unable to claim until it guessed a free ticket.

### 3.4 Answer-format ambiguity cost real points

team-05 lost 2 points to format, not fact: it submitted
`2026-10-15T08:57:00Z` and `C:/Downloads/brief-viewer.exe` where the expected
answers were `08:57:00` and `C:/Downloads`. The generic footer only covers
times ("times use HH:MM:SS UTC"). T03-Q4 asks for a "target directory" while the
evidence field `target_path` holds a full file path. The walkthrough hint
settles it, but only after a reject.

### 3.5 `/originals` is referenced by the guide but not published

team-05 reported that T05 and the Autopsy guidance tell the participant to
compare `/evidence` against `/originals`, but only `evidence-public` is published
to the agent-visible folder. On a real desktop `/originals` **is** mounted (I
verified 21 files there), so this is a limitation of what I exposed to the
agents, not of the event. Noted so the result is not misread.

### 3.6 Encoding artefacts in the rendered pages

Multiple agents reported `\uFFFD` replacement characters where the scenario uses
an em-dash (`T11 � Investigate...`, `Help level 3 � explicit walkthrough`).
Likely a charset declaration issue in the participant templates, or agent-side
decoding. It degrades readability of otherwise correct content.

## 4. The hint ladder has no ladder

Reported independently by team-02 and team-05: levels 1 and 2 are **identical
boilerplate across every question in the exercise**:

- level 1: "Start with `<selection>` and read the fields named in the question."
- level 2: "Compare the selected record with adjacent events; apply clock
  correction only to device_time."

Level 2 is actively misleading on binary analysis and server-log questions,
where no clock correction is involved. Only level 3 is question-specific, and it
states the answer outright. So the "three help levels" are one real hint
sandwiched between two no-ops.

## 5. Infrastructure metrics

Sampled every 5 s for the duration (`metrics.jsonl`): per-container CPU and
memory, host RAM and disk, outbox depth, and HTTP latency to IRIS/CTFd/Guacamole.
See the metrics section of the accompanying report for percentiles and peaks.

**Capacity finding.** The 5-team bring-up was refused twice by the capacity
model, and both refusals were the model being correct:

1. `capacity.host.disk_gib: insufficient for 5 teams: need 275` — the shipped
   example profile reserves 200 GiB for central services, which is unrealistic.
2. `capacity.host.memory_mib: insufficient for 5 teams with 20% headroom: need
   19660` — 5 teams needs ~19.2 GiB.

The memory refusal is the more interesting one. **Earlier in this session the
Docker engine reported a 15.5 GiB cap, which made 5 teams impossible.** After
Docker Desktop's backend crashed and I relaunched it, the engine reported
**31.2 GiB** and 5 teams came up comfortably. The 10-team rehearsal host sizing
depends on that cap, and **nothing in the repository records what the cap
actually was.** This is a reproducibility hazard for the rehearsal.

## 6. What this test does not establish

- **No human session.** Five AI agents made HTTP requests. Nobody used Guacamole,
  ran Autopsy, or opened a team desktop under load. The desktop-usability gate
  remains open.
- **Not a capacity rehearsal.** 5 teams, one host, one run. Says nothing about
  10 teams, and no claim is made.
- **Answers came from the in-game walkthrough hints**, which the scenario
  explicitly permits at any help level. Legitimate play, but it does not
  measure how long a *real* team takes, and it does not validate that a
  question is solvable without the hint. The beginner rehearsal in `NEXT.md`
  remains unrun.
- **No restarts, no failover, no backup/restore** during the run.
- **One run.** No repeat, so no confidence intervals.
