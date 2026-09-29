# Facilitator-only: the optional breadcrumbs

These are the traces left across the prepared evidence for issue 59. They carry no
points, they are never required, and no scored question, step, hint or selection
names one. A team that finds none of them has done the exercise correctly. Read
[ground-truth.md](ground-truth.md) for the answers and
[solutions.md](solutions.md) for the coaching.

Participant-facing text lives only in `assets/breadcrumbs-v1.json`. Do not restate
a breadcrumb in a hint, in a spoken briefing or in the deck: a hint that quotes one
turns an optional aside into a scored dependency.

## Attribution: read this first

Issue 59 asks for "fictional adversary" Easter eggs. The approved narrative
contract deliberately forbids naming an adversary group, codename, operator or
sponsor (`assets/scenario-narrative-v1.json`, `exercise.adversary`), and T20-Q4
scores `no` for whether the evidence establishes adversary intent. A named
adversary would contradict a scored answer and would push teams toward
pattern-matching instead of reading records.

So every breadcrumb here is **unattributed**: it reads as a note left by someone
using the access, never as the calling card of a named side. `ridge/breadcrumbs.py`
enforces this with a word-boundary adversary check, and there is no codename
anywhere in the fixture. If a team asks who the author was, the correct answer is
the one the closing ticket scores: the records do not establish it.

## The seven breadcrumbs

| ID | Phase | Released with | Location under `/evidence` | Points at | Cross-task | Optional |
|---|---|---|---|---|---|---|
| BC-01 | phase-1 | run start | `notes/collector-handover.txt` | `network/sensor.pcap`, `network/dns.pcap`, T02 | yes | yes |
| BC-02 | phase-1 | run start | `notes/length-is-not-identity.txt` | `server/catalog.csv`, T19 | yes | yes |
| BC-03 | phase-2 | run start | `notes/same-string.txt` | `disk/WS17-fat16.img`, `prepared/memory-processes.json`, T15 | yes | yes |
| BC-04 | phase-2 | run start | `notes/two-handles.txt` | `server/access.csv`, T08 | yes | yes |
| BC-05 | phase-3 | T11 | `notes/third-machine.txt` | `hunting/coverage.csv`, T12 | no | yes |
| BC-06 | phase-4 | T09 | `notes/supersede-note.txt` | `server/version-comparison.csv`, T09 | no | yes |
| BC-07 | phase-4 | T20 | `notes/timeline-order.txt` | `hunting/coverage.csv`, T12 | yes | yes |

Every one is optional and none is bonus. The fixture's `scoring` block says why
there is no bonus: stock CTFd challenges are locked down in this deployment
(`integrations/ctfd_silent_ridge` 403s `/api/v1/*` except the scoreboard GET),
scoring is one `Awards` row per answered question, and IRIS findings are created
from answers rather than from events. There is no surface that could carry a bonus
award and reconcile it against both systems, so no breadcrumb is scored. Do not
award one manually; a manual award cannot be reconciled and will not survive
export.

### What each one gives and withholds

Each fixture entry carries a `reveals` line and a `must_not_reveal` list. The
short version:

- **BC-01** points a team from the sensor capture to the name lookup. It names no
  workstation, address, request identifier, byte count or document version.
- **BC-02** is the strongest of them for timeline work: it says the wire record
  and the access record agree on a length and that this proves nothing, and it
  sends the team to the catalogue. It is a pointer, not the T19 answer.
- **BC-03** links the recovered cache to the process view's command-line argument
  as the same string, so T05 and T15 corroborate rather than duplicate. It does
  not give the string.
- **BC-04** is the only prose in the corpus written by someone other than exercise
  control. It is deliberately a fragment between two handles that resolve to
  nothing in any collected source, which is exactly why it cannot be turned into
  an attribution. It does not say which of the two fetches returned content.
- **BC-05** is the honest way to hand a team the unresolved lead: the same tool
  name appears on more than one machine, the coverage record is why the third
  cannot be settled. It does not name the machine, the publisher or the times.
- **BC-06** is the reasoning error the exercise turns on, stated by nobody: a
  superseding version does not un-send the earlier one. It explicitly tells the
  reader not to quote it as a finding.
- **BC-07** is a reminder about ordering across three systems and three clocks. It
  is delivered with the closing ticket and deliberately answers none of the four
  closing questions.

## How they are delivered, and why

Two mechanisms, both existing ones.

**Run-start (`initial`).** BC-01 to BC-04 are rendered by `expanded/prepare.py`
into the published evidence tree as `notes/<file>`. The whole initial tree is
mounted read-only at `/evidence` before the first ticket is claimed, so these are
visible from the start. That is correct: every phase-1 and phase-2 ticket is
unlocked at run start, so there is nothing later to protect.

**On unlock (`release`).** BC-05 to BC-07 are carried in the controller release
vault beside the follow-up evidence for their gated ticket and published by
`ridge/evidence_release.py` when that ticket is delivered — the same verified,
checksummed, fail-closed path as `identity/late-auth.csv`. Their gates are T11
(after T10), T09 (after T08) and T20 (after T07, T09, T11 and T19).

**The trap this design avoids.** `State.initialize` enqueues *every ticket with no
prerequisites* for delivery, and `transport.remote_sink` publishes a ticket's
release when the ticket is delivered. A breadcrumb hung on a root ticket would
therefore be on the mount at run start, and `notes/timeline-order.txt` would spoil
the phase it belongs to. `ridge.breadcrumbs.check_delivery` refuses any release
breadcrumb whose gate has no prerequisites, and
`BreadcrumbPublicationTimingTests` walks a real state to prove that root tickets
deliver at start and that T11 does not deliver until T10 closes.

## If a team finds them

Do not confirm a find during the run, and do not treat one as a question to be
answered. A team that raises a breadcrumb in its AAR or handover has done the
right thing twice: it read the evidence closely, and it was careful about what it
claimed from the note.

- **A team cites a breadcrumb as a finding.** Ask what in the released record
  supports the claim independently. Every breadcrumb points at a real source and
  carries no value; the value is always somewhere the note deliberately did not
  go. The note is a direction, not evidence.
- **A team names an adversary.** This is the T20-Q4 error arriving early. Let it
  stand, note it for the AAR, and point at the record that does not support the
  name rather than at the breadcrumb.
- **A team finds all seven.** Say nothing during the run. At the AAR it is worth
  one prompt: ask which of the seven they would have been willing to act on. The
  intended answer is "none on its own", which is the same discipline the closing
  ticket scores.
- **A team finds none.** Nothing to do. The exercise scores 80 answers and none
  of them depends on a breadcrumb.

## Limits worth stating plainly

- Breadcrumb files are `.txt` under `/evidence/notes/`, so they are reachable
  through the file manager and a text editor. They are **not** ingested into the
  pre-built prepared Autopsy case (`assets/autopsy-case-v2.json`), which was
  packaged before this issue and is a separate published LFS artifact. A team
  searching the case for `text:BriefSync` will not hit a breadcrumb. Rebuilding
  the case to index them is release work, not part of this issue.
- They are not indexed into Wazuh. `ridge/evidence_release.publish` only indexes
  released `.csv` files, and a note in a data view would be noise in a SIEM.
- Nothing under `facilitator/` is reachable from participant code, and nothing
  in `assets/breadcrumbs-v1.json` is a solution mapping. The fixture holds the
  text; this file holds the mapping.
