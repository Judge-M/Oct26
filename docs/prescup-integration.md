# President's Cup content: augmentation proposal

**Status:** proposal for review — no content has been imported.
**Source:** <https://github.com/cisagov/prescup-challenges> (CISA / CMU SEI; MIT / CC0 / Apache-2.0 / MIT(SEI) per directory).
**Target:** the expanded Silent Ridge implementation (IRIS queue, CTFd questions,
Wazuh, Autopsy, Wireshark, Cutter, Guacamole desktops). See
`docs/expanded-deployment.md` and `docs/expanded-validation.md`.
**Goal:** decide what, if anything, to pull into Silent Ridge while keeping the
exercise reproducible and offline.

This document inventories the reusable President's Cup content, maps it to the
twenty expanded tickets and the analysis tools, and estimates the software,
hardware, cost and effort of each option. Everything below is a planning estimate,
not a commitment. It supersedes the earlier version written against the retired
five-cell baseline.

## 1. Bottom line

The expanded stack changes the calculus in two ways. First, it already runs an
Elastic-based SIEM (Wazuh), CTFd, Autopsy, Cutter and Guacamole, so several
President's Cup labs now map **directly** onto tools the exercise already uses.
Second, the stack is already heavy and only partly validated, so adding more
infrastructure works against the lightweight goal. The value is therefore in
**technique and scenario content**, not in standing up more VMs.

Three layers remain the right frame:

1. **Technique and scenario harvesting** from the skill labs into existing or new
   tickets and findings. Near-zero infrastructure.
2. **Self-contained Python scenarios** (an EDR hash-monitor and a LOTL
   log-injection pair) vendored as optional offline stations. Standard library only.
3. **Optional converted challenge annex** using one to three of the
   `conversions/` challenges, which are the only content that runs as shipped.

## 2. Licensing guardrails

The repository is **not uniformly MIT**. The top-level `LICENSE.md` concatenates
per-season terms:

| Source directory | License | Usable |
|---|---|---|
| `skilling-continuation-labs/` | MIT | Yes; keep notice |
| `pc7/`, `conversions/` | CC0 (US government) + contractor grant + Apache-2.0 | Yes; keep notice |
| `pc1`–`pc4`, `pc6`, `pc6-round1` | MIT (SEI) — MIT-style but custom, with third-party clauses | Yes; keep notices |
| `pc5` | CC BY-NC 4.0 (non-commercial) | Only if the CTF is non-commercial |

If we import anything: retain the copyright and permission notice, carry third-party
asset terms (fonts, Bootstrap, jQuery and so on), and record provenance. Do not
import `pc5` content if the event could ever be commercial.

## 3. Fit against the expanded architecture

The expanded implementation already satisfies several things the President's Cup
labs would otherwise require:

| Expanded capability | President's Cup labs that now map to it |
|---|---|
| Wazuh (Elastic-based) historical view | Detection Rules in Logging Made Easy; Log Management using LME; Living Off the Land |
| CTFd coached questions and scoring | `conversions/challenge-server` grading/token model is largely redundant |
| Autopsy prepared cases | Training Day (deleted artifact, logs, PCAP, memory blob); Project Overwatch; Ransomware Rhapsody |
| Cutter static analysis | Training Day static binary exercise; Project Overwatch rootkit techniques |
| Guacamole Ubuntu/Xfce desktops | Any lab VM, at the cost of more desktop images and memory |
| IRIS native findings | Prescup scenario write-ups and answer keys as finding text |

The practical conclusion: prefer **content** that enriches existing Wazuh/Autopsy/
Cutter tickets, and avoid duplicating CTFd/IRIS with the CTF-NG challenge server.

## 4. Inventory and fit

### Group A — converted, containerized challenges (`conversions/`, 12 total)

Self-contained, reproducible, and explicitly written to be adapted. Mapped to the
expanded tickets and tools:

