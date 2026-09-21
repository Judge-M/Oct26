# G01 Receipt (independent slice) — Operator runbook

Date: 2026-09-20. Branch: `chore/g01-runbook`. Base: `main` (through PR #35).
Test count: **280 passing** (documentation-only change).

## Blocked prerequisite (named per card)

G01 lists **A01, F06**. **F06 (dress rehearsal) is blocked** — it needs the
event hardware and follows F03/F05. Per the card's finish-and-stop rule this
turn completes only the independent work: the operator runbook. **The release
freeze itself is not declared** — freezing before the dress rehearsal would be
exactly the unsupported-claim pattern the card forbids.

## What was built

**`docs/runbook.md`** — the operator handoff document, generated from the
accepted, drill-tested commands (every command in it has been run against the
real stack in the N1–N5 drills, except where labeled):

- One-page event-day sequence: doctor → up → status → distribute logins →
  start → announce/recover during play → pause → backup → down. Participant
  URLs and the private-runtime conventions stated up front.
- Symptom → diagnostic → action table covering the failures actually observed
  in drills (stage probe errors, start gating, the unlock-delivery transient,
  outbox backlog, disconnected team, desktop resource pressure).
- Appendix A: private credential locations and backup layout/retention.
- Appendix B: full wipe/restore procedure with the refusal semantics
  (`--accept-release`, `--degraded-ok` naming data loss), `fence`, and the
  explicit statement that `switch` awaits the AWS provider.
- Appendix C: offline bundle install/verification (`ridge.offline_install`),
  including the `certified_complete: false` drill-material distinction.
- Appendix D: retained-cost inventory (local: none after `down`; AWS: not
  built, cost verification is part of E03–E05).
- Known limitations: capacity/duration unproven until F03/F06; AWS provider
  and off-box copy unbuilt; Windows `prepare` verified on one host only.

README now links the runbook as the event-day reference.

## Acceptance-check status against the card

- "Generate a concise runbook from the accepted commands…" — **done**.
- "A second agent or operator follows the runbook without conversation history
  and completes the accepted two-team smoke" — **not done**: requires a fresh
  operator/host, naturally paired with the F05 cold-cache install test and the
  F06 dress rehearsal. The runbook was written to make that test possible.
- "Event-day instructions fit on one page with detailed recovery appendices" —
  structured that way (page one ends before the appendices).
- Freeze, readiness-document version pinning to a final release: **deferred**
  until F06 closes; untested profiles remain explicitly unsupported.
