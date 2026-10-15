# CTF walkthrough (PR #196) - independent content review

Review date: 2026-10-01
Reviewed commit: `dd46a18` (branch `docs/ctf-walkthrough`, PR #196)
Subject: `docs/walkthrough/CTF-WALKTHROUGH.md` (771 lines) and its 7 screenshots
Method: every factual claim was re-derived from the repository's sources of truth; the
screenshots were opened and read, not trusted. Line numbers below refer to `dd46a18`.

This review is read-only with respect to the walkthrough. It records findings; it does
not edit the document. Landing fixes is a separate instruction.

---

## 1. Verdict

The narrative, the participant guidance and the screenshots are high quality and mostly
exact. Fourteen things need fixing or deciding before the document is presented as
authoritative.

| Class | Count | Meaning |
|---|---|---|
| A - contradicts a source of truth | 7 | Wrong on the facts; must be corrected |
| B - internal inconsistency | 4 | The document disagrees with itself |
| C - unverified or likely false | 2 | Claim cannot be supported as written |
| D - process | 1 | PR structure problem |

The single largest defect class is the phase/ticket tables in section 7: phase
boundaries are shifted by one ticket from T11 onward, and five of the twenty tool
entries are wrong.

---

## 2. Sources of truth used

| Claim type | Source of truth |
|---|---|
| Phase membership and phase titles | `ridge/scenario_narrative_v1.json`; cross-checked in `docs/learning-objectives.md:252-264` |
| Ticket titles, tools, dependencies, answers, hints | `expanded/tickets.json` (gitignored; regenerate with `python expanded/author.py`) |
| Learning objective content and mechanism | `docs/learning-objectives.md` - one section per LO (LO1 line 61, LO2 line 91, LO3 line 116, LO4 line 140, LO5 line 160, LO6 line 180, LO7 line 202, LO8 line 223), each with a **Mechanism** and an **Achievement evidence** paragraph |
| Claim-button gate | `ridge/web.py:22` |
| Wazuh data view definitions | `deployment/expanded/wazuh/saved-objects.json` |
| Desktop shortcuts | `deployment/expanded/desktop/configure-desktop.sh` (and `configure-image.sh`, `install.sh`) |
| Rendered page encoding | `ridge/web.py:2` |
| The PR itself | `git show dd46a18`, `gh pr diff 192`, `gh pr view 196` |

---

## 3. Findings

### A. Contradicts a source of truth

#### F01 - Phase boundaries are shifted by one ticket from T11 onward

Locations: lines 554, 580, 599, and the ticket rows at 563, 588.

Document says:

- Phase 2 = T06-T11
- Phase 3 = T12-T16
- Phase 4 = T17-T20

Repository says (`ridge/scenario_narrative_v1.json`, identical in
`docs/learning-objectives.md:252-264`):

- Phase 2 = T06-T10
- Phase 3 = T11-T15
- Phase 4 = T16-T20

Consequences: T11 is tabled under Phase 2 (line 563) but belongs to Phase 3; T16 is
tabled under Phase 3 (line 588) but belongs to Phase 4; Phase 4 omits T16 entirely.

Fix: change the three headings and move the T11 and T16 rows. Phase 1 (line 525) is
already correct.

#### F02 - Phase 4 title is wrong

Location: line 599.

Document: `Phase 4 - Corroborate and state the conclusion (T17-T20)`
Repository: `Phase 4 - Correlate and state the defensible conclusion`

Fix: use the repository wording, including the ticket range once F01 is applied.

#### F03 - Five of twenty tool entries are wrong, and one title is another ticket's

Locations: lines 559-561, 605-606 (also titles at 563, 603).

| Line | Document | Repository (`expanded/tickets.json`) |
|---|---|---|
| 559 | T07 `Audit document and roster access`, tool `Autopsy` | T07 is **`Test the effect of the password reset`**, tool **Wazuh**. The document has given T07 T08's title and T08's tool. |
| 560 | T08 tool `-` | T08 tool is **Autopsy** (title `Audit document and roster access` is correct here) |
| 561 | T09 `Superseding brief`, tool `-` | T09 is **`Compare superseding movement information`**, tool **Linux file manager** |
| 605 | T19 `Compare DLP body hash with catalog`, tool `-` | T19 is **`Verify the transmitted payload`**, tool **Linux file manager** |
| 606 | T20 `Exposure limits`, tool `-` | T20 is **`Test the limits of the overall exposure conclusion`**, tool **Wazuh** |

Also truncated titles: line 563 `Unresolved host lead` vs
`Investigate the unresolved host lead`; line 603 `Inspect the harmless training binary`
vs `... binary configuration`.

Fix: regenerate the table from `expanded/tickets.json` rather than editing by hand.

Note: the descriptions in the "Core objective" column are accurate. Only the title and
tool columns are wrong.

#### F04 - The dependency diagram is missing three of five edges

Location: lines 650-656.

Document shows only `T06 -> T07` and `T07, T09, T11, T19 -> T20`.

Repository (`expanded/tickets.json`, `requires` field) has five edges:

```
T06 -> T07
T08 -> T09
T10 -> T11
T01 + T05 -> T19
T07 + T09 + T11 + T19 -> T20
```

Fix: add `T08 -> T09`, `T10 -> T11`, `T01 + T05 -> T19`. Without `T01 + T05 -> T19`
the diagram cannot explain why T19 - a Phase 4 ticket the document calls a payload
comparison - does not open at the start.

#### F05 - "12 of 20 had a claim button; the rest were locked pending prerequisites" is wrong

Location: lines 658-660.

Two separate claims, both unsupported:

1. **"the rest were locked pending prerequisites"** - only 5 of 20 tickets have a
   `requires` value (T07, T09, T11, T19, T20). The other 15 have `requires: []`, so
   at most 5 tickets could ever be locked that way. 20 - 12 = 8 cannot all be
   prerequisite locks.
2. **"12 of 20"** - the claim button requires
   `snapshot.mode=='running' and t.status=='available' and t.iris_id`
   (`ridge/web.py:22`). Tickets are delivered to IRIS asynchronously, so a ticket can
   be unlocked yet unclaimable for a short window. That is "not yet prepared", which
   is a different condition and is not prerequisite locking.

Fix: either state the number with the correct reason (N unlocked; M of those still
being delivered to IRIS) or state the repo-provable fact: **15 tickets have no
prerequisites and 5 are gated**. Do not attribute the gap to prerequisites.

If a run-specific number is kept, re-read it from the run's own state database at the
stated moment. The number is an observation, not a product fact.

#### F06 - The "verbatim" coached route is truncated, and on `main` it does not exist at all

Locations: lines 220-236.

Two problems.

**(a) Truncated.** On this branch, `expanded/author.py:92` (`EXTRA_STEPS`) adds two
extra steps to T01-Q1. The document quotes the first and stops mid-way through the
second. The quoted block (lines 234-235) ends at `its workstation name (WS-17).` and
omits the sentence that follows it in the source:

> `The address column in that file is not the same address, so correlate by account
> rather than by address.`

That omitted sentence is the point of the step. A reader copying the quote gets an
incomplete instruction under a heading that says "verbatim".

**(b) Branch-dependent.** Those two extra steps come from PR #192, which is not on
`main`. On `main`, `expanded/author.py` has no `EXTRA_STEPS` and `expanded/tickets.json`
ships T01-Q1 with the four base steps only. So the quoted block is true on this
branch and false on `main`.

Fix: re-copy the steps from a freshly generated `expanded/tickets.json` on this branch,
and add a note that the route requires PR #192 to have landed.

#### F07 - `silent-ridge-timed` cannot be selected in the user interface

Locations: lines 363, 390, 592, 718.

Document tells participants to select `silent-ridge-timed`, and to distinguish it from
`silent-ridge-timeless`.

`deployment/expanded/wazuh/saved-objects.json` defines two index patterns:

| id | title (what the picker displays) | timeFieldName |
|---|---|---|
| `silent-ridge-timed` | `silent-ridge-*` | `timestamp` |
| `silent-ridge-timeless` | `silent-ridge-*` | (none) |

Both have the **same title**, so the picker shows `silent-ridge-*` twice and the
documented names never appear. Screenshot `images/05-wazuh-discover-497-hits.png`
confirms it: the selected view reads `silent-ridge-*`.

This is a product defect as well as a documentation defect, and it undercuts the LO6
lesson (line 385), which rests on the participant picking the right one of two views.

Fix - pick one, and record the decision:

- give the two patterns distinct titles (`silent-ridge-timed`, `silent-ridge-timeless`)
  and keep the document as written, or
- keep the titles and reword the document plus `expanded/guides.md` and
  `docs/learning-objectives.md` to describe them by their time field (one has
  `timestamp`, one has none).

Either way `expanded/author.py:131` (`choose the silent-ridge-* data view`) must agree
with whatever the document says.

### B. Internal inconsistencies

#### F08 - Section 10 drops tickets that section 3 and section 7 assign to LO2

Location: line 672.

Section 10 lists LO2 as `T15, T16, T19, T20`. But:

- section 3 (line 244) assigns LO2 to the T01 four-hop chain;
- section 7 (line 531) assigns `LO1, LO2` to T01;
- `docs/learning-objectives.md:101-114` builds LO2 from `req-71` (T01), session
  `S-41` (T06), the cached hash (T05/T19), T15, T16 and T20.

Fix: section 10 should include T01 (and the identifier joins in T05/T06) or explain
why it lists only the later tickets.

#### F09 - LO5 is attributed three different ways

Locations: lines 563, 584, 586, 675.

- Section 10 (line 675): `T08-T12, T19, T20`. This matches
  `docs/learning-objectives.md:171-175` exactly - correct.
- Section 7 line 563: T11 is `LO6` only - should include LO5.
- Section 7 line 584: T12 is `LO1, LO6` - should include LO5.
- Section 7 line 586: T14 is `LO1, LO5` - but LO5's mechanism never cites T14.

Fix: make section 7 match section 10, and drop LO5 from T14 unless there is a reason
the document should state.

#### F10 - The desktop icon table misdescribes two entries and omits one

Locations: lines 309-317.

- `File system` is described as "CSVs you would otherwise open in a spreadsheet". It is
  the stock Xfce root-filesystem icon; `/evidence` is the separate **Evidence** icon
  (`configure-desktop.sh`: `shortcut 'Evidence' 'thunar /evidence'`). Screenshot 04
  shows both, plus **Home**.
- `Incident queue` / `Questions and help` / `How-to guides` are described together as
  "Shortcuts back to IRIS and CTFd". The first two are
  (`configure-desktop.sh:33-34`); `How-to guides` runs
  `shortcut 'How-to guides' 'thunar /evidence/guides'` (`configure-desktop.sh:37`) -
  a folder, not a link to either web app.
- `Home` is present in screenshot 04 and absent from the table.

Fix: split the third row, correct the `File system` description or drop it, add `Home`.
The authoritative shortcut set is the eight named in `configure-desktop.sh`.

#### F11 - Section 3's card anatomy claims seven parts; the quoted card has eight

Locations: lines 195-218.

The table lists Heading, Phase, Why this question matters, Route, Coached steps, Answer
format, Recovery. The card quoted immediately above also contains a **Purpose**
paragraph (`ridge/web.py` renders `q.purpose` separately from `q.stakes`).

Fix: either add Purpose to the table or fold it into the "Why this question matters"
row and say so.

### C. Unverified or likely false

#### F12 - The mojibake claim is not supported

Location: lines 736-737.

The document states em-dashes render as the replacement character in participant
strings.

What is true: em-dashes (`U+2014`) really are in participant-visible strings - the
help-level heading in `ridge/web.py:29` (`Help level 3` + `U+2014` +
`explicit walkthrough`), the
relinquish control on `ridge/web.py:23`, and `expanded/guides.md:52`, which
`expanded/prepare.py:196` ships as `guides/getting-started.md`. So the claim is
coherent.

What argues against it: `ridge/web.py:2` opens the shared page template with
`<meta charset="utf-8">`, which tells the browser to decode as UTF-8. On that basis
the page should render correctly.

The likeliest explanation is a terminal artifact: PowerShell renders `U+2014` and
`U+00A7` as garbage even when the bytes are correct. That reproduces on demand in this
very repository - `ridge/web.py:19` contains `U+00B7` (MIDDLE DOT), and reading it through a
console shows a replacement character while the file bytes stay clean UTF-8. A console
rendering is not evidence about a served page.

Needs one of: a screenshot of the affected page listing the codepoints, or removal.
Do not publish an unverified defect claim in a document that otherwise verifies
cleanly.

#### F13 - The UTC conversion in section 5.1 is timezone-dependent and can recreate the trap it warns about

Location: lines 370-376.

The screenshot reads `Oct 15, 2026 @ 04:00 -> 06:30`, which the document glosses as
"(local rendering of `08:00 -> 10:30 UTC`)". The Kibana/OpenSearch time picker renders
**browser-local** time, so that conversion holds only if the browser was at UTC-4 when
the screenshot was taken. The repository cannot confirm the browser's timezone.

Two further wrinkles:

- the taught range elsewhere is `08:00-09:30` UTC
  (`expanded/author.py:132`, `expanded/guides.md:55`), not `08:00-10:30`;
- the fix is phrased "set an absolute **UTC** range", but the field takes local time.
  Only a machine already at UTC gets the right instant by typing `08:00`. On a UTC-4
  machine `08:00` means 12:00 UTC, and on a UTC+2 machine it means 06:00 UTC - both
  outside the window, both producing exactly the zero-result condition section 12.1
  warns about. Note this also means the screenshot's displayed numbers imply the
  screenshotting browser was at UTC-4; that is an inference, not a stated fact.

Fix: state the browser timezone the screenshot was taken in, and phrase the instruction
as "set an absolute range on the scenario date; the picker uses your machine's local
timezone", with the worked example showing local and UTC together.

### D. Process

#### F14 - PR #196 is stacked on PR #192 and does not say so

`gh pr view 196 --json files` reports 14 changed files, but only 8 are the walkthrough.
The other 6 (`docs/handoff/*`, `expanded/author.py`) belong to PR #192. Merge order is
therefore constrained, reviewers see unrelated changes, and F06 depends on this
stacking.

Fix: disclose it in the PR body, or rebase so that PR #196 contains only the
walkthrough files.

---

## 4. Verified correct (do not re-litigate)

Checked and confirmed exact at `dd46a18`:

- Ports in the tab table and quick-start card (CTFd 8083, IRIS 8081, Guacamole
  `:8082/guacamole/`, Wazuh 8443); the `/guacamole/` path matches
  `ridge/deploy/local.py`.
- Both CA fingerprints and the stale-CA trap (two `silent-ridge-ca` certificates with
  different keys).
- Every quoted string checked character by character: `Correct - one point earned.
  Findings synchronization pending.`, `Relinquish - keep completed answers`, `Open IRIS
  tasks and shared findings`, the 409 message, `Answered by {{solved_by}}`, `Owner:`.
- The T01-Q1 card anatomy (prompt, purpose, steps, format, recovery, hints) against
  `expanded/tickets.json`.
- Help levels 1-3 and the level-3 text, verbatim from `hints`.
- `CTFD_LOGIN_INTERVAL_S = 6.1` (`expanded/load.py:57`) and that the participant guide
  does not mention it. Note the guide is generated: `expanded/prepare.py:196` writes
  `guides/getting-started.md` from `expanded/guides.md`, and that source contains no
  mention of `6.1`, a login interval, `429` or rate limiting. The document's bare
  `getting-started.md` (line 722) should name `guides/getting-started.md`.
- 505 documents at provision; T13/T14 acquisition
  `2026-09-15T23:22:04.3517080Z`; the 120-second correction applies only to T04.
- T20 requires T07, T09, T11, T19 (the only dependency the document gets right).
- Section 8's four answer-format examples are all real answers from
  `expanded/tickets.json`.
- Section 0's scenario brief and operating rule, verbatim from
  `ridge/scenario_narrative_v1.json`.
- One-ticket-at-a-time (`ridge/state.py`), and the `solved_by` -> `team-01` /
  scoreboard `team1` split (team id vs CTFd team name) - correct in both contexts.
- Section 11's scoreboard retraction is consistent with issue #193's edited text.
- Section 10's LO5 and LO6 rows are exact matches for
  `docs/learning-objectives.md:171-175` and `:198`.
- Screenshot 04: icons match the eight shortcuts in `configure-desktop.sh` plus stock
  Xfce icons. Screenshot 05: 497 hits, index `silent-ridge-oct26`, `timestamp per 5
  minutes`, and the seven listed fields all match the image.

---

## 5. How to reproduce this review

On a clean clone. PowerShell 5.1 notes are included because several checks fail there
for quoting reasons, not for content reasons: `*` inside a double-quoted string is
expanded, and em-dashes/U+00A7 render as garbage in the console even when the bytes are
correct. Read files, do not trust the console.

```powershell
# 1. Get the branch under review.
git fetch origin docs/ctf-walkthrough
git worktree add ..\oct26-review FETCH_HEAD

# 2. expanded/tickets.json is gitignored (.gitignore:20) and absent on a clean clone.
#    Generate it before checking any ticket fact.
cd ..\oct26-review
python expanded/author.py

# 3. F01, F02 - phase boundaries and titles.
python -c "import json; d=json.load(open('ridge/scenario_narrative_v1.json',encoding='utf-8')); print([ (p['title'],p['tickets']) for p in d ])"
Select-String -Path docs/learning-objectives.md -Pattern 'Phase 1|Phase 2|Phase 3|Phase 4'

# 4. F03, F04, F05 - ticket titles, tools, dependencies.
python -c "import json; d=json.load(open('expanded/tickets.json',encoding='utf-8')); [print(t['id'], '|', t['subject'], '|', t['title'], '| requires=', t['requires']) for t in d]"

# 5. F06 - the two steps the walkthrough omits.
Select-String -Path expanded\author.py -Pattern 'EXTRA_STEPS' -Context 0,8
git grep -n 'EXTRA_STEPS' -- expanded/author.py

# 6. F07 - why silent-ridge-timed is not selectable.
python -c "import json; d=json.load(open('deployment/expanded/wazuh/saved-objects.json',encoding='utf-8')); objs = d if isinstance(d,list) else d['objects']; [print(o['id'], '|', o['attributes'].get('title'), '|', o['attributes'].get('timeFieldName')) for o in objs]"

# 7. F09, F10 - learning objectives and desktop shortcuts.
Select-String -Path docs\learning-objectives.md -Pattern 'Mechanism|Achievement evidence'
Select-String -Path deployment\expanded\desktop\configure-desktop.sh -Pattern "shortcut '"

# 8. F12 - the encoding claim.
Select-String -Path ridge\web.py -Pattern 'charset'

# 9. F14 - what the PR actually contains.
gh pr view 196 --json files,headRefName,baseRefName,mergeable
gh pr diff 192
```

Live-run observations (the "12 of 20" claim in F05, the 497-hit figure, the scoreboard
value) come from a 4-team run on a separate host and cannot be reproduced from a clean
clone. Re-read them from that run's `work/runtime-play/state/state.sqlite` and the
screenshot rather than restating them.

---

## 6. Open decisions for the organizer

1. **F07 is a product fix or a wording fix.** One of the two Wazuh index patterns is
   effectively unselectable by name. Which way do we go?
2. **F06 and F14 are the same dependency.** The walkthrough quotes content that exists
   only on PR #192's branch. Confirm PR #192 lands first, then re-copy the quote.
3. **F05 needs a decision on what number to publish** - a repo fact (15 ungated, 5
   gated) or a run observation with its provenance stated.
4. **F12 needs evidence or removal.** An unverified defect claim in a document that
   otherwise verifies cleanly is the most damaging kind of error here.
5. **Fix in place or review-comment first?** This document proposes fixes; it has not
   applied them. Applying them to `docs/ctf-walkthrough` and pushing updates PR #196;
   that is a separate instruction.
