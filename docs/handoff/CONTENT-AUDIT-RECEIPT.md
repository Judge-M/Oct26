# Content audit receipt — taught evidence paths across all 80 questions

Date: 2026-09-30. Branch: `fix/bounded-http-503-reset` (three commits, unpushed).
Baseline: `main` `4203239` plus this branch's fixes.
Stack: 2-team pilot, `work/runtime-pilot`.

**Status:** content audit complete for all 80 questions. 70 have a sound taught
path, 7 need a second file their steps never name, and 3 could not be confirmed
reachable and need an author. No question is unanswerable — every `hints` list
ends with a walkthrough sentence naming the answer — but 7 of 80 cannot be solved
by following their own instructions.

This is a **content** finding, not a tooling one. Every test passes, the
walkthrough scored 80/80, and the native effects verified correctly. The defect
is between the instructions and the evidence.

## 1. Method

For each of the 80 questions:

1. Recover the expected answer from the question's own hint text, then **verify it
   against the stored SHA-256 `digest`**. A wrong extraction cannot pass, so each
   answer is provably the intended one.
2. Extract the evidence files the question points at, from its `evidence`,
   `steps` and `source_record` fields.
3. Test whether the answer is present in those files. PCAPs are decoded, not byte
   grepped.
4. For anything unreachable, search the whole released evidence tree to
   distinguish "wrong file named" from "answer not published at all".

Inputs are only what a participant can read: question rows from the provisioned
state, and the read-only `/evidence` mount on a team desktop. No private data.

## 2. Result

```
questions audited: 80
  answer IS in the file the question names : 73
  needs a second, un-named file            :  3
  could not confirm reachable             :  3
  (the other 1, T11-Q3, resolved on review)
```

**Corrected 2026-09-30.** An earlier version of this receipt reported 7 broken
routes including all four T02 questions. That was wrong: I had converted
`10.26.10.17` to the wrong hex (`0a1a1411` instead of `0a1a0a11`) and therefore
concluded bytes were absent that were present. A proper Ethernet/IPv4/UDP/DNS
decode of `dns.pcap` shows all four T02 answers are exactly where the ticket says
they are. T02 is fine. The confirmed defects are 3, not 7.

### The 3 confirmed broken routes (fixed)

| Q | Answer | Question names | Answer actually in |
|---|---|---|---|
| T01-Q1 | `WS-17` | `network/sensor.pcap` | `endpoint/events.csv` (via `identity/auth.csv`) |
| T07-Q2 | `09:26:00` | `wazuh/telemetry.jsonl` | `identity/late-auth.csv` |
| T07-Q4 | `session revocation` | `wazuh/telemetry.jsonl` | `identity/policy.txt` |

T01-Q1 in detail: the ticket teaches `sensor.pcap` with `udp.port == 514`, but
there are **zero `WS-*` strings in the entire capture** (verified across all 24
packets). It carries the requester's address `10.26.10.17`, and the chain is
three hops:

```
sensor.pcap        10.26.10.17 requests /files/plan-v3  (req-71)
identity/auth.csv  10.26.10.17 = user m.ellis, session S-41
endpoint/events.csv m.ellis = WS-17    (verified unique: m.ellis maps to WS-17 only)
```

`endpoint/events.csv` holds no `10.26.10.17` value, so passing through the user
identity is mandatory — and nothing in the hint, steps or
`guides/getting-started.md` mentions it.

T07-Q2 in detail: `telemetry.jsonl` contains exactly **one** `session_refresh`
record and it is timestamped `09:03:00Z` — which is T06's answer, the *earlier*
refresh. The late refresh the question wants is in `identity/late-auth.csv`. A
participant searching the Wazuh index finds a real but wrong record.

T07-Q4 in detail: the string "revocation" appears **nowhere** in
`telemetry.jsonl`. The answer is a policy statement in `identity/policy.txt`,
not a telemetry field.

### The 3 that could not be confirmed — CORRECTED, all three are reachable

**Corrected 2026-09-30 after a 5-team stress test.** I originally reported
T12-Q2/Q3 as "genuinely unreachable, needs an author". **That was wrong.**
`/evidence/server/collection.txt` states:

```
DOCS-1 audit: 08:00–09:30 UTC; collection unavailable 09:14–09:18 UTC. Other servers were not collected.
```

