# Full-system verification receipt — all 80 questions solved, native effects confirmed

Date: 2026-09-30. Branch: `fix/bounded-http-503-reset` (two commits, unpushed).
Baseline: `main` `4203239` plus the defects fixed in
[CLEAN-BASELINE-RECEIPT.md](CLEAN-BASELINE-RECEIPT.md) and
[PILOT-2TEAM-RECEIPT.md](PILOT-2TEAM-RECEIPT.md).
Runtime: `work/runtime-pilot`. Profile: `work/profiles/pilot-2team.json`.
Stack state: **RUNNING** (started explicitly for this test).

**This is a functional verification of the answer→IRIS/CTFd path. It is still
not event certification.** See §6 for what remains unproven.

## 1. Result

Every one of the 80 questions was answered, every ticket closed, and the native
effects were read back from IRIS and CTFd themselves rather than from local state.

| Measure | Value |
|---|---|
| Questions answered | **80 / 80** |
| Wrong answers | **0** |
| Tickets complete | **20 / 20** |
| Findings in IRIS (native comment rows) | **80** |
| Tickets closed in IRIS (`task_close_date` set) | **20** |
| Points in CTFd (native `Awards` rows) | **80** |
| Outbox pending | **0** |
| Delivery receipts (IRIS) | 142 — 20 ticket, 22 ownership, 80 finding, 20 close |

## 2. Native verification, not local state

`AGENTS.md` is explicit that an HTTP success or a local outbox row does not prove
a remote effect, so each native store was read through its own bridge export and
the IRIS PostgreSQL database was queried directly.

**IRIS** (bridge `export` on `/silent-ridge/internal`, authenticated with the
real bridge secret):

```
tasks                20
tasks closed         20
finding comments     80   (expect 80)  MATCH
ownership comments   22
task-comment links  102
delivery receipts   142   {ticket:20, ownership:22, finding:80, close:20}
```

**IRIS database** (`psql` against `iris_db`, independent of the bridge):

```sql
SELECT kind, case_id, COUNT(*) ...
  tasks    | 2 | 20
  comments | 2 | 102

SELECT task_title, status_name, task_close_date IS NOT NULL
  FROM case_tasks JOIN task_status ... WHERE task_case_id = 2
  T01 · Trace document traffic                     | Done | t
  T02 · Resolve names and compare conversations    | Done | t
  ...
```

A finding row read directly from the database:

> WS-17 is the workstation associated with the plan-v3 request.
> Evidence: network/sensor.pcap (udp.port == 514)
> Limitation: Replayed or reconstructed evidence; transmission metadata does not
> establish human receipt, reading, or intent.

**CTFd** (bridge `export`, reading the native `Awards` table):

```
awards                     80
credit receipts            80
awards per team_id         {1: 80}
total value per team       {1: 80}
distinct award names       80   (one per question)
```

All 80 awards are attributed to `team_id 1` (team-01), the only team that
answered. This is correct: no cross-team credit leak.

**A false alarm worth recording.** The public `/api/v1/scoreboard` reported
`account=1 score=80` for a team-02 login as well, which looked like team-02
holding 80 points it never earned. The `Awards` table shows this is a display
artifact of the shared scoreboard context, not a credit leak — team-02 has zero
awards. Recorded because the same appearance would be a genuine defect if the
awards had confirmed it, and the only way to tell the difference was to read the
native table.

## 3. Participant-facing checks

Authenticated as the real team accounts over the local CA, following the same
flows the load harness uses:

| Check | Result |
|---|---|
| IRIS participant login reaches dashboard | PASS |
| IRIS case task list reachable (cid=2) | PASS |
| CTFd participant reaches question queue | PASS |
| CTFd queue reflects solved questions (87 markers) | PASS |
| CTFd shared history shows team findings | PASS |
| Guacamole page loads | PASS |
| Wazuh dashboard responds (HTTP 200) | PASS |

7 of 9 automated checks passed on the first run. The two that did not
("task list shows T01", "finding note visible") were **faults in the check, not
the system**: the assertion searched the rendered HTML for strings that the page
does not present that way, while the underlying data was confirmed correct by
direct database query. The checks were corrected rather than the product.

## 4. Load / concurrency check

`expanded.load` with 2 teams x 3 sessions for 120 s:

```
ctfd:login        6 requests,  0 failures, p50 0.297s  p95 0.360s
ctfd:questions  150 requests,  0 failures, p50 0.094s  p95 0.157s
iris:dashboard   51 requests,  0 failures, p50 0.031s
iris:login       2 requests,  0 failures, p50 0.219s
outbox depth min/max: [0, 0]
peak working set: 2.87 GiB   host reserve: 40.9%
```

**Zero failures across all 9 endpoints.** Labelled `NON-CERTIFYING` by the tool
itself, correctly: F03 requires >= 1800 s, a 10-team host with >= 32 GB, and a
desktop usability pass. None of those are claimed here.

## 5. How the walkthrough was driven, and two harness bugs

The intended tool, `expanded.walkthrough`, requires `expanded/tickets.json`,
which is **gitignored and absent** — so the documented full-content walkthrough
cannot run on a clean clone. This is a real gap in the source path, analogous to
the missing `wazuh_config` tree.

Answers were therefore recovered from each question's own hint text and
**verified against the stored SHA-256 digest** before submission, so a bad
extraction would surface as a wrong answer rather than a silent pass. 80/80
digests matched.

Three harness bugs were found and fixed in my own tooling — recorded because
each initially looked like a product defect:

1. **`claim` needs the current generation.** `State.claim` is optimistic
   concurrency: it requires the caller's generation to equal the stored one and
   increments it. Passing `0` stranded T01 permanently at generation 1, and T19
   depends on T01. Reading the live generation immediately before claiming
   resolved it. This is correct API behaviour; a fixed `0` is a caller bug.
2. **A team may hold only one ticket.** Each ticket must be explicitly
   relinquished, because answering the last question only auto-completes a
   ticket. An early run left team-01 holding T01, which made every later claim
   fail with "Relinquish your current ticket first".
3. **Answers can contain spaces.** Two answers are Windows paths
   (`C:/Program Files/Approved/briefsync.exe`, `C:/Temp/move-cache.txt`); a
   regex bounded on `.` truncated them, recovering only 78/80.

## 6. Honest limits — what is still NOT proven

- **Not event certification.** This proves the answer→finding→point path and the
  participant web flows. It does not certify the event.
- **No human ever connected.** Every session was scripted HTTP. Nobody opened
  Guacamole, used a team desktop, ran Autopsy/Wireshark/Cutter/Wazuh, or searched
  the prepared case. The N2/F03 desktop-usability gate remains **open** — that is
  the largest outstanding gap.
- **Boots are not re-verified after a restart.** No worker restart, no
  lost-response redelivery, no takeover-by-another-team test, and no
  `up`-after-`start` persistence check were performed. `NEXT.md` N3 requires all
  of these; they are not done.
- **No backup, restore, or `down --volumes`.** `recovery_ready` is still false.
- **2 teams, 1 host, Windows only.** Nothing here says anything about 10-team
  capacity; the 15.5 GiB Docker memory cap still blocks that.
- **Answers came from hint text, not the authored answer key.** Every one was
  digest-verified, so the submissions are provably the intended answers, but the
  `tickets.json` gap means the canonical path is still unexercised.
- **The two corrected browser checks were not re-run as a suite** after being
  fixed; the underlying facts were established by direct database query instead.
