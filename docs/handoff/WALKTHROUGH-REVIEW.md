# Handoff: CTF walkthrough review (PR #196)

Status: **review complete, fixes not applied.**
Date: 2026-10-01
Branch: `docs/ctf-walkthrough` @ `dd46a18` (PR #196, base `main`, mergeable)
Full findings: [`docs/reviews/walkthrough-review-2026-10-01.md`](../reviews/walkthrough-review-2026-10-01.md)

This file exists so a fresh agent can pick the work up from the repository alone, with
no earlier chat.

---

## Read in this order

1. `AGENTS.md` - standing rules, including the ones that bind this task (below).
2. `docs/reviews/walkthrough-review-2026-10-01.md` - the deliverable: 14 findings,
   each with location, what the document says, what the repository says, and a fix.
   Section 4 lists what was verified correct so you do not redo that work. Section 5
   has reproduce-it-yourself commands.
3. `docs/walkthrough/CTF-WALKTHROUGH.md` - the subject, at the same commit the
   findings cite. Line numbers in the review match this file exactly at `dd46a18`.

Then stop and ask which of the decisions in the review's section 6 the organizer wants
taken.

---

## Where things stand

| Item | State |
|---|---|
| PR #196 `docs/ctf-walkthrough` | OPEN, head `dd46a18`, 14 files, mergeable. 8 are the walkthrough, 6 belong to PR #192 (F14). |
| PR #192 `fix/taught-evidence-paths` | OPEN, head `9b84bae`. Not merged. The walkthrough quotes content that only exists here (F06). |
| PR #185 `fix/wazuh-bringup-defects` | OPEN, head `f02ca10`. |
| PR #183 `fix/bounded-http-503-reset` | OPEN, head `c675ac8`. |
| Issue #193 | OPEN, **already edited** to withdraw the "scoreboard empty" claim as not reproduced. Do not re-file it. |
| Walkthrough fixes | **None applied.** The review is read-only on the subject. |
| Issue #188 (empty scoreboard as a defect) | Correctly never filed. The stress-receipt rendering did not reproduce in the 4-team run. |

Known gaps in the handoff docs themselves, found while writing this file:

- `docs/handoff/README.md` links to `CLEAN-BASELINE-RECEIPT.md`,
  `DESKTOP-USABILITY-RECEIPT.md`, `FULL-VERIFICATION-RECEIPT.md` and
  `PILOT-2TEAM-RECEIPT.md`. **None of the four is tracked on this branch**, so those
  links are dead here. They live on other branches; do not assume a missing receipt is
  a deleted receipt.
- `docs/handoff/AI-START-HERE.md` and `docs/handoff/ISSUE-INDEX.md` are **not in the
  repository at all** on this branch. If they appear on a checkout, they are untracked
  leftovers and their "nothing has been pushed" status is stale - refresh rather than
  trust them.

---

## The 14 findings in one line each

**Must fix (contradicts a source of truth):**

- **F01** Section 7 phase boundaries are shifted by one ticket from T11 on; correct
  split is T06-T10 / T11-T15 / T16-T20.
- **F02** Phase 4 title is "Correlate and state the defensible conclusion", not
  "Corroborate and state the conclusion".
- **F03** Five of twenty tool entries wrong (T07, T08, T09, T19, T20); T07 carries
  T08's title.
- **F04** Dependency diagram shows 2 of 5 edges; missing T08->T09, T10->T11,
  T01+T05->T19.
- **F05** "12 of 20 … the rest were locked pending prerequisites" - only 5 tickets
  have prerequisites; the gap is async IRIS delivery, not locking.
- **F06** The "verbatim" coached route omits the last sentence of T01-Q1's second
  step, and does not exist on `main` (it comes from PR #192).
- **F07** `silent-ridge-timed` / `silent-ridge-timeless` are not selectable: both
  index patterns are titled `silent-ridge-*`. Product defect, not just wording.

**Internal inconsistencies:**

- **F08** Section 10's LO2 row omits T01, which sections 3 and 7 assign to LO2.
- **F09** LO5 attributed three different ways; section 7 omits it from T11 and T12 and
  adds it to T14 wrongly.
- **F10** Desktop icon table: `File system` misdescribed, `How-to guides` wrongly
  grouped as a web-app shortcut, `Home` missing.
- **F11** Card anatomy claims seven parts; the card it quotes has eight (Purpose).

**Unverified / likely false:**

- **F12** Mojibake claim - `ridge/web.py:2` sets `<meta charset="utf-8">`. Almost
  certainly a terminal artifact. Needs a screenshot with codepoints, or delete it.
- **F13** Section 5.1's "(local rendering of 08:00 -> 10:30 UTC)" depends on browser
  timezone and conflicts with the taught 08:00-09:30 UTC range.

**Process:**

- **F14** PR #196 is stacked on PR #192; disclose it or rebase.

---

## What the next agent should do

Suggested sequence, one item at a time, evidence for each:

1. **Confirm the branch.** `gh pr view 196 --json headRefOid,files,mergeable` and
   compare to `dd46a18`. If the head moved, re-check line numbers before trusting the
   review's citations.
2. **Answer the five decisions** in review section 6. They change what gets edited,
   and F06/F07 cannot be resolved by editing prose alone (one needs PR #192 to land,
   the other may need `saved-objects.json` changed).
3. **Apply F01-F05 and F08-F11** to `docs/walkthrough/CTF-WALKTHROUGH.md` as one
   focused commit. These are prose/table corrections with unambiguous answers. Prefer
   regenerating the section 7 tables from `expanded/tickets.json` over hand-editing.
4. **Resolve F12 and F13 before publishing.** Either gather the evidence or remove the
   claim. Do not leave an unverified defect claim in a document that otherwise
   verifies cleanly.
5. **Handle F14** - add a line to the PR #196 body noting it contains PR #192's
   changes, or rebase onto `main`.
6. **Record the result** the way the repository expects: commit, changed files, what
   was verified, what was not, and the next blocked item. Add a "Latest" line to
   `docs/handoff/README.md` if this becomes a new receipt.

Stop after the walkthrough is corrected and the record is written. Do not merge.

---

## Rules that bind this task

- **Never merge a PR.** Landing is the organizer's.
- **Never claim event certification.** N2/F03 is open: no human has played the
  exercise. A scripted HTTP pass is not certification.
- **Do not touch `Dockerfile:106` and do not start event services** for a documentation
  task.
- **No secrets, rosters or live event state** in anything you push. `work/` is private.
- **Verify the verifier.** The recurring failure in this project is trusting a local
  signal (outbox `done=1`, a green unit test, a passing HTTP status, a console
  rendering) for a remote fact. Check the native store or the image itself.
- **PowerShell 5.1 traps** that produced false alarms during this review: `*` inside a
  double-quoted argument is expanded (`count(*)` breaks), and `U+2014`/`U+00A7` render
  as garbage in the console even when file bytes are correct. Check codepoints, not
  the console.
- **`expanded/tickets.json` is gitignored** (`.gitignore:20`) and absent on a clean
  clone. Run `python expanded/author.py` before checking any ticket fact.

---

## Limitations of this review

- Static and screenshot-based. No container, image or service was started.
- The walkthrough's run-specific observations (497 hits, the "12 of 20" figure, the
  scoreboard value, the four-clicks-deep findings path) were checked against the
  screenshots and against the repository, not re-executed against a live stack. The
  live run state lives on a separate host and is not in the repository.
- `docs/learning-objectives.md` mechanism sections were used as the authority for
  learning-objective membership. If the organizer wants a different authority, F08 and
  F09 should be re-derived from it.
- Screenshots: 04 (desktop) and 05 (Wazuh Discover) were opened and read, and are the
  basis of F07, F10 and the review's screenshot claims. 01, 02, 03, 06 and 07 were not
  opened in this pass - their captions were checked against the repository, not against
  the pixels.
