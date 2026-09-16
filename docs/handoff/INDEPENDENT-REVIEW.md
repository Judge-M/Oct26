# Independent review of the Silent Ridge assessment

Date: **2026-09-16**
Reviewer: Agent C (`lane/review-h01`, based on `main` `370ff50`)
Scope: independently confirm or refute the P0/P1/P2 claims in
[ASSESSMENT.md](ASSESSMENT.md) and [../expanded-validation.md](../expanded-validation.md)
against the actual code, configuration, tests, workflows and manifests in this working
copy. This review is read-only except for this file; no other file was modified before
this document was written.

## Method and environment

- Read the repository at `370ff50` (working tree clean). Read code, Compose, workflows,
  manifests and tests directly; ran the full test suite; ran `ridge.cli` against the
  shipped default configuration to observe behaviour.
- Environment: Windows, Python 3.12.4. Docker, Linux/WSL, Java/Autopsy, AWS and Hyper-V
  are **not available** here, so no container, hypervisor or cloud claim was executed.
- Git LFS assets were not re-pulled (per instruction). Large-asset bytes were not
  re-verified; only their manifests were read.

### Baseline test state (executed)

```text
python -m unittest discover -s tests
Ran 73 tests in 61.544s
OK
```

`expanded-validation.md:9-11` records **42 tests** and `ASSESSMENT.md:5` records a prior
**71 tests**. Neither matches the current tree. The 73 passing tests are the baseline
used below.

---

## Verified / refuted / environment-blocked summary

| # | Claim (source) | Verdict | Key evidence |
|---|---|---|---|
| P0-1 | No deployment orchestrator | **CONFIRMED** | `ridge/cli.py:13-33` |
| P0-2 | `expanded/config.json` not runnable | **CONFIRMED (executed)** | `ridge/preflight.py:24-25`; command output below |
| P0-3 | Autopsy path contracts disagree | **CONFIRMED** | `expanded/author.py:22,149`; `ridge/preflight.py:47-51`; `expanded/prepare.py` (no match); `docs/desktop-image.md:49,51` |
| P0-4 | No end-to-end follow-up delivery contract | **CONFIRMED** | `ridge/evidence_release.py:68`; `deployment/expanded/desktop/configure-image.sh:87-88` |
| P0-5 | Central provisioning / Wazuh incomplete | **CONFIRMED** | `deployment/expanded/compose.central.yaml:4-16`; no Wazuh Compose file exists |
| P0-6 | Ten-team capacity arithmetic | **CONFIRMED** | `expanded/author.py:157`; `README.md:31` |
| P1-1 | Single active controller/site | **CONFIRMED (design)** | `ridge/state.py` central SQLite + outbox |
| P1-2 | Incomplete recovery | **CONFIRMED** | `ridge/export_run.py:23-35`; `ridge/storage.py:32` |
| P1-3 | Identity portability | **CONFIRMED** | `ridge/preflight.py:22-25` |
| P1-4 | Run isolation | **CONFIRMED** | `compose.central.yaml:1,83-90` |
| P1-5 | Resource capacity | **CONFIRMED** | `assets/desktop-v1.json:43-46` |
| P1-6 | Storage lifecycle | **CONFIRMED** | `ridge/storage.py:29-41` |
| P1-7 | Release completeness | **CONFIRMED** | `ridge/distribution.py:17,88`; `ridge/bundle.py:19-20`; `publish.yml:36` |
| P1-8 | AWS readiness and cost | **CONFIRMED** | `assets/desktop-v1.json:41`; `docs/desktop-image.md:29-31` |
| P2-1 | `versions.json` still names Cutter 2.3.4 | **CONFIRMED** | `deployment/expanded/versions.json:8` vs `assets/desktop-v1.json:56` |
| P2-2 | Legacy `install.sh` vs `configure-image.sh` | **CONFIRMED** | both files present and divergent |
| P2-3 | Docs/manifests describe missing artifacts | **CONFIRMED** | `expanded/manifest.example.json:7`; `README.md:5` |
| — | README relative links are broken | **REFUTED** | every relative markdown link resolves |
| — | GitHub "no Releases" | **UNVERIFIED** | no network; local `git tag` is empty |
| — | CI / prior 71-test claim | **ENVIRONMENT-BLOCKED** | no CI access |