The gap boundaries are right there. My audit searched for the literal string
`09:14:00` and the file says `09:14–09:18` — an en-dash and no seconds — so my
exact-substring test reported a false absence. A fourth measurement error of
mine, and the most consequential: I escalated two questions to a maintainer as
needing an author when they needed only a step pointing at a file already
published.

- **T12-Q2** `09:14:00` and **T12-Q3** `09:18:00` — answerable from
  `server/collection.txt`. Both now carry a step naming that file. Fixed.
- **T11-Q3** `08:50:00` — reachable at minute precision from
  `"offline since 08:50"`; the `:00` is an answer-format artifact. Judged fine,
  left unchanged.

### A defect the audit structurally could not find

The audit asked "is the answer present in the file this question names?". That
misses a second failure mode: the answer *is* in the named file, but the stated
`selection` does not surface it. team-04 hit this live on T07-Q1: the ticket's
selection is `data.action:session_refresh`, but the question asks about the
**password reset**, which is a separate `action` value. Following the stated
procedure returns nothing. Now fixed with a step telling the participant to
search `data.action:password_reset`.

## 3. Three corrections I made to my own work

All are recorded because each initially looked like a product defect and all were
my error.

**Over-reported by four questions (twice).** My first audit byte-grepped the
PCAPs and declared T02-Q1..Q4 unreachable (11 broken). Wrong twice over: DNS
names are length-prefixed, so a contiguous substring search misses them, *and* I
converted `10.26.10.17` to the wrong hex, inventing an absence that did not
exist. A proper Ethernet/IPv4/UDP/DNS decode shows all four T02 answers in
`dns.pcap` exactly where the ticket claims. Real count: 3.

**A false absence in my own verification.** The check I wrote to prove T02 was
healthy used `b'0a1a0a11'` — a Python bytes *literal*, which parses as raw byte
values, not as hex digits. It reported the data missing when it was present.
Fixed with `bytes.fromhex`.

**Nearly filed a false critical on a broken test.** Earlier, a hand-rolled DES
implementation reported VNC authentication rejected for both teams. Running it
against six NIST known-answer vectors failed all six, so the bug was mine. The
same pattern — believe the tool, check the tool — applied twice more here.

The through-line: every one of these was a measurement error on my side, caught
only by verifying the verifier. None was caught by the system under test.

## 4. What this does and does not establish

- **Establishes:** the specific per-question routes above, each verified against
  the released evidence on a live desktop.
- **Does not establish:** that these are the *only* content problems. The audit
  tests answer reachability, not question fairness, wording, difficulty, or
  whether the intended technique actually leads to the answer. A beginner
  rehearsal would find things this cannot.
- **Does not establish:** anything about the 10-team capacity rehearsal, or about
  a human session. Still no person has investigated a ticket.
- **A judgement call, flagged not hidden:** I classified T11-Q3 as probably fine
  and T12-Q2/Q3 as broken. A maintainer who intended the `08:50` style
  minute-precision answers to be exact will disagree about T11-Q3. The reasoning
  is shown so it can be checked.

## 5. Follow-ups

**Done:** the 3 confirmed routes are fixed in `expanded/author.py` via a new
`EXTRA_STEPS` map that appends the cross-source hop to the affected question's
`steps`. The base per-tool templates are untouched, `EXTRA_STEPS` defaults to
empty for every other question, and `steps` is now copied per question so a
supplement cannot leak into sibling questions in the same ticket. Regeneration is
idempotent (identical SHA-256 across runs), all 80 answers are unchanged, and
`tests/test_autopsy_paths.py` (which calls `author.build`) passes.

**Still open:**

1. **Resolve T12-Q2/Q3** — either author the DOCS-1 gap boundaries or repoint the
   question. This needs an author's judgement, not a mechanical fix.
2. **Add an authoring-time reachability check** to the test suite: assert each
   question's answer is findable using only the files its `evidence`/`steps` name.
   Three of these defects were caught by hand in one pass; the check is
   mechanical and would stop the class recurring. Note the parser subtlety —
   PCAP answers are inside packet payloads and DNS names are length-prefixed, so
   a naive substring scan both misses real hits and invents false ones.
3. **Strip the answer from `hints`.** The walkthrough sentence currently reads
   "The supplied record/comparison yields X. Enter X." That is why no question is
   strictly unanswerable — and also why a team that gives up can just read the
   answer instead of learning anything.
4. **Re-audit T12 and any question whose answer is a derived value** rather than
   a literal string. T11-Q3 (`08:50:00` from "offline since 08:50") is a judgement
   call; a maintainer may disagree.
