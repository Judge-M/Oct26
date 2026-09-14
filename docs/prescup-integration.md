# President's Cup content: augmentation proposal

**Status:** proposal for review — no content has been imported.
**Source:** <https://github.com/cisagov/prescup-challenges> (CISA / CMU SEI, MIT / CC0 / Apache-2.0 / MIT(SEI) per directory).
**Goal:** decide what, if anything, to pull into Silent Ridge while keeping the exercise
lightweight and offline.

This document inventories the reusable President's Cup content, maps it to the five
Silent Ridge cells and the learning objectives in `docs/learning-objectives.md`,
and estimates the software, hardware, cost and effort of each option. Everything
below is a planning estimate, not a commitment.

## 1. Bottom line

Most of the catalog is either **heavy** (hosted multi-VM labs whose environments are
not in the repository) or **offensive** (web and binary exploitation). For a lightweight
CTF the value sits in three layers:

1. **Technique and scenario harvesting** from the skill labs, folded into Silent Ridge
   injects and worksheets. Near-zero infrastructure.
2. **Two self-contained Python scenarios** (an EDR hash-monitor and a LOTL log-injection
   pair) vendored as optional offline stations. Python standard library only.
3. **An optional Docker "challenge annex"** using one to three of the `conversions/`
   challenges. Moderate infrastructure.

The `conversions/` directory is the single most important find: it is the only content
that runs as shipped, is containerized, and is explicitly written to be adapted.

## 2. Licensing guardrails

The repository is **not uniformly MIT**. The top-level `LICENSE.md` concatenates
per-season terms:

| Source directory | License | Usable |
|---|---|---|
| `skilling-continuation-labs/` | MIT | Yes; keep notice |
| `pc7/`, `conversions/` | CC0 (US government) + contractor grant + Apache-2.0 | Yes; keep notice |
| `pc1`–`pc4`, `pc6`, `pc6-round1` | MIT (SEI) — MIT-style but custom, with third-party clauses | Yes; keep notices |
| `pc5` | CC BY-NC 4.0 (non-commercial) | Only if the CTF is non-commercial |

Requirements if we import anything: retain the copyright and permission notice, carry
third-party asset terms (fonts, Bootstrap, jQuery, and so on), and record provenance.
Do not import `pc5` content if the event could ever be commercial.

## 3. Inventory and fit

### Group A — converted, containerized challenges (`conversions/`, 12 total)

These ship with a `docker-compose.yml` (CTF-NG `x-challenge` block), source, and a
solution. They are self-contained and reproducible.

| Challenge | Type | Cell | Fit | Infrastructure to run |
|---|---|---|---|---|
| Ransomware Rhapsody (`c21`) | Ransomware IR / forensics | Endpoint / Response | High | One Ubuntu container |
| Throw Me A Bone (`c02`) | Vulnerability management + AD password audit | Server / Vulnerability | High | Six servers + scanner + Kali (heavy) |
| Let Loose the Logs of War (`c05`) | Log analysis | Hunting / Server | Med-High | One container |
| Mindhunter (`c47`) | Forensics | Endpoint | Med | One container |
| Weak Web Warnings (`c37`) | Web exploitation | — | Low (offensive) | One web + Kali |
| Shop Smart (`c03`) | OWASP exploitation | — | Low (offensive) | One web + Kali |
| They All Float Down Here (`c04`) | Floating-point coding puzzle | — | None | One container |
| Triple Lindy (`c01`), Finsta (`c18`), va_list (`c34`), Kessel Run (`c41`), Crucible (`c45`) | Mixed (OSINT / binary) | — | Low-Med | Varies |

### Group B — skill labs (`skilling-continuation-labs/`, 19 total)

Most are documentation plus a solution; the environments are hosted, not shipped.
Only a few include reusable scripts.

| Lab | Ships in repo | Cell | Fit | Infrastructure if run for real |
|---|---|---|---|---|
| Living Off the Land | `httpListener.py`, `logInjection.sh`, `mini_challenge.py`, systemd units | Hunting / Network | High | auditd + pwsh (light) |
| Automated Defenses | `EDR-Files.zip` (`file_monitor.py`, `encryptor.py`), `emailer.sh` | Endpoint / Response | High | Standard-library Python (none) |
| Incident Response with Velociraptor | `windows10-baseline.zip`, `ubuntu-baseline.zip`, `grading.py` | Endpoint | High | Velociraptor server + clients |
| Detection Rules in Logging Made Easy | docs only | Hunting / Server | Med-High | Elastic / LME |
| Log Management using Logging Made Easy | `fresh-os-services.txt` | Server / Hunting | Med-High | Elastic / LME |
| DNS and Name-based Security Solutions | docs only | Network | Med | Pi-hole, Postfix, pfSense, Kali |
| Phishing Mitigation with MFA | docs only | Identity | Med | Web app + mail server |
| fast-flux, weaponized-archive, xz-utils, secure-programming, web pentest, SCADA/Modbus, Kubernetes, network-segmentation | docs (some include sample malware or tarballs) | — | Low / None | Heavy, offensive, or risky |

### Group C — platform (`conversions/challenge-server/`)

A complete self-contained challenge host: Flask plus flask-executor, CoreDNS 1.14.1,
`nmap`, `dnsutils` and `pythonping`, and a YAML grading configuration supporting button,
cron and text modes, tokens from environment or file, points, attempt limits and rate
limits, on `internal: true` networks. Genuinely reusable, but adopting it is a platform
decision rather than a content addition.