---

## P0 — verified in detail

### P0-1 — No deployment orchestrator (CONFIRMED)

`ridge/cli.py:13-33` defines only core-state subcommands: `init`, `mode`, `recover`,
`export`, `status`, `diagnostics`, `preflight`, `provision`, `migrate`, `cancel-export`,
`announce`. There is no host, network, certificate, application-account, desktop or AWS
creation path. `ridge/desktop_image.py` only reassembles the published QCOW2
(`desktop_image.py:12-47`); `ridge/distribution.py` only packs/fetches a release
(`distribution.py:47,126`). None is a one-command setup. The claim is accurate.

### P0-2 — Default configuration is not runnable (CONFIRMED, executed)

`expanded/config.json:6-12` contains five teams with `iris: "101"…` and `ctfd: 1…` and
**no** `iris_login` or `ctfd_name`; `:14-18` use documentation IPs (`192.0.2.x`).
`ridge/preflight.py:24-25` raises when either field is missing. Executed against the
shipped config after initializing state from generated content:

```text
python -m ridge.cli --state <tmp>\state.sqlite init --config expanded/config.json --content <tmp>\tickets.json
python -m ridge.cli --state <tmp>\state.sqlite preflight --config expanded/config.json
  File "...\ridge\preflight.py", line 25, in check
    raise ValueError('Record expected iris_login and ctfd_name for every team')
ValueError: Record expected iris_login and ctfd_name for every team
```

The documented remedy (`README.md:27`, `docs/expanded-deployment.md:51-57`) is manual
editing of IDs and names. The claim is accurate.

### P0-3 — Autopsy path contracts disagree (CONFIRMED)

- `expanded/author.py:22,25,28,37,52,55,58,61` set the Autopsy evidence string to
  `autopsy/WS17/WS17.aut`; `:149` turns that into question evidence
  `/evidence/autopsy/WS17/WS17.aut`.
- `ridge/preflight.py:47-51` requires every question path beginning `/evidence/` to be a
  real file under `RIDGE_EVIDENCE_PUBLIC`, unless it is a delayed release file.
- `expanded/prepare.py` produces `disk/WS17-fat16.img`, `prepared/*.json`, etc., and has
  **no** `autopsy` reference at all (verified: `rg -n autopsy expanded/prepare.py` → no
  matches, exit 1). The `autopsy/WS17/WS17.aut` directory is therefore never created on
  the controller evidence mount, so preflight fails for all eight Autopsy tickets.
- The desktop instead opens `~/Cases/WS17/WS17.aut` (`docs/desktop-image.md:49`) and
  keeps the closed original at `/opt/silent-ridge/prepared-case/WS17`
  (`docs/desktop-image.md:51`; `deployment/expanded/desktop/seal-image.sh:5`).

This is a static, reproducible blocker. The claim is accurate; the fix belongs to A05
(separate an evidence reference from a local tool entrypoint).

### P0-4 — Follow-up evidence has no desktop delivery contract (CONFIRMED)

`ridge/evidence_release.py:68` publishes released files into the controller's
`RIDGE_EVIDENCE_PUBLIC`. The desktop image bind-mounts its **own baked**
`/opt/silent-ridge/evidence` onto `/evidence`
(`deployment/expanded/desktop/configure-image.sh:87-91`). No supplied Compose service,
mount or replication step connects the controller share to the desktop share. T09/T19
require newly released files and T07/T11 require indexed follow-ups
(`ridge/scenario.py:4-9`). The claim is accurate.