| Challenge | Type | Expanded fit | Infrastructure to run |
|---|---|---|---|
| Ransomware Rhapsody (`c21`) | Ransomware IR / disk forensics | Autopsy disk tickets (`T03`–`T05`, `T08`) | One Ubuntu container |
| Throw Me A Bone (`c02`) | Vulnerability management + AD password audit | New server/vulnerability ticket (NTDS.dit, hashcat) | Six servers + scanner + Kali (heavy) |
| Let Loose the Logs of War (`c05`) | Log analysis | Wazuh hunting tickets (`T10`–`T12`) | One container |
| Mindhunter (`c47`) | Forensics | Autopsy/endpoint tickets | One container |
| Weak Web Warnings (`c37`), Shop Smart (`c03`) | Web exploitation | None (offensive; off-theme) | Web + Kali |
| They All Float Down Here (`c04`) | Floating-point coding puzzle | None | One container |
| Triple Lindy (`c01`), Finsta (`c18`), va_list (`c34`), Kessel Run (`c41`), Crucible (`c45`) | Mixed (OSINT / binary) | Low-Med | Varies |

### Group B — skill labs (`skilling-continuation-labs/`, 19 total)

Most are documentation plus a solution; the environments are hosted, not shipped.

| Lab | Ships in repo | Expanded fit | Infrastructure if run for real |
|---|---|---|---|
| Living Off the Land | `httpListener.py`, `logInjection.sh`, `mini_challenge.py`, systemd units | Wazuh encoded-PowerShell detection; hunting tickets | auditd + pwsh |
| Automated Defenses | `EDR-Files.zip` (`file_monitor.py`, `encryptor.py`), `emailer.sh` | Endpoint/response; a self-contained station | Standard-library Python |
| Incident Response with Velociraptor | `windows10-baseline.zip`, `ubuntu-baseline.zip`, `grading.py` | Autopsy/memory tickets (`T13`–`T16`); baseline-vs-compromised | Velociraptor server + clients |
| Detection Rules in Logging Made Easy | docs only | Wazuh detection engineering (Sigma/Elastic) | Wazuh (already present) |
| Log Management using Logging Made Easy | `fresh-os-services.txt` | Wazuh logging gaps and retention | Wazuh (already present) |
| DNS and Name-based Security Solutions | docs only | Wireshark network tickets (`T01`, `T02`) | Pi-hole, Postfix, pfSense, Kali |
| Phishing Mitigation with MFA | docs only | Identity tickets (`T06`, `T07`) | Web app + mail server |
| fast-flux, weaponized-archive, xz-utils, secure-programming, web pentest, SCADA/Modbus, Kubernetes, network-segmentation | docs (some include sample malware or tarballs) | Low / None | Heavy, offensive, or risky |

### Group C — platform (`conversions/challenge-server/`)

A complete CTF challenge host (Flask, CoreDNS, grading config, `internal: true`
networks). The expanded stack already provides CTFd and IRIS, so adopting this would
duplicate the question/scoring layer. Consider it only for hosting a separate,
optional annex — not as a replacement for CTFd/IRIS.

## 5. Software requirements

| Layer | Expanded baseline (today) | Added |
|---|---|---|
| Tier 1 — offline skill stations | Python 3.12, Docker, IRIS/CTFd/Wazuh stack | Nothing new |
| Tier 2 — challenge annex | Docker Engine + Compose v2 | Challenge base images (`debian:bullseye`, `python:latest`, `alpine`) |
| Tier 3 — full labs | IRIS 2.4.20, CTFd 3.7.7, Wazuh 4.9.2, Guacamole 1.5.5, Autopsy 4.22.0, Cutter 2.3.4, Ubuntu 24.04 Xfce | Elasticsearch/ElastAlert/Wazuh extras, Velociraptor, pfSense, Pi-hole, Postfix, T-Pot, Kali |
| Participant tooling | Autopsy, Wireshark, Cutter, Wazuh, file manager | Optional: hashcat / John, SleuthKit, binwalk, foremost, CyberChef, nmap |

Note that Tier 3's Elastic-family additions partially overlap Wazuh, which already
bundles an Elastic-compatible indexer and dashboard.

## 6. Hardware requirements

| Layer | CPU | RAM | Disk | Notes |
|---|---|---|---|---|
| Expanded baseline | unmeasured (see `deployment/expanded/measure.py`) | unmeasured | unmeasured | IRIS + Postgres + RabbitMQ + CTFd + MariaDB + Redis + Wazuh + Guacamole + desktop VMs |
| Tier 1 | — | +0.5 GB | <100 MB | negligible |
| Tier 2 (1–3 challenges + server) | 2–4 vCPU | +2–4 GB | +10–20 GB | per concurrent team instance; images can be pre-saved for offline use |
| Tier 3 (full labs) | 4–8 vCPU | +16–32 GB | +50–100 GB | works against the lightweight goal |

