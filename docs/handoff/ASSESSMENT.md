# Repository assessment and PR relevance

## Evidence boundary

Reviewed current main `305c257`, repository code/configuration/workflows, artifact manifests, and GitHub PR patches/API state. Prior completed validation: 71 tests, Windows/Linux CI, actual CTFd adapter smoke, prepared-case GUI/search, Cutter analysis, desktop offline boot, and published LFS availability. This review did not rerun multi-gigabyte builds or the full test suite. No full deployed event or ten-team rehearsal is claimed. GitHub returned **no Releases** at review time. Package existence/access was not independently established; the tag publishing workflow has not been demonstrated as a complete event release.

The untracked `deployment/expanded/New-BuildVMs.ps1` in this local workspace is an abandoned build experiment, not part of merged main. Do not silently include it in future work.

## Open PRs

### #6 — Document NICE Framework learning objectives and facilitation mechanisms

[PR](https://github.com/Judge-M/Oct26/pull/6), reviewed head `9dfa3c7e3c43037a276035b2bcfd9a46d8df4f50`. Two files: README link and `docs/learning-objectives.md`.

**Relevance: high for learning design; low for deployment completion. Recommendation: retain, update, then merge separately.** Its objective/mechanism/evidence structure is useful for rehearsal and participant guidance. It does not alter runtime code.

Required updates before merge:

1. Remove the assertion that native captures and prepared cases are still missing. Link the current native, desktop and Autopsy manifests; distinguish created artifacts from incomplete whole-event acceptance.
2. Correct LO1: current T13/T14 use actual native acquisition UTC and must not receive the historical 120-second correction. Preserve the historical correction exercise in the appropriate other tickets.
3. Correct the T15/T16 crosswalk: T15 is memory-derived process evidence; T16 is the acquired live connection snapshot, **not a validated memory connection result**.
4. Replace blanket “exactly-once” wording with the actual guarantee: durable retries plus transactional application receipts, subject to tested adapter behavior. Live IRIS and cross-system outage acceptance remain gates.
5. Separate practice from assessment: read-only use of supplied originals does not itself demonstrate acquiring a forensic duplicate. Free walkthroughs and public answers support coached practice, not proof of unaided mastery.
6. Update ten-team workload assumptions. Verify NICE IDs/task statements against a pinned official component release before claiming a formal mapping; this review did not independently validate every NIST mapping.

The PR body contains obsolete baseline language; rewrite it around the final updated document. GitHub's mergeability was `unknown` during this read; no clean-merge claim is made.

### #7 — Document President's Cup augmentation options and tradeoffs

[PR](https://github.com/Judge-M/Oct26/pull/7), reviewed head `8583102b44679642e12fd2b9d1cd4709dfad7255`. One new proposal document; no imported challenge content.

**Relevance: optional future curriculum; low for the current critical path. Recommendation: defer until rehearsal identifies a specific learning gap.** Retaining the proposal as a clearly nonbinding backlog document is reasonable; do not treat its Phase 1 as required event work.

Before eventual merge/import: align its description of Wazuh with the pinned deployed indexer rather than implying generic Elastic compatibility; update Cutter 2.3.4 to the delivered 2.5.0; distinguish available tools from demonstrated whole-stack operation; repair its dependency on the learning-objectives document if #6 has not landed. Verify each proposed source's exact commit, license and bundled assets before importing anything. Its licensing table and effort estimates were not independently certified here. Avoid new EDR/LOTL execution stations, Velociraptor, T-Pot, or a second scoring server merely to fill time. They enlarge deployment and maintenance scope.

## Readiness matrix

| Area | Present and supported by evidence | Missing acceptance / work |
|---|---|---|
| Core state | SQLite transactions, ownership generations, explicit provisioning, pause, outbox leases, ordered dependencies, export barriers, diagnostics; unit/race tests | Live multi-service fault injection, operator controls and deployment lifecycle |
| CTFd | Transactional credit plugin and actual container smoke in CI | Automated users/teams/settings; full participant sessions and scoreboard reconciliation |
| IRIS | ORM adapter with transactional receipt/task/comment operations | Built/live integration test, initialization and account/case/status provisioning, permission verification |
| Content | Generated historical evidence, native Sandbox memory/EVTX, neutral records and provenance, preserved historical timeline | Every question navigated and answered against the exact installed release; ten-team workload validation |
| Desktop | 5,228,265,472-byte QCOW2 in six LFS parts; 30-GiB virtual disk; offline QEMU boot; Autopsy and Cutter checks | Hyper-V and AWS boot, provisioning, Guacamole sessions, per-team copies and evidence updates |
| Wazuh | Stable-ID bulk indexing and historical record generation | Complete vendored stack/config/certificates, account/role/view creation, TLS wiring and actual queries |
| Distribution | Git/LFS content, checked assembly, candidate GHCR/release workflow | Published immutable release and all dependency images; complete offline manifest and installable product |
| Recovery | Core and three-system logical export, backup-verified export pruning | Native database/volume/desktop backups, validated restore, cross-provider fencing and cost-aware teardown |
| Operations | CLI, diagnostics and container measurement helper | One-command orchestration, capacity measurements, actionable status, run-scoped cleanup and rehearsal |

## Architectural blockers, by severity

### P0 — blockers to the promised event experience

**1. There is no deployment orchestrator.** `ridge/cli.py` manages core state; it does not create application accounts, hosts, networks, certificates, desktops or AWS resources. `ridge/distribution.py` downloads files; `ridge/desktop_image.py` joins a disk. None is a one-command setup.

**2. The default configuration is not runnable.** `expanded/config.json` contains five teams, placeholder IRIS/CTFd IDs and documentation IPs. It omits `iris_login` and `ctfd_name`, which `ridge/preflight.py` requires. Generate actual mappings after account provisioning; do not teach users to hand-edit IDs.

**3. Autopsy path contracts disagree.** `expanded/author.py` puts `/evidence/autopsy/WS17/WS17.aut` in Autopsy question evidence. `ridge/preflight.py` requires initial question paths to exist on the controller evidence mount. `expanded/prepare.py` does not create that case there. The desktop uses `~/Cases/WS17/WS17.aut` and `/opt/silent-ridge/prepared-case/WS17`. This is a static, reproducible preflight blocker, not a reason to put a writable case on a shared read-only evidence mount. Separate evidence references from local tool entrypoints and validate each appropriately.

**4. Follow-up evidence has no end-to-end desktop delivery contract.** `ridge/evidence_release.py` publishes into the controller's `RIDGE_EVIDENCE_PUBLIC`; the desktop binds its own baked `/opt/silent-ridge/evidence` to `/evidence`. No supplied mount/replication step connects them. T09/T19 require newly released files, and T07/T11 require indexed follow-ups. Implement and test delivery, acknowledgments, reconnection and visibility before declaring tasks usable. A pre-ingested Autopsy case will not automatically index arbitrary newly copied files; explicitly decide which follow-ups use file manager/Wazuh and keep Autopsy immutable unless incremental ingest is designed and tested.

**5. Central provisioning and Wazuh are incomplete.** Compose requires many private variables, identities and preloaded images. The full Wazuh stack/certificates are not vendored. The integration Compose file lacks an explicit local-CA mount/trust setting despite requiring HTTPS. CTFd smoke does not certify IRIS, Wazuh or Guacamole. Replace documented manual bootstrap steps with idempotent automation and a live vertical slice.

**6. Ten-team educational capacity is unsupported.** Twenty tickets × 65 estimated team-minutes = 1,300. Dividing by ten gives about **130 estimated minutes/team**, not 260. Dependencies, shared global completion and free answer walkthroughs can further affect useful work. If four hours of meaningful activity per team remains required, the rough floor is 2,400 team-minutes, but measured scheduling and beginner results are decisive. Preserve the cooperative global ownership model; do not silently duplicate scoreable tickets per team to mask the gap.

### P1 — required before event approval

- **Single active controller/site:** SQLite and the outbox are a central authority. Service errors are caught and retried, but host loss still stops progress. Local↔AWS switching needs a coherent backup, source fencing and destination health checks; never run two writable copies of a run. Do not promise zero data loss for a cold backup.
- **Incomplete recovery:** `ridge.export_run` is an audit export, not a full disaster recovery image. It excludes native application databases, Guacamole state, Wazuh snapshots, desktop workspaces and deploy secrets. A JSON export alone cannot support switching providers.
- **Identity portability:** imported application IDs and receipts must survive full restores. Recreating teams with new numeric IDs against old core state breaks mappings and reconciliation. Back up and restore the stack coherently, or implement a separately tested remapping migration.
- **Run isolation:** constant Compose project names/named volumes can accidentally reuse prior state. Supply event-scoped project/volume/network names and maintain an ownership inventory. `up` retries must not create another run or overwrite the old one.
- **Resource capacity:** the only desktop allocation exercised was 4 vCPU/8 GiB. Ten at that allocation already require 80 GiB guest RAM before central services and host overhead. This is a planning calculation, not a measured minimum. The present 32-GiB computer is a development host, not evidence of ten-team capacity. Measure down-sizing or select larger/distributed hosts.
- **Storage lifecycle:** `ridge.storage` safely prunes completed three-system JSON exports only. It does not manage VM disks, logs, native DB volumes, snapshots, large release caches or aborted staging. Add measured reserves, rotation and backup-aware run cleanup.
- **Release completeness:** no GitHub Release exists yet; custom images and all upstream dependencies need immutable locks, offline saves, trusted manifests and a successful cold install. `ridge.bundle` and `ridge.distribution` use different inventories/image reference conventions; join them deliberately.
- **AWS readiness and cost:** the QCOW2 is not an AMI. Prepare and test import before event day. Stopping EC2 does not remove EBS/IP/storage costs. Teardown must inventory retained billable resources and distinguish a warm backup from a cold archived backup. [AWS image import formats](https://docs.aws.amazon.com/vm-import/latest/userguide/vmimport-differences.html), [AWS instance lifecycle billing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html).

### P2 — completion and usability

- README, `docs/expanded-validation.md`, deployment introduction and `expanded/manifest.example.json` still describe missing artifacts or no WSL/toolchain. `versions.json` still names Cutter 2.3.4. Replace historical assertions with dated generated acceptance records.
- Consolidate the legacy `desktop/install.sh` and actual `configure-image.sh` path; ensure users cannot accidentally replace the tested service with an older template.
- Prefer focused lifecycle modules with typed configuration and readable error messages; do not spend the readiness budget on wholesale Python style rewrites. Existing bounded transport timeouts, per-ticket retries and exception boundaries are useful foundations.
- An HTTP `/health` response or running process is not enough. Report readiness by application, desktop, evidence delivery and backup state; distinguish degraded synchronization from total service death.

## Scope deliberately excluded

No new learning platform, Kubernetes, active-active databases, new Windows host-memory acquisition, mandatory malware execution, or broad library modernization. Native evidence already exists; rebuild it only for a demonstrated content defect. Future generated artifacts remain publishable alongside source with provenance; deployment secrets and real participant state remain private.
