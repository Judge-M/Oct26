# The Operation Silent Ridge narrative - current state

An orientation to the story, the cast, the evidence and the machinery, for
whoever has to review, change or run this exercise. It describes what exists
**today**, and it is deliberately explicit about the two things that are still
undecided.

Answers are not reproduced here. They live in `expanded/author.py`
(`SPECS`, `FINDINGS`, `LIMITS`) and are published by design; duplicating them
into a second document is the exact drift problem this narrative layer was built
to stop. See [Where the answers are](#11-where-the-answers-are).

---

## 1. The story in one paragraph

A fictional internal document service holds the movement briefs for patrol
**LANTERN**, a fictional field unit. A brief contains a sector, a movement
window and a check-in word: the kind of document an organisation genuinely
protects. At 09:30 UTC the outgoing shift hands the incoming team an unfinished
problem. One document was fetched and re-used outside its normal pattern on the
same morning, while the same session was refreshed from an address appearing in
no approved remote-access list. Two colleagues acted on the same weak signal and
neither escalated. The response moved in three bad steps: a credential was reset
(correct instinct, does not end a session), a network review started (correct
second step), and nobody asked what that session could still reach.

**The supported exposure is one movement brief, transmitted once, to a
documentation-range address.** A second, larger document was requested from the
same session and refused. A third workstation showed a similar tool name and was
never collected from. The difference between those three unknowns *is* the
exercise.

**The outcome is a boundary, not a story.** "A correct boundary is a result, not
a failure to find one."

## 2. Cast and canon

Every name below is fictional. Nothing represents a real unit, person, route,
coordinate or adversary.

| Name | What it is |
|---|---|
| LANTERN | The fictional patrol whose movement briefs are the target document |
| `plan-v3` / `plan-v4` | Two versions of the movement brief; v4 supersedes v3 at 09:10 |
| `WS-17` | Planning clerk's workstation, the workstation in question |
| `WS-22` | Duty planner's workstation, the benign comparator |
| `WS-31` | The unresolved lead; collection stopped mid-morning, never closed |
| `DOCS-1` | The document service |
| `IDP-1` | The identity provider |
| `198.51.100.77` | RFC 5737 TEST-NET-2 **documentation space**. Never connect. |
| `relay.archive.example` | The fictional name that resolved to the above |
| `BriefSync` | The scheduled-task name that appears on two workstations |
| `brief-viewer.exe` | A harmless **training surrogate**, not malware. Never run it. |
| `CEDAR` | A check-in word, carried unchanged between v3 and v4 |

The canon itself is pinned in code, not remembered: `scripts/generate.py:74-90`
(the collection handout glossary) and `facilitator/ground-truth.md`. The
consistency check enforces that participant-facing content draws its names from
that set and spells them one way.

### There is deliberately no adversary

Issues #59 and #66 both asked for a "Wraith" / shadow-network framing.
**No such name exists in this repository, and none was introduced.** T20-Q4's
scored answer is `no` for *"Does the evidence establish adversary intent?"*
Naming a group would contradict a scored answer and push participants toward
pattern-matching instead of reading records. Atmosphere is carried descriptively
("the relay answered", "the endpoints named inside them are the incident
endpoints"). The breadcrumb BC-04 is two handles that resolve to no account, host
or directory entry anywhere, which is the point, because it is exactly why
attribution cannot be made.

## 3. Two narrative contracts, and the open decision

**This is the single most important thing in this document.**

`upstream/main` contains **PR #129 "feat: add shared participant narrative"**
(commit `076e65c`), implementing issues 55/56/60. PR #151 implements the same
three issues differently. They edit the same four files, so both cannot be
correct. PR #151 keeps both working and asks the organizer to decide.

| | #129 (on main) | PR #151 (this work) |
|---|---|---|
| Fixture | `ridge/scenario_narrative_v1.json`, 57 lines | `assets/scenario-narrative-v1.json`, ~250 lines |
| Module | `ridge/narrative.py`, 52 lines | `ridge/scenario_contract.py` + `ridge/web_narrative.py` |
| Fields | title, fiction_notice, premise, discovery, stakes, participant_role, operating_rule, roles, tools, phases, completion | all of those, plus exposure, escalation, outcome, classification_line, boundaries, aar, per-ticket stakes/urgency/transition, hint and accepted-answer text |
| Answer-leak guard | none | `check_no_answers` over 57 distinctive scored answers |
| Exemption guard | none | `check_public_terms` |
| Cross-surface validation | none | `ridge/narrative_consistency.py`, 10 guards, in `preflight` |
| Deck / map / breadcrumbs | none | 22-slide deck + facilitator appendix, T01 map, 7 breadcrumbs |

**What the page actually shows today:** #129's markup is the primary narrative
(fiction notice, premise, discovery, stakes, role, tools, per-ticket phase,
briefing, stakes and handoff, "Why this question matters", shared progress).
PR #151 adds only what #129 lacks: the four phases with purpose, urgency, action
and transition, hint policy, accepted-answer guidance, ticket completion, exercise
completion, participant boundaries, and the T01 map link. Both render contexts
are live on both lanes; no scenario sentence is displayed twice.

**The cost of leaving it undecided:** the repository ships two fixtures that must
be kept narratively consistent **by hand, and nothing enforces it**. Only PR
#151's contract is covered by the leak guard and the consistency survey. If
#129 wins, `ridge/web_narrative.py` and the PR #151 contract tree become dead
weight that still ships in all three images.

## 4. The four investigation phases

The contract's phases are a **narrative** layer. The unlock graph in
`expanded/author.py` is separate and unchanged; phases cut across it.

| Phase | Title | Tickets |
|---|---|---|
| `phase-1` | What actually left the network | T01, T02, T03 |
| `phase-2` | The workstation that sent it | T04, T05, T13, T14, T15, T16, T17, T18 |
| `phase-3` | The account and its session | T06, T07, T10, T11, T12 |
| `phase-4` | The document, and the limit of the claim | T08, T09, T19, T20 |

Each phase carries a purpose, an urgency cue, an expected participant action and
a transition. The validator refuses a phase missing any of them, and refuses a
ticket that belongs to zero or two phases.

## 5. The twenty tickets

20 tickets, 80 scored questions. Roots (no prerequisites) publish at run start,
which matters for placement: see section 7.

| Ticket | Title | Tool | Evidence | Requires |
|---|---|---|---|---|
| T01 | Trace document traffic | Wireshark | `network/sensor.pcap` | - |
| T02 | Resolve names and compare conversations | Wireshark | `network/dns.pcap` | - |
| T03 | Reconstruct the viewer download | Autopsy | `browser/downloads.csv` | - |
| T04 | Investigate persistence | Autopsy | `endpoint/events.csv` | - |
| T05 | Recover and compare cached content | Autopsy | `disk/WS17-fat16.img` | - |
| T06 | Separate password and session authentication | Wazuh | `wazuh/telemetry.jsonl` | - |
| T07 | Test the effect of the password reset | Wazuh | `wazuh/telemetry.jsonl` | T06 |
| T08 | Audit document and roster access | Autopsy | `server/access.csv` | - |
| T09 | Compare superseding movement information | Linux file manager | `server/version-comparison.csv` | T08 |
| T10 | Test a benign comparator | Wazuh | `wazuh/telemetry.jsonl` | - |
| T11 | Investigate the unresolved host lead | Wazuh | `wazuh/telemetry.jsonl` | T10 |
| T12 | Map collection coverage | Wazuh | `wazuh/telemetry.jsonl` | - |
| T13 | Inspect acquired process-log records | Autopsy | `prepared/windows-process.json` | - |
| T14 | Inspect acquired task-log records | Autopsy | `prepared/windows-task.json` | - |
| T15 | Inspect the prepared memory process tree | Autopsy | `prepared/memory-processes.json` | - |
| T16 | Correlate the acquired connection snapshot | Autopsy | `prepared/windows-connections.json` | - |
| T17 | Inspect the harmless training binary configuration | Cutter | `binary/brief-viewer-training` | - |
| T18 | Follow a small static code example | Cutter | `binary/brief-viewer-training` | - |
| T19 | Verify the transmitted payload | Linux file manager | `network/dlp-metadata.json` | T01, T05 |
| T20 | Test the limits of the overall exposure conclusion | Wazuh | `wazuh/telemetry.jsonl` | T07, T09, T11, T19 |

### What the ticket shape teaches

- **T06 / T07** - a successful sign-in and a refreshed session are different
  events with different weaknesses. T07 establishes that a password reset does
  *not* end the session. Three of T20's four answers are `no`, and that is the
  intended result.
- **T10** - the benign comparator. Clearing WS-22 is worth more than another
  suspicious finding, and it is the cheapest way for a team to lose the room.
- **T11 / T12** - the lead that cannot be closed, and the coverage record that
  explains why. Absence of telemetry is not absence of activity.
- **T16** - an acquired live connection snapshot, explicitly *not* a validated
  memory-derived finding. Overstating it is the failure the exercise is built to
  catch.
- **T17 / T18** - a harmless surrogate and a small static example, present to
  teach that configuration is not execution.

## 6. Surfaces

Participants reach evidence as a read-only bind mount at `/evidence` on a shared
container desktop, opened through Thunar. Firefox 140 ESR is present, so
`file:///` HTML renders offline with zero new infrastructure.

| Surface | Where participants see it | Narrative source |
|---|---|---|
| CTFd question page | `http://<host>:8083/silent-ridge` | both contracts |
| IRIS incident queue | `http://<host>:8081/silent-ridge` | both contracts |
| Wazuh dashboard | `https://<host>:8443` | - (tool, not narrative) |
| Guacamole desktop | `http://<host>:8082` | - |
| Evidence tree | `/evidence` on the team desktop | fixture text files |
| Event-day deck | 22 slides, projected PDF | contract, byte-verified |
| Facilitator appendix | 2 slides, never projected | contract |
| T01 network map | `/silent-ridge/network-map`, CTFd lane only | `assets/t01-network-map-v1.json` |
| Breadcrumbs | `/evidence/notes/`, released on unlock | `assets/breadcrumbs-v1.json` |

**There are no CTFd `Challenges` in this exercise.** Stock challenges are
deliberately locked down: `/api/v1/*` returns 403 except the scoreboard GET, and
`/challenges` redirects. Scoring is `Awards` rows, one point per question, with a
`RidgeCredit` idempotency table so a replayed answer cannot double-credit.

## 7. Why things are placed the way they are

**The T01 map is a post-completion view, not released evidence.** Every ticket
with no prerequisites is enqueued for delivery at `State.initialize`
(`ridge/state.py:122-123`, `ridge/transport.py:30-39`), so
`RELEASE_FILES['T01']` would have published at run start and handed the room all
four T01 answers before anyone asked. The map is therefore served behind a
controller gate on the same condition that closes T01. Reasoning is recorded in
`ridge/scenario.py`.

**Breadcrumbs are gated on tickets that unlock late.** BC-05 on T11, BC-06 on
T09, BC-07 on T20. Only tickets with prerequisites can carry a release safely.

**The deck's closing statement is not projected.** `exercise_complete.brief`,
`.residual` and `.scoring_note` state the supported exposure and the residual
unknowns, and that is the scored conclusion. Projecting them from a briefing
slide would pre-empt it, and `FORBIDDEN_REF_PREFIXES` blocks them with a test.

**The facilitator appendix is a separate project file** with its own banner,
excluded from the participant projection set, so a facilitator pause or inject
instruction can never be projected by accident.

**Nothing names an adversary.** See section 2.

## 8. Optional breadcrumbs

7 breadcrumbs, 2 per phase, 5 of them cross-task. Listed in
`facilitator/breadcrumbs.md`.

| ID | Phase | Gate | Points at |
|---|---|---|---|
| BC-01 | phase-1 | - | the sensor capture and the DNS capture, then T02 |
| BC-02 | phase-1 | - | the service catalogue, then T19 |
| BC-03 | phase-2 | - | the recovered cache and the prepared process view, then T15 |
| BC-04 | phase-2 | - | the service access log, then T08 |
| BC-05 | phase-3 | T11 | the coverage record, then T12 |
| BC-06 | phase-4 | T09 | the version comparison, then T09 |
| BC-07 | phase-4 | T20 | the coverage record, then T12 |

**No breadcrumb is bonus-scored.** Optional means a team may ignore every one and
still close all 80 questions; no fixture is named by a question, a hint or a
required evidence path. Bonus scoring is deliberately declined because it cannot
be reconciled reliably with CTFd and IRIS.

## 9. The T01 exfiltration map

`assets/t01-network-map-v1.json` is rendered by `ridge/network_map.py` into one
self-contained offline HTML file. 19 nodes (4 host, 1 service, 1 external,
3 object, 10 evidence-source) and 13 directed edges: **11 observed, 2 inferred**.

- **Keys on `request` / `path` / `time`, never on `id`.**
  `expanded/prepare.py:128-132` rewrites the `id` column of every published CSV
  to a 12-char sha256 prefix, so the authoring labels are not present in
  participant evidence.
- Every edge cites the evidence file supporting it; selecting one reveals the
  record and its path.
- Observed and inferred are visually distinct, and the page states plainly that
  an IP address, a byte count and a successful HTTP response do **not** establish
  human receipt, reading, intent or attribution.
- The external address is marked documentation-space, and the file contains no
  `src=`, `href=`, `url(`, `fetch(` or scheme that could cause a browser to
  contact it. `offline_report` refuses to emit one that could.

## 10. How drift is prevented

```
python -m ridge.narrative_consistency
python -m ridge.cli preflight            # runs it as part of a real deployment
```

Ten guards in `ridge/narrative_consistency.py`: `check_canon`,
`check_surfaces`, `check_entities`, `check_sections`, `check_lineage`,
`check_provenance`, `check_restatement`, `check_tools`, `check_leakage`,
`check_determinism`.

They check that every required section exists; that every surface traces back to
one contract revision; that no surface carries a scenario sentence the contract
does not have; that entities come from canon and are spelled one way; that every
tool named in the issue is explained somewhere; that no scored answer, credential
or facilitator path reaches a participant surface; and that the content is
reproducible from committed sources alone.

Each has a **negative test that proves it fires.** A validator with no failing
test is not a validator. Planting the documentation address into a ticket brief
makes the check exit 1 and name the file and line.

**Known limit:** restatement detection is a similarity test. A paraphrase sharing
no six-content-word run is not caught by that guard; the exact provenance checks
are what cover an inventing surface.

**A second validator covers the learning objectives.**
`python -m ridge.learning_objectives` checks
`docs/learning-objectives.md` against the tree: that every ticket is claimed by an
objective, that T12 is documented against the *timeless* Wazuh view, that only T04
takes the 120-second device correction, that quoted ticket titles are current, and
that the two acquisition dates are stated and distinct. The document is rendered
from `assets/learning-objectives-v1.json`, so it cannot drift the way the three
participant surfaces previously did. Its NICE Framework mapping is **gated
closed** — the identifiers could not be verified against NICE 4.0, so the
document says so rather than asserting them, and the gate is a status a
facilitator reads in the preflight receipt.

## 11. Where the answers are

`expanded/author.py` - `SPECS` (question and answer pairs and the unlock graph),
`FINDINGS` (the finding posted to IRIS per question), `LIMITS` (per-tool
limitation). Rendered by `ridge/state.py` into the `questions` table, bridged to
CTFd and IRIS, and published by design.

Derived acceptance artefacts: `docs/acceptance/question-matrix.md`
(`python -m ridge.question_matrix`) and `docs/workload.md`
(`python -m expanded.workload`).

Facilitator-only: `facilitator/ground-truth.md` (canonical timeline),
`facilitator/solutions.md`, `facilitator/breadcrumbs.md`,
`facilitator/network-map-capture.md`. None is reachable from participant code.

**Standing caveat:** the level-3 hint is a full walkthrough that states the answer
(`expanded/author.py:158`), and hints are deliberately free and ungated. This is
existing approved behaviour, not a leak introduced by the narrative layer. The
narrative guards are enforced against narrative text specifically.

## 12. Known limits and open work

- **The two contracts (section 3) are undecided.** Everything else here assumes
  PR #151 merges, or that #129 is extended to absorb the guards and the
  additional surfaces.
- **The deck PDF is stale.** `kimi-slides` is not on this host and 404s from npm.
  The `.page` sources are authoritative; the committed PDF still shows the old
  13-slide deck and **must be rebuilt before the deck is projected**.
  `python -m ridge.deck_narrative --pdf` reports staleness rather than pretending.
- **Nothing has been verified against the live stack.** No Docker, CTFd, IRIS,
  Wazuh or desktop container was run. Guards are proven to *fire*; the surfaces
  are not proven *readable* to a person.
- **The prebuilt Autopsy case does not index the breadcrumbs.** They are `.txt`
  files under `/evidence/notes/`, reachable by the file manager, not by the
  case's text index. `assets/autopsy-case-v2.json` is a record of a real closed
  case and was not edited, because adding paths to it would falsely claim they
  were ingested.
- **Breadcrumb discoverability is evidence-tree-only.** They are deliberately not
  listed in CTFd or IRIS, because listing them would make an optional aside look
  required.
- **The participant scoreboard 500 is unresolved.** Not reproducible from
  committed source; the only deterministic 500 found is a non-integer `freeze`
  config, which nothing in this repo sets. Not faked. See
  `docs/narrative-operations.md`.
- **Two pre-existing flaky tests** - `tests/test_load.py` and
  `tests/test_bounded_http.py` - fail roughly 2-3 runs in 6 on clean
  `upstream/main`. Socket races, not introduced here, not fixed.
- **Guacamole is explained on one participant line** (`pages/15_step3.page`).
  The check proves it exists; it cannot prove anyone reads slide 15.

## 13. Changing the narrative

`docs/narrative-operations.md` is the operational runbook: how to change the
narrative for a new run, how to reset or reseed it, how a facilitator verifies
it is present, and a failure, meaning and where-to-look table for the consistency
check.

The short version: **edit the contract, not the surface.** Adding a sentence to
`ridge/web.py` or a `.page` file is how the three surfaces drifted apart in the
first place, and `check_provenance` and `check_restatement` will fail on it.