The expanded baseline itself is already large and its sizing is explicitly
unmeasured. Any Tier 2 or Tier 3 addition should follow a measured rehearsal on the
Linux host. Tier 2 can stay isolated (`internal: true`) and offline if images are
packaged with `docker save`.

## 7. Benefits

- Enriches existing Wazuh, Autopsy and Cutter tickets with ready-made scenarios,
  queries and answer keys, at near-zero infrastructure cost (Tier 0/1).
- Adds defensive coverage the expanded content does not yet exercise: detection
  engineering, logging gaps and retention, LOTL/fileless tradecraft, automated EDR
  response, DNS/name-based controls, MFA and phishing, vulnerability management.
- Provides additional NICE-mapped activities that extend
  `docs/learning-objectives.md`.
- Optional single-container challenges add hands-on tool variety (SleuthKit,
  binwalk, hashcat, scapy) without a full lab stack.

## 8. Costs and effort (estimates)

Assumptions: one engineer already familiar with this repository; working days,
excluding event-day support.

| Work item | Effort | Recurring cost |
|---|---|---|
| Harvest lab techniques into existing/new tickets and findings | 2–5 days | none |
| Vendor EDR and LOTL Python stations, tests, notices | 2–4 days | low (script drift) |
| Integrate one converted challenge (compose, ticket/finding wiring, solutions, tests) | 2–5 days each | image and CVE upkeep |
| Add a Wazuh detection-engineering ticket from Detection Rules/LME | 2–4 days | index/rule maintenance |
| Stand up full LME/Velociraptor/T-Pot labs | 2–4 weeks | heavy infrastructure and patching |
| Offline packaging of new images (`docker save`) | 0.5–1 day | re-package per release |

Licensing cost is zero. The real costs are engineering time, RAM and disk, and
ongoing maintenance — all of which the expanded stack has already raised.

## 9. Lightweight-preserving integration

- **Tier 0 — documentation only.** Map labs to tickets and objectives; no
  infrastructure.
- **Tier 1 — offline Python stations.** Vendor the EDR and LOTL scripts under a
  `labs/` directory; standard library; preserves the offline design.
- **Tier 2 — Docker challenge annex.** One to three converted challenges on an
  isolated Compose network, separate from the central stack.
- **Tier 3 — full hosted labs.** Only if scope deliberately grows.

## 10. Recommended plan

1. **Phase 1 (first).** Harvest technique content from Living Off the Land,
   Automated Defenses, Velociraptor IR, Detection Rules, Log Management, DNS and
   Phishing into existing or new tickets, using the tools the exercise already
   ships. Vendor the EDR and LOTL scripts as Tier 1 stations.
2. **Phase 2 (optional).** Add a Tier 2 annex with Ransomware Rhapsody (Autopsy
   disk forensics) and Let Loose the Logs of War (Wazuh log analysis).
3. **Phase 3 (only if the event grows).** Consider heavier labs, with a measured
   resource review first. Do not adopt the CTF-NG challenge server; CTFd already
   provides the question and scoring layer.

## 11. Risks

- License mix-ups, especially `pc5` (CC BY-NC), and missed attribution.
- Scope creep on a stack that is already heavy and only partly validated.
- Offensive content that is off-theme for a cooperative CND run.
- Maintenance load from extra images, CVEs and grader upkeep.
- Resource contention on event hardware if annex challenges run alongside the
  central stack.

## 12. Decisions to record

- [ ] Import any President's Cup content, or keep Silent Ridge self-authored?
- [ ] If yes, which tier (0 / 1 / 2 / 3)?
- [ ] Approve the Phase 1 shortlist (LOTL, EDR, Velociraptor IR, Detection Rules,
      Log Management, DNS, Phishing) and the tickets each maps to.
- [ ] Approve vendoring the EDR and LOTL Python stations.
- [ ] Approve a Tier 2 annex (Ransomware Rhapsody, Let Loose the Logs of War).
- [ ] Confirm commercial or non-commercial use (affects `pc5` eligibility).
- [ ] Assign an owner for attribution and license notices.
