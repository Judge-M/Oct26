# Operation Silent Ridge (Judge-M/Oct26) — Independent Review

Review date: 2026-09-17 · Reviewed commit: `f4ad28b` (main, merge of PR #21)
Reviewer ran the test suite against this commit: **221 tests, all passing, ~32 s**.

---

## 1. What this project is

A cooperative defensive-cybersecurity incident-response CTF ("Operation Silent Ridge")
for **10 teams / 30 participants**, planned for late October 2026. Participants claim
tickets in DFIR-IRIS, investigate with **Autopsy, Wireshark, Cutter and Wazuh**, and
submit answers through **CTFd**; a Python "ridge" core (SQLite journal) owns
transactional state, ownership handoff, evidence release and scoring receipts.

The repo is unusually well-governed for an agent-built project: AGENTS.md, a task-card
system (A01–H01), a consolidation record for abandoned PRs 14–20, and deliberate
fail-closed behavior for unimplemented lifecycle commands. The README is honest:
**"Not event-ready."**

## 2. Executive verdict

**The content layer is essentially complete and good quality. The infrastructure layer
is maybe 40–50% done, and nothing has ever run end-to-end as a live stack.** Every
critical runtime claim so far rests on unit tests, one CTFd container smoke, and an
offline desktop boot — not on an integrated two-team run. The repo itself says this
repeatedly, and my review confirms it.

| Layer | State | Confidence |
|---|---|---|
| Challenge content (20 tickets, 80 questions) | Complete, coherent, verified against question matrix | High |
| Scenario / facilitator material | Complete, pedagogically careful | High |
| Ridge core state machine | Implemented, well-tested (221 unit tests green) | High for code, unproven live |
| CTFd / IRIS / Wazuh provisioning adapters | Source exists; only CTFd has a container smoke | Medium-low |
| Docker images (iris, ctfd, integration, desktop) | Build recipes + receipts machinery exist; no evidence of current successful builds in-repo | Unverified |
| Desktop VM (5.2 GB QCOW2, LFS) | Published, offline QEMU boot verified historically | Medium |
| Deployment orchestration (`ridge.deploy up/start/backup/restore/switch/down`) | **Deliberately refuses to run** — not implemented | Blocked |
| Recovery / AWS / fencing / teardown | Explicitly excluded stubs; open tasks | Blocked |
| Ten-team capacity | Unsupported — arithmetic says ~130 min/team of content vs 240-min target | Known gap |
| Offline release bundle | Not published; **zero GitHub Releases exist** | Gap |

## 3. What works (verified this review)

- **Test suite:** `python -m unittest discover -s tests` → 221 tests, OK. Covers core
  transactions, compose rendering, CTFd provisioning logic, deploy config/journal,
  desktop delivery, distribution, resilience, workload simulation, readiness-docs
  consistency. (The repo's own ASSESSMENT.md still cites "71 tests" — stale, see §6.)
- **Content generation:** `python expanded/author.py` deterministically generates
  `expanded/tickets.json` (20 tickets × 4 questions = 80), matching
  `docs/acceptance/question-matrix.md` row-for-row in my spot check (T01–T12 verified).
- **Question quality:** every question carries a prompt, exact answer, tool, evidence
  path, selection/query, source record, step-by-step walkthrough, and an explicit
  *limitation* ("transmission metadata does not establish human receipt…"). This is
  genuinely well-designed defensive content with real analytical rigor (clock-skew
  correction, coverage gaps, deliberate unresolved leads like WS-31).
- **Governance docs:** NEXT.md (N1–N5), BUILD-FIRST.md, CONSOLIDATION.md, task cards
  A01–H01 with dependencies and acceptance criteria form a credible finish plan.
- **Fail-closed deploy CLI:** `ridge.deploy` `up/start/backup/restore/switch/down`
  deliberately refuse; `build`/`verify-build`/`doctor` are implemented with fingerprinted
  build receipts and a process lock.

## 4. What is broken or missing (ordered by severity)

### P0 — blocks any live use
1. **No deployment orchestrator.** Nothing creates accounts, networks, certificates,
   desktops or AWS resources end-to-end. `ridge deploy up` refuses by design.
2. **Default config is not runnable.** `expanded/config.json` ships **5 teams** (event
   is 10), placeholder IRIS/CTFd IDs, and documentation-only IPs (192.0.2.x). It omits
   `iris_login` / `ctfd_name` required by `ridge/preflight.py`. (Known: ASSESSMENT P0-2;
   still true at this commit.)
3. **Evidence-delivery path incomplete.** Controller publishes releases to
   `RIDGE_EVIDENCE_PUBLIC`; desktops mount a baked `/opt/silent-ridge/evidence`. No
   tested replication connects them, so inject tickets (T07/T09/T11/T19 follow-ups)
   cannot reach a running desktop yet.
4. **Central provisioning/Wazuh incomplete.** Wazuh certs/index/roles are candidate
   manifests; integration compose lacks the local-CA trust mount; IRIS pgcrypto init and
   admin-role wiring are unproven (NEXT.md N1 items 3–4).
5. **No live vertical slice.** `ridge/vertical_slice.py` (171 lines) exists but has never
   run against a built stack (N3).

### P1 — required before event approval
6. **Recovery is SQLite-only.** `ridge.export_run` excludes IRIS/CTFd/Wazuh native DBs,
   Guacamole state, desktop workspaces and deploy secrets. Restoring the export alone
   breaks ID mappings (identity portability problem).
7. **No offline release.** Zero GitHub Releases; image digests and dependency bundle are
   unfinished gates. `ridge.bundle` and `ridge.distribution` use different inventory
   conventions.
8. **AWS path zero-progress.** QCOW2 is not an AMI; no import test, no fencing, no
   cost-aware teardown.
9. **Capacity math doesn't close.** 20 tickets × 65 min = 1,300 team-minutes → ~130
   min/team at 10 teams vs the 240-min target (docs/workload.md is honest about this;
   simulated makespan 195 min). Needs either measured down-scoping or more content.
10. **Run isolation:** constant compose project/volume names risk state reuse across runs.

### P2 — polish/usability
11. Question matrix itself admits walkthroughs are "not yet verified on installed tools"
    (docs/expanded-validation.md row 80).
12. Rendered participant guide packaging outstanding; old `desktop/install.sh` vs
    `configure-image.sh` duplication unresolved.
13. Legacy `app/` + `admin/` portal still present as a test fixture only — fine, but its
    docs (`docs/admin-panel.md`) are retired stubs pointing elsewhere.

## 5. Challenge content assessment

- **Scenario:** fictional SOC disclosure exercise (insider-style data egress of a
  movement brief, "LANTERN v3", via a session-stealing viewer). Fully fictional, clean
  legal/safety posture, no executable malware in the repo (the "brief-viewer.exe" is a
  training binary, source included at `expanded/binary/brief-viewer-training.c`).
- **Structure:** 5 analytic lanes (network, endpoint, identity, server, hunting) mapped
  to NICE work roles in `docs/learning-objectives.md`; cooperative global ownership
  model (teams claim/relinquish tickets; points persist across ownership changes).
- **Difficulty/coaching:** graduated hints + free walkthroughs with no point penalty —
  good for beginners, but as ASSESSMENT notes, this is coached practice, not assessment
  of unaided mastery. Since all answers are public on GitHub, treat this event as a
  coached exercise; for any scored assessment you need a private content variant
  (facilitator/ground-truth.md says this explicitly — good).
- **Timeline/evidence discipline:** excellent — canonical 50-minute UTC timeline,
  deliberate evidence gaps, a 120-second device-clock correction exercise, and
  inject-based escalation (3 injects).
- **Risk:** 80 questions' answers are pinned to exact evidence values; any regeneration
  of evidence assets must re-verify the whole matrix (this is an explicit unmet gate).

## 6. Contradictions and stale information found

1. **Participant count/date mismatch (legacy vs current).** Root `config.json`:
   20 participants, 180 minutes, 5 cells, `exercise_date 2026-10-15`. README/current
   design: **10 teams / 30 participants**, 260-minute target. The root config is the
   retired baseline's, but nothing in-file says so.
2. **Event date inconsistency.** `expanded/config.json` and all generated Wazuh-question
   steps say the exercise date is **2026-10-15**; the repo is named Oct26 and the event
   is "a few weeks" from mid-September. Either the scenario date is a fixed fiction
   (fine, but then say so) or it's stale.
3. **`expanded/config.json` team count.** 5 teams defined vs 10-team event; IPs are
   RFC-5737 documentation addresses. Preflight-required keys missing. (Flagged in
   ASSESSMENT P0-2; still open.)
4. **ASSESSMENT.md is now partially stale:**
   - Cites "71 tests" → actual suite is now 221 tests.
   - P2 claims `versions.json` "still names Cutter 2.3.4" → versions.json now correctly
     says 2.5.0; the only remaining 2.3.4 references are inside ASSESSMENT.md itself.
   - PR #6/#7 review sections are moot: both PRs are closed (#6's content effectively
     landed — learning-objectives.md already contains the corrected T13/T14 and T15/T16
     language the PR review demanded).
5. **`expanded/tickets.json` is referenced but not committed.** `ridge/cli.py` defaults
   `--content expanded/tickets.json`, and `docs/resilience.md` +
   `docs/handoff/historical-notes/migration-and-operations.md` both instruct operators to
   run `migrate --content expanded/tickets.json`. The file must first be generated by
   `python expanded/author.py`; neither doc says that. A fresh checkout following those
   docs verbatim fails.
6. **`docs/expanded-validation.md` lingering caveats** that read like open blockers but
   mix resolved and unresolved states (e.g., handout packaging "still outstanding"
   alongside verified artifact rows) — needs a dated refresh as task A01 intends.
7. **Deploy docs vs reality (intentional but pervasive):** older task reports and
   historical-notes describe manual bootstrap recipes (LOCAL-SETUP-FINDINGS.md) that
   AGENTS.md explicitly overrides. Anyone skimming docs/linearly will hit contradictory
   procedures; the repo relies on readers starting at AGENTS.md.
8. **Workload numbers:** 260 (per-team target, `expanded/config.json`), 240 (docs/workload
   target), 130 (actual 10-team average), 195 (simulated makespan) — all correct in
   context but scattered; a reader can easily quote the wrong one.

## 7. Steps to a usable product (recommended order)

The repo's own N1–N5 sequence is sound; here's the condensed critical path with my
emphasis:

1. **Week 1 — Content freeze & docs cleanup (low risk, do immediately).**
   - Task A01/A02: regenerate the acceptance record, fix §6 items (config date note,
     tickets.json generation step, refresh ASSESSMENT, pick the real event date).
   - Decide the 10-team workload answer (accept ~130 min + facilitated discussion, add
     content, or shorten the event window). This is a *content* decision that blocks
     rehearsal planning.
2. **Week 1–2 — Real builds (N1).** Run the four image builds on the actual Docker host;
   wire the two-team profile into IRIS/CTFd bootstrap; complete Wazuh certs/index/roles;
   record receipts.
3. **Week 2 — Desktop slice (N2).** One container desktop through Guacamole, three
   concurrent clients, seeded WS17 case, evidence-release delivery to desktops proven
   (this closes the biggest functional hole).
4. **Week 2–3 — Two-team live acceptance (N3).** Real vertical slice: findings/points
   verified after delivery, ownership transfer, worker restart, browser sessions,
   interrupted-response delivery. Finish paused.
5. **Week 3 — Lifecycle (N4).** One-command up/status/down with journal, kill/resume
   tests, truthful gating.
6. **Week 3–4 — Recovery + release (N5).** Full-stack backup/restore (native DBs +
   workspaces), verified backup before any teardown, offline bundle with pinned digests,
   **and a full ten-team dress rehearsal**. AWS switching only if time remains —
   consider descoping AWS entirely for this event; a single well-tested local site beats
   an untested failover.
7. **Create the private variant** if any scoring matters (answers are public).

## 8. Notable strengths worth preserving

- Honest status taxonomy (source implemented ≠ image built ≠ service started ≠ accepted).
- Deterministic content generation with checksums and LFS manifests.
- Question-level evidence limitations — rare and pedagogically excellent.
- Fail-closed CLI preventing premature "it works" claims.

## 9. Key risks if unmanaged

- **Schedule risk:** N1–N3 have never been executed even once; each contains known-hard
  unknowns (Wazuh vendoring, Guacamole schema reconciliation, IRIS init). A few weeks is
  tight; the content/docs cleanup (week 1) and descoping AWS are the main levers.
- **Capacity risk:** content may under-fill the event window at 10 teams.
- **Single-host risk:** no fencing; never run two writable sites.