### P0-5 — Central provisioning and Wazuh incomplete (CONFIRMED)

- `deployment/expanded/compose.central.yaml:4-16,38,43,48-50,66,68,74` require roughly
  fifteen private variables, identities and preloaded images before the stack can start.
- No Wazuh Compose/certificate/configuration file is vendored: the only Compose files are
  `compose.central.yaml`, `compose.guacamole.yaml`, `compose.integration.yaml`
  (`deployment/expanded/`). `docs/expanded-deployment.md:42-47,66-67` states the Wazuh
  stack "must be included from the pinned upstream artifact" and that the supplied
  deployment "has not yet been run".
- `compose.integration.yaml:23` requires an HTTPS `WAZUH_INDEXER_URL`, but the service
  mounts only `ridge_iris`, `ridge_ctfd` and `wazuh_index` secrets (`:25`) — there is no
  CA/`SSL_CERT_FILE` mount, despite `docs/expanded-deployment.md:44-46` requiring the
  local CA to be trusted.
- CI certifies only the CTFd adapter (`.github/workflows/validate.yml:19-26`); IRIS,
  Wazuh and Guacamole have no live test.

The claim is accurate.

### P0-6 — Ten-team capacity arithmetic (CONFIRMED)

`expanded/author.py:157` sets `estimate_minutes=65` for each of the twenty tickets
defined at `:15-76`. 20 × 65 = **1,300 team-minutes**; ÷ 10 teams = **130 min/team**;
÷ 5 teams = **260 min/team** (the figure quoted at `README.md:31`). Four hours × 10
teams = **2,400 team-minutes**. The arithmetic in `ASSESSMENT.md:64` is correct. This is
a planning estimate only, as the source itself states (`author.py:158`).

---

## P1 — verified in detail

- **Single active controller/site (CONFIRMED, design).** `ridge/state.py` holds run,
  teams, tickets, questions, answers, audit, outbox and delivery dependencies in one
  SQLite database with leases (`state.py:96-141,338-395`). `export_run.py` freezes the
  controller during export. This is a central authority with no fencing/second-site
  coordination, exactly as stated.
- **Incomplete recovery (CONFIRMED).** `ridge/export_run.py:23-35` writes
  `integration.json`, `iris.json`, `ctfd.json` only. `ridge/storage.py:29-41`
  (`verified_export`) explicitly accepts only those three names. Native application
  databases, Guacamole state, Wazuh snapshots, desktop workspaces and deploy secrets are
  not included.
- **Identity portability (CONFIRMED).** Teams carry numeric `iris`/`ctfd` IDs compared
  against live applications (`ridge/preflight.py:22-25`); a full restore that recreates
  accounts with new IDs would break the mapping.
- **Run isolation (CONFIRMED).** `compose.central.yaml:1` hardcodes
  `name: silent-ridge-central`; volumes at `:83-90` are unscoped. `compose.integration.yaml:1`
  and `compose.guacamole.yaml:1` likewise hardcode project names. Constant names allow a
  later `up` to reuse prior volumes.
- **Resource capacity (CONFIRMED).** `assets/desktop-v1.json:43-46` records the only
  exercised allocation: 4 vCPU / 8192 MiB. Ten such desktops are 80 GiB of guest RAM
  before central services.
- **Storage lifecycle (CONFIRMED).** `ridge/storage.py:29-41` prunes only completed
  three-system JSON exports; it does not manage VM disks, logs, native DB volumes,
  snapshots or release caches.
- **Release completeness (CONFIRMED).** `ridge/distribution.py:17` restricts image
  locking to `integration, iris, ctfd`; `ridge/bundle.py:19-20` expects eleven images
  including Wazuh, Guacamole, MariaDB, Redis, RabbitMQ and Postgres. The publish workflow
  builds only three images (`.github/workflows/publish.yml:36`). `distribution.py:88`
  hardcodes `event_ready=False` and `complete_offline_bundle=False`. `git tag` is empty,
  so no release exists locally.