## 4. Software requirements

| Layer | Baseline (today) | Added |
|---|---|---|
| Tier 1 — offline skill stations | Python 3.12 (standard library), Docker, nginx, SQLite | Nothing new |
| Tier 2 — challenge annex | Docker Engine + Compose v2 | Challenge base images (`debian:bullseye`, `python:latest`, `alpine`); CTF-NG base adds Flask, flask-executor, PyYAML, requests, pythonping, nmap, dnsutils, CoreDNS |
| Tier 3 — full labs | — | Elasticsearch, Kibana, ElastAlert, Wazuh, Fleet, Velociraptor server, pfSense, Pi-hole, Postfix, webmin, T-Pot, Kali, `pwsh`, auditd, Suricata |
| Participant tooling | Browser, Wireshark, SQLite viewer, text editor | Optional: hashcat / John, SleuthKit, binwalk, foremost, scapy, CyberChef, nmap |

## 5. Hardware requirements

| Layer | CPU | RAM | Disk | Notes |
|---|---|---|---|---|
| Baseline Silent Ridge | 2 vCPU | 4 GB | 2 GB | per current README; one browser per analyst |
| Tier 1 | — | +0.5 GB | <100 MB | negligible |
| Tier 2 (1–3 challenges + server) | 2–4 vCPU | +2–4 GB | +10–20 GB | per concurrent team instance; images can be pre-saved for offline use |
| Tier 3 (LME + Velociraptor + T-Pot) | 4–8 vCPU | 16–32 GB | 50–100+ GB | breaks the lightweight goal |

Network: Tier 2 can stay fully isolated (`internal: true`) and offline if images are
packaged with `docker save`. No egress is required.

## 6. Benefits

- Fills coverage gaps in Silent Ridge: detection engineering, logging gaps and
  retention, LOTL/fileless tradecraft, automated EDR response, DNS/name-based controls,
  MFA and phishing, vulnerability management, ransomware IR.
- Adds tool variety participants do not currently get: auditd, Elastic/Kibana,
  Velociraptor, hashcat, SleuthKit, binwalk, CyberChef.
- Provides ready-made NICE Framework mappings and answer keys that reinforce
  `docs/learning-objectives.md`.
- Containerized conversions are reproducible and adaptable, so authoring effort is
  lower than building from scratch.
- Optional automated grading and tokens if the event grows.
- Maximizes the existing build: one cooperative scenario can become a multi-station
  event with more replay value.

## 7. Costs and effort (estimates)

Assumptions: one engineer already familiar with this repository; working days,
excluding event-day support.

| Work item | Effort | Recurring cost |
|---|---|---|
| Harvest lab techniques into existing injects and handouts | 1–3 days | none |
| Vendor EDR and LOTL Python stations, tests, notices | 2–4 days | low (script drift) |
| Integrate one converted challenge (compose, portal/controller wiring, solutions, tests) | 2–5 days each | image and CVE upkeep |
| Adopt the CTF-NG challenge server and grader | 1–2 weeks | platform maintenance |
| Stand up full LME / Velociraptor / T-Pot labs | 2–4 weeks | heavy infrastructure and ongoing patching |
| Offline packaging of new images (`docker save`) | 0.5–1 day | re-package per release |

Licensing cost is zero. The real costs are engineering time, RAM and disk, and ongoing
maintenance.

## 8. Lightweight-preserving architecture

- **Tier 0 — documentation only.** Map labs to cells and objectives; no infrastructure.
- **Tier 1 — offline Python stations.** Vendor the EDR and LOTL scripts under a `labs/`
  directory; standard library; preserves the no-egress design.
- **Tier 2 — Docker challenge annex.** One to three converted challenges on an isolated
  Compose network, separate from the participant portal.
- **Tier 3 — full hosted labs.** Only if scope deliberately grows; not lightweight.

## 9. Recommended plan

1. **Phase 1 (first).** Harvest technique content from Living Off the Land, Automated
   Defenses, Velociraptor IR, Detection Rules, Log Management, DNS and Phishing into
   Silent Ridge injects, worksheets and learning objectives. Vendor the EDR and LOTL
   scripts as Tier 1 stations. No new hardware.
2. **Phase 2 (optional).** Add a Tier 2 annex with Ransomware Rhapsody (endpoint/IR) and
   Let Loose the Logs of War (hunting). Both are single-container, defensive and
   NICE-mapped.
3. **Phase 3 (only if the event grows).** Consider the CTF-NG challenge server for
   grading, or heavier labs, with a budget review first.

## 10. Risks

- License mix-ups, especially `pc5` (CC BY-NC), and missed attribution.
- Scope creep that breaks the offline, no-egress design.
- Offensive content that is off-theme for a cooperative CND run.
- Maintenance load from container images, CVEs and grader upkeep.
- Resource contention on event hardware if multiple teams run annex challenges at once.

## 11. Decisions to record

- [ ] Import any President's Cup content at all, or keep Silent Ridge self-authored?
- [ ] If yes, which tier (0 / 1 / 2 / 3)?
- [ ] Approve the Phase 1 shortlist (LOTL, EDR, Velociraptor IR, Detection Rules,
      Log Management, DNS, Phishing).
- [ ] Approve vendoring the EDR and LOTL Python stations.
- [ ] Approve a Tier 2 annex (Ransomware Rhapsody, Let Loose the Logs of War).
- [ ] Confirm commercial or non-commercial use (affects `pc5` eligibility).
- [ ] Assign an owner for attribution and license notices.
