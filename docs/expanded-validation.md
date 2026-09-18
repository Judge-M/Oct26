# Expanded acceptance record

## Baseline and executed local checks

Current upstream main was rechecked as
`b4def5d4b65395aa0f441e785f225e053eec10d9` on 2026-09-14. No repository AGENTS.md
was present in the source archive. All 25 baseline tests passed before edits.

The final local suite passed **42 tests in 20.958 seconds** on Windows using the
bundled Python 3.12.14 / SQLite 3.53.1 runtime. This comprises 25 retained baseline tests and 17 new
tests, without double-counting an imported test class. Python compilation and
`git diff --check` passed. The initial sandbox execution failed on temporary-file
permissions; the recorded passing tests ran with normal process permissions.

Rechecked 2026-09-16 on branch `lane/wave0` (Windows, Python 3.12.4): the current
suite `python -m unittest discover -s tests` passes **73 tests in 61.6 seconds**
(`OK`). This supersedes the 42-test figure above for the current tree; the earlier
count is retained as the historical baseline.

Both participant Jinja templates were rendered locally with Jinja2 3.1.6; their
generated JavaScript passed Node syntax checks. PyYAML 6.0.2 parsed the root and
candidate Compose/workflow files. These are syntax/render checks, not browser
usability or Docker Compose execution. Docker build-context exclusions were
updated to include the new adapters and integration modules while excluding run
state and generated artifacts.

New tests cover claim races (same ticket and same team), transfer without reset,
global completion/history, follow-up release, duplicate answers, incorrect and
unauthorized submissions, cross-application identity/role checks through a real
local HTTP server, restart/lost-response recovery with a simulated sink, pause and
clock progression, public announcements, exports, content/help presence, evidence
coherence, artifact tampering/path escape, configurable Guacamole concurrency,
duplicate SQL columns and stale image-source detection.

An independent pyfatfs 1.1.0 read-only check opened the generated FAT16 image,
listed README.TXT, PLANV3.TXT and HISTORY.TXT, and read the expected fictional
LANTERN v3 content. The deleted cache is absent from the normal directory listing.
The parser dependency needed setuptools 80.9.0; this was installed only under the
ignored local test directory. This check is not an Autopsy recovery test.

## Resource observations

The deliverable preparation-fixture release contains 31 files totaling 8,566,037
bytes, including an 8,388,608-byte FAT16 image. This measures only the small
generated fixture set, not final evidence, cases, VM images or service capacity.
No host CPU/RAM/VM allocation is committed. Use `deployment/expanded/measure.py`
on the Linux rehearsal host to collect actual container CPU, memory and I/O
samples for named exercise containers during idle, concurrent analysis and
outage/recovery phases. Measure guest case-copy/launch/search time and disk growth
separately. No representative beginner timing has been recorded.

## CI status

The revised workflow runs portable tests on Windows and Linux, builds the actual
extended CTFd image and exercises its receipt/authentication/API restrictions,
and builds the harmless Linux binary alongside preparation fixtures. It replaces
the obsolete reporting-portal container job. CI has not run: the source branch has
not been published. Results must be recorded after the draft branch run; they are
not assumed from local tests.

## Acceptance status

| Requirement | Status and evidence |
|---|---|
| Adjustable teams/VMs and explicit sharing | Configuration and SQL generator tested; actual Guacamole/desktop sessions untested |
| One active ticket/one owner; simultaneous claims | Implemented and local race tests passed |
| Transfer with retained progress and original-team points | Implemented and tested in core |
| Current-ticket question gating | Core HTTP boundary tested; actual CTFd route checks pending CI |
| Exactly-once points/comments/tasks | Core outbox retry test passed against simulated sink; actual application receipts need runtime checks |
| Findings and global closure | Implemented; local core tests passed; live IRIS posting/closure not tested |
| Shared history and no report/approval gate | Implemented in replacement workflow |
| Offline central stack and desktop template | Candidate configurations/scripts supplied; no deployment executed locally |
| Autopsy disk/log/memory workflows | Native FAT fixture generated; native Windows reconstruction present and checksummed (`assets/native-windows-v1/manifest.json`); prepared Autopsy case present (`assets/autopsy-case-v2.json`, reopened with 90 indexed documents); per-question navigation on the installed tools unverified |
| Harmless binary/Cutter | Source supplied; Linux build delegated to CI; Cutter UI unverified |
| Wazuh historical correlation | Replay/indexing/release code supplied; actual index/view/permissions unverified |
| Protected future material | Separate source tree and release code; generated initial visibility tested; deployed permissions unverified |
| Export/reset/recovery | Core export/recovery tested; combined application export and full clean-volume reset unexecuted |
| Complete offline bundle consistency | Verifier/assembler supplied and mismatch logic tested; no complete bundle exists |
| At least 240 minutes of meaningful activity | 260-minute five-team arithmetic estimate only; content/native artifacts and beginner rehearsal required |
| Exact installed-tool guidance | Authored outlines only; navigation and walkthroughs not yet verified on installed tools |

## Prior review findings disposition

| Baseline finding | Disposition |
|---|---|
| Clock follows latest ledger event | Retired UI; replacement clock uses current pause-aware elapsed time, with a regression test |
| Duplicate SQL labels lose values | Retained helper now rejects duplicate names with an explicit alias error; test passed |
| Old image paired with new source | Retained packer checks image contents; expanded assembler checks all extension sources and re-saves exact image identities |
| Handouts omitted from downloads | Old UI retired; desktop file manager provides released files. Rendered-guide packaging is still outstanding |
| Entire ledger claimed public | Controller visibility documentation corrected |
| Deadline changes in private notes | Replacement persistent public announcement command/UI implemented and tested |
| Manual refresh | Replacement polls status and updates/reloads safely between answer edits; live UI rehearsal outstanding |
| Lost report drafts | Mandatory report composer retired; no retained manual reporting workflow |
| Long single-page workflow | Separate queue, questions/help and native findings navigation; beginner usability unverified |
| Unexplained SQL prerequisite | Retired participant SQL interface; approved-tool guidance authored |
| Conflicting historical validation counts | This record is authoritative; old validation documents are historical |

## Remaining work and smallest environment need

Do not declare the exercise complete. A Linux preparation/rehearsal host is needed
to run the actual IRIS/Wazuh/Guacamole stack, boot and validate the desktop VM,
open the published prepared Autopsy case on the installed tools, and validate
offline restore and resource usage. The native Windows-log and memory
reconstruction and the prepared case are already published and checksummed; what
remains is validation on the installed tools, not artifact creation. This machine
has no Docker, no installed WSL distribution, and no Java/Autopsy tools. GitHub CI
can cover some container/build checks but cannot substitute for the desktop and
beginner rehearsal. The artifact store provider and final hardware remain open
configuration choices, not invented commitments.
