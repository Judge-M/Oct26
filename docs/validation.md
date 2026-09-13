# Validation record

Portable validation uses Windows and Python 3.12.14. The suite preserves the ten
original evidence/runtime tests and the tab-login test, and adds ten review regressions.

| Check | Executed result |
|---|---|
| 21 portable tests | Passed locally |
| Default and 120-minute schedules | Passed: rendered handouts, inject clocks/deadlines, joint report, closure and unchanged historical evidence |
| Invalid configuration | Rejected before generation |
| Canonical initial manifest and rehashed public inject tampering | Rejected by regressions |
| Release directory/log/ledger consistency | Passed mismatch and duplicate checks |
| Clock start/pause/resume and named controller decisions | Passed; UTC/elapsed mapping, restart and export tested |
| Read-only controller API and comment attribution | Passed; cells cannot write controller records |
| Cross-host hunting correlation | Passed: H101–H104 include IDP-1's H102 |
| Offline package checksums | Passed tamper regression |
| Browser exercise | Headless Edge passed five simultaneous cells, displayed T1-C1 and CTL IDs, download, isolated sign-out and refresh |
| Portable CLI rehearsal | Start/pause/resume, decision, release, verify and export passed on an isolated QA run |
| JavaScript syntax and Compose configuration | Passed locally |
| Local Docker execution | Unavailable: docker info exceeded a ten-second timeout |
| Windows/Linux CI portable suites | Passed |
| Linux CI container and offline restoration | Passed: both images saved/loaded, packaged source restored, startup with --no-build --pull never, boundary and HTTP smoke checks |

CI runs portable tests on Windows/Linux and Linux container build, read-only mounts,
image/network boundaries, shared comments, controller ledger, release, persistence,
export and reset. It also saves/loads exact images and starts the packaged controller
source with builds and pulls disabled. Image identities and package checksum are
printed in the offline-pack step and recorded in the package.

Outstanding: actual Jira import/permissions/comment export; separate participant
seats and lab firewall/TLS; clean physical offline host with preinstalled compatible
engine/Python; accessibility checks; and a timed human rehearsal. CI restoration
is not evidence that those site-specific checks passed. Controller attribution
requires named operators on access-controlled host accounts; the external ledger
is not cryptographically tamper-proof.

Executed CI evidence: [successful portable/container/offline run](https://github.com/Judge-M/Oct26/actions/runs/34732840276)
on implementation commit cd8c0a5. The package records exact image identities; the
current PR checks cover subsequent changes.