- **AWS readiness and cost (CONFIRMED).** `assets/desktop-v1.json:41` records
  `aws_import_validated: false`; `docs/desktop-image.md:29-31` states the QCOW2 is not an
  AMI and Hyper-V/AWS boot are unvalidated.

## P2 — verified in detail

- `deployment/expanded/versions.json:8` still pins **Cutter 2.3.4**, while
  `assets/desktop-v1.json:56` and `docs/desktop-image.md:3` deliver **2.5.0**.
- Both `deployment/expanded/desktop/install.sh` (legacy: writes VNC URLs into desktop
  shortcuts, no credential gate) and `configure-image.sh` (current: `open-service.py`,
  `open-autopsy.sh`, `ConditionPathExists=/etc/silent-ridge/vnc-password`) exist. The
  legacy file can still overwrite the tested service.
- `expanded/manifest.example.json:7` still lists "ready-to-open Autopsy cases", "native
  Windows event logs" and "validated Linux desktop template" as missing even though the
  corresponding manifests exist (`assets/autopsy-case-v2.json`,
  `assets/native-windows-v1/archive.json`, `assets/desktop-v1.json`).

---

## Findings the assessment missed

1. **The handoff documents are stale relative to the branch they ship on.**
   `ASSESSMENT.md:11-26` and `README.md:18` describe PR #6 as **open** and list
   "required updates before merge", but PR #6 is already merged at the working-copy base
   (`370ff50 Merge pull request #6 from stoptalkingishh/docs/nice-learning-objectives`).
   `ASSESSMENT.md:5` says main was reviewed at `305c257`; the actual base is `370ff50`.
   Consequently the pre-merge corrections were never applied: `docs/learning-objectives.md:189`
   still claims an "exactly-once outbox", and `:224` still groups `T15`, `T16` as
   "Autopsy — prepared memory tree/connections", the exact conflation the assessment
   flagged. Any future agent following the handoff will look for a PR that is already
   landed.
2. **Test-count drift is unresolved.** The authoritative record
   (`expanded-validation.md:9-11`) says 42 tests; `ASSESSMENT.md:5` says 71; the tree has
   73. The assessment's own "prior validation" figure cannot be reproduced.
3. **`expanded/tickets.json` is not committed.** `README.md:23` and the CLI default
   (`ridge/cli.py:15`) reference it, but it is generated by `expanded/author.py`
   (`author.py:162-163`). A user who runs `ridge.cli init` before `author.py` gets a
   missing-file error rather than a guided message. Minor usability gap.
4. **README relative links are intact (refutes a plausible concern).** A recursive check
   of every relative markdown link in the tree found no broken target. The
   `profiles/event-*.json` paths in `README.md:26-40` do not exist, but `README.md:22`
   explicitly labels that block a "proposed interface, not existing functionality", so it
   is not a defect.

## Unverified or environment-blocked

- **GitHub Releases / package access.** No network and no local tags; `ASSESSMENT.md:5`
  ("GitHub returned no Releases") is plausible but not verified here.
- **CI history and the 71-test prior run.** No CI access from this host.
- **Docker, Linux/WSL, Hyper-V, Java/Autopsy, AWS.** Not available; no live container,
  hypervisor, image-import or teardown check was executed.
- **Large LFS asset integrity.** Not re-pulled; manifests were read but the 5 GB desktop
  disk and native archive were not hashed again.

## Conclusion

Every P0 and P1 claim in `ASSESSMENT.md` is confirmed against the tree; the P2 items are
also confirmed. The two material gaps are (a) the stale "open PR #6" state, which makes
part of the handoff misleading, and (b) the un-reproducible test-count record. The
Autopsy path, runnable-config and capacity findings are the highest-value blockers and
are all independently reproduced above.
