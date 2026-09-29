# Learning objectives and NICE Framework mapping

Operation Silent Ridge is a cooperative defensive exercise. This document states
what participants should be able to do afterwards, maps each objective to the NICE
Framework, and names the exercise mechanism that produces the learning rather than
merely describing the topic. It is written for the expanded implementation:
twenty IRIS tickets, each with four CTFd coached questions, coordinated through
IRIS and CTFd from a Guacamole desktop, and analysed with Wireshark, Autopsy,
Wazuh, Cutter and a Linux file manager.

Framework reference: [NIST SP 800-181 Rev. 1, Workforce Framework for Cybersecurity
(NICE Framework)](https://csrc.nist.gov/pubs/sp/800/181/r1/final), NICE Framework
Components version 2.2.0. The role/task relationships used below were checked
against the [official Components 2.2.0 JSON](https://csrc.nist.gov/csrc/media/Projects/cprt/documents/nice/v2-2-0_nf_components.json)
on 2026-09-29 and are recorded in `docs/nice-components-2.2.0-mapping.json`.
Work Role IDs use the current `CATEGORY-WRL-NNN` form.
The 2017 IDs are deprecated; where an organization still reports them, the two most
common equivalents are Cyber Defense Analyst `PR-CDA-001` (now Defensive
Cybersecurity `PD-WRL-001`) and Cyber Defense Incident Responder `PR-CIR-001` (now
Incident Response `PD-WRL-003`).

## How learning is facilitated

The mechanism is the objective, not a lecture around it. Five design choices carry
the teaching load in the expanded implementation:

1. **Authentic, deterministic artifacts.** `expanded/prepare.py` generates a
   purpose-built FAT16 image with a recoverable deleted cache entry, a valid DNS
   PCAP, a reconstructed syslog PCAP that matches the proxy CSV, browser/
   authentication/server/coverage exports, and historical JSONL. Stable source
   hashes replace conspicuous suspicious-record ranges, and the artifact verifier
   checks every released category.
2. **Tool-mediated analysis.** Each ticket names a tool and a starting selection:
   Wireshark (`udp.port == 514`, `dns`), Autopsy (a prepared case with disk, log and
   memory sources), Wazuh (`silent-ridge-timed` for dated events and
   `silent-ridge-timeless` for undated coverage/catalog records), Cutter (a
   harmless static training binary) and the Linux file manager (CSV). Participants
   learn the tool by answering a specific, evidence-bounded question.
3. **Coached, gated questions.** Teams claim one IRIS ticket at a time. Its four
   CTFd questions are answerable only by the owner. Hints and the full walkthrough
   are free. A correct answer earns one point, queues an authored finding for IRIS,
   and persists globally; the last answer closes the ticket and unlocks authored
   follow-ups (for example `T07` requires `T06`; `T20` requires `T07`, `T09`, `T11`
   and `T19`).
4. **Durable shared findings with transactional receipts.** Accepted answers queue
   native IRIS findings and CTFd awards through durable outbox retries and
   application-side receipts. The intended effect is one award/finding/task per event
   key, but that depends on tested adapter behavior: live IRIS and cross-system outage
   acceptance remain gates (see `docs/expanded-validation.md`). Relinquishing a ticket
   retains answers and findings; the replacement owner completes the remainder.
5. **Explicit evidence limits.** Every finding carries a `limitation`, and questions
   repeatedly ask what the evidence does *not* establish ("does a connection entry
   prove a human read the payload?", "is roster disclosure established by the denied
   request?"). Prepared and replayed material is labelled as such.

The after-action review in `facilitator/assessment-aar.md` is the reflection
mechanism; there is no report, grading or approval gate.

## Objectives

### LO1 — Interpret source time and preserve provenance across records

Correlate records while preserving whether each time is a normalized event time,
a `device_time` that needs correction, an undated coverage fact or an actual
acquisition time, recording every correction and never editing the source.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T0173 Perform timeline analysis; T0168 Perform data comparison against established database |
| Defensive Cybersecurity `PD-WRL-001` | T1084 Identify anomalous network activity; T1386 Analyze network traffic anomalies |

**Mechanism.** `T01`/`T02` (Wireshark) and `T03` (Autopsy) read timestamps that are
already normalized. Only `T04` applies the documented 120-second WS-17 device
correction. `T12` reports that offset from an undated coverage record in
`silent-ridge-timeless`; it does not apply the correction or use an absolute time
range. `T13`/`T14` instead read the separate native Windows reconstruction captured
at **2026-09-15T23:22:04.3517080Z**, whose
`assets/native-windows-v1/manifest.json` records **actual acquisition UTC** rather
than the fictional 2026-10-15 scenario time; the historical offset must not be
applied to those acquisition timestamps. `expanded/guides.md`
instructs participants to correct only `device_time` and never to re-correct
normalized or acquisition records; the authored findings record the correction or
its absence.

**Achievement evidence.** The corrected `T04` registration time and the `T12`
device-offset value, alongside `T13`/`T14` answers that preserve actual acquisition
UTC and explicitly refuse the historical correction. Together these demonstrate
that participants can distinguish corrected `device_time`, already normalized
records, timeless coverage facts and provenance-bearing acquisition timestamps.

### LO2 — Reconstruct an intrusion chain and separate observation from inference

Build and defend a causal sequence from independent telemetry, and state precisely
what the evidence does and does not establish.

| Work role | Tasks |
|---|---|
| Defensive Cybersecurity `PD-WRL-001` | T1391 Reconstruct malicious attacks; T1348 Distinguish between benign and potentially malicious attacks and intrusions; T1351 Determine impact of malicious activity |
| Incident Response `PD-WRL-003` | T1489 Correlate incident data; T1252 Determine the scope, urgency, and impact of cyber defense incidents |

**Mechanism.** The chain closes only when records are joined by identifiers:
`req-71` links the plan download to document-service access; session `S-41` spans
identity, endpoint and server; the cached hash links the recovered file to the
catalog; `T15` traces the prepared memory process tree from viewer PID to parent and
cache argument; `T16` correlates that PID with an acquired guest-local connection
snapshot; and `T19` compares the DLP body hash with `server/catalog.csv`. `T20` is a
synthesis ticket that requires `T07`, `T09`, `T11` and `T19` before it unlocks. The
`T16` snapshot is not a validated memory connection; its address was assigned to
guest loopback while networking was disabled, so it establishes neither Internet
traffic nor human receipt.

**Achievement evidence.** Answers that cite the joining identifier, process ancestry
or payload hash and each finding's stated limitation, plus the `T20` conclusion that
distinguishes transmission from human receipt and intent.

### LO3 — Preserve and handle digital evidence defensibly

Treat originals as immutable, verify integrity, work from copies, and respect
prepared artifacts.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T1120 Create forensically sound duplicates of evidence; T1510 Preserve digital evidence; T1199 Identify digital evidence for analysis; T0167 Perform file signature analysis; T1607 Recover information from forensic data sources |

**Mechanism.** Autopsy tickets open a **copy** of a closed prepared case while
`/evidence` and `/originals` stay mounted read-only; `T05` recovers a deleted cache
entry by searching a surviving suffix. Native prepared records retain `original_path`
and `original_sha256` so their derivation can be checked against the supplied
original. `expanded/guides.md` states that imaging, live containment, agent
installation and large ingest jobs are out of scope. The artifact manifest and
verifier enforce integrity, and `T17`/`T18` inspect a harmless training binary
statically in Cutter without executing it. Reading the supplied read-only originals
is coached practice; it does not itself demonstrate acquiring a forensic duplicate,
and no scored item claims that skill.

**Achievement evidence.** Correct use of the writable case copy and read-only
evidence, deleted-file recovery, and findings that trace back to a source reference
rather than a relabelled artifact.

### LO4 — Assess identity and session activity, and judge control efficacy

Reconstruct session use, interpret MFA semantics, and determine whether a credential
action actually contains the incident.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T1250 Perform incident triage; T1251 Recommend incident remediation strategies; T1252 Determine scope, urgency and impact |
| Defensive Cybersecurity `PD-WRL-001` | T1548 Determine adequacy of access controls |
| Insider Threat Analysis `PD-WRL-005` | T1084 Identify anomalous network activity; T1324 Process digital evidence |

**Mechanism.** `T06` uses the Wazuh replay (`data.session:S-41`) to separate the
external `previous_claim` refresh from a failed password login. `T07` then tests
whether the 09:20 password reset contains the incident, using the late 09:26 refresh
and the supplied identity policy; it unlocks only after `T06`.

**Achievement evidence.** Session-centric answers that conclude the reset is
insufficient without explicit revocation, and that treat an IP address as
non-attributive.

### LO5 — Bound disclosure scope and avoid absence-of-evidence fallacies

Quantify what was exposed using response codes, byte counts, object versions and
stated collection limits, and refuse to over-claim from missing data.

| Work role | Tasks |
|---|---|
| Defensive Cybersecurity `PD-WRL-001` | T1351 Determine impact of malicious activity; T1548 Determine adequacy of access controls |
| Incident Response `PD-WRL-003` | T1252 Determine scope, urgency and impact |
| Vulnerability Analysis `PD-WRL-007` | T1020 Determine the operational and safety impacts of cybersecurity lapses |

**Mechanism.** `T08` separates HTTP 200 with bytes from HTTP 403 with zero bytes
(`req-75`); `T09` compares v3 and v4; `T10` is a benign WS-22 comparator; `T11`
leaves WS-31 unresolved; `T12` maps coverage gaps; `T19` establishes payload
identity; `T20` asks directly whether roster disclosure, WS-31 clearance or
adversary intent are established. Each finding's `limitation` records the boundary.

**Achievement evidence.** A scope position that distinguishes disclosed from denied
objects, names the gaps, and avoids an enterprise-wide all-clear or an intent claim.

### LO6 — Test scope hypotheses against coverage and uncertainty

Use reproducible queries to test competing scope hypotheses against the supplied
collection model, and keep systems unresolved where coverage cannot support a
conclusion.

| Work role | Tasks |
|---|---|
| Threat Analysis `PD-WRL-006` | T1053 Identify and characterize intrusion activities; T0718 Identify intelligence gaps and shortfalls; T1054 Scope analysis reports to audiences; T1768 Prepare threat activity reports |
| Defensive Cybersecurity `PD-WRL-001` | T1350 Perform continuous monitoring of system activity |
| Insider Threat Analysis `PD-WRL-005` | T1743 Identify information collection gaps |

**Mechanism.** Timed Wazuh tickets use the absolute scenario-date UTC range against
`silent-ridge-timed`; `T10` establishes a benign host and `T11` an unresolved lead.
`T12` uses `silent-ridge-timeless` for the undated coverage map. The `T11` questions
compare host inventory with collection coverage and explicitly forbid clearing an
unobservable host.

**Achievement evidence.** Reproducible queries or filters per hypothesis and a scope
position (supported / suspected / benign / unobservable) that keeps unresolved hosts
open.

### LO7 — Produce precise, evidence-bounded findings and share them durably

Answer a specific question with the exact requested value and record a finding whose
evidence and limits are explicit, without a manual report.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T1332 Produce incident findings reports; T1333 Communicate incident findings; T1316 Document incidents; T1251 Recommend remediation strategies |
| Defensive Cybersecurity `PD-WRL-001` | T1241 Document cybersecurity incidents; T1603 Recommend threat and vulnerability risk mitigation strategies |

**Mechanism.** Each CTFd question states a format ("Enter only the requested value;
times use HH:MM:SS UTC. Case and outer whitespace are ignored.") and is graded using
that exact rule. A correct answer queues an authored IRIS finding that includes
`text`, `evidence` and `limitation`.
The queue's one-ticket-at-a-time gating and the dependency chain pace the work; the
durable outbox and application-side receipts keep accepted findings from duplicating
across outages, subject to the tested adapter behavior described above.

**Achievement evidence.** Exact answers whose findings carry a source reference and a
limitation, and continued progress after a relinquish or a service interruption.

### LO8 — Reconcile findings across teams and run an after-action review

Build on other teams' shared findings and convert the run into specific improvements.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T0510 Coordinate incident response functions; T1485 Prepare after action reviews; T1333 Communicate incident findings |
| Threat Analysis `PD-WRL-006` | T1643 Develop common operational pictures; T1054 Scope analysis reports to audiences |
| Insider Threat Analysis `PD-WRL-005` | T1986 Develop a continuously updated overview of an incident throughout its life cycle |

**Mechanism.** Accepted answers post native IRIS findings visible to all teams;
ownership transfers retain answers and findings for the replacement owner; global
closure unlocks follow-ups. The AAR asks teams to explain one finding and its
supporting evidence, and to discuss clock normalization, versions/sessions/denied
access/gaps, remaining uncertainty, whether shared findings helped, and which tool
instructions need improvement.

**Achievement evidence.** A follow-up ticket answered from a prior team's finding, and
AAR improvement items with an owner, target rehearsal date and success criterion.

## Ticket-to-role crosswalk

Twenty tickets group by tool and theme. The phase axis comes from the four
authoritative phases in `ridge/scenario_narrative_v1.json`; each row stays within one
phase. The primary role is the strongest match, the tool is the analysis mechanism,
and the final column states the boundary that must survive into the finding.

| Tickets | Scenario phase | Tool / theme | Primary work role | Supporting roles | Evidence limitation |
|---|---|---|---|---|---|
| `T01`, `T02` | Phase 1 — Establish the disclosure path | Wireshark — packet and DNS correlation | Defensive Cybersecurity `PD-WRL-001` | Digital Forensics `PD-WRL-002` | Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent. |
| `T03`, `T04`, `T05` | Phase 1 — Establish the disclosure path | Autopsy — browser, persistence and deleted cache | Digital Forensics `PD-WRL-002` | Defensive Cybersecurity `PD-WRL-001` | Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action. |
| `T06`, `T07` | Phase 2 — Test identity and access explanations | Wazuh — session and credential actions | Incident Response `PD-WRL-003` | Insider Threat Analysis `PD-WRL-005`; Defensive Cybersecurity `PD-WRL-001` | Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur. |
| `T08` | Phase 2 — Test identity and access explanations | Autopsy — document and roster access | Digital Forensics `PD-WRL-002` | Defensive Cybersecurity `PD-WRL-001` | Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action. |
| `T09` | Phase 2 — Test identity and access explanations | File manager — superseding movement information | Defensive Cybersecurity `PD-WRL-001` | Vulnerability Analysis `PD-WRL-007` | The supplied document or export supports only the stated comparison, not human receipt or adversary intent. |
| `T10` | Phase 2 — Test identity and access explanations | Wazuh — benign comparator | Threat Analysis `PD-WRL-006` | Defensive Cybersecurity `PD-WRL-001`; Insider Threat Analysis `PD-WRL-005` | Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur. |
| `T11`, `T12` | Phase 3 — Define scope and collection limits | Wazuh — unresolved lead and coverage | Threat Analysis `PD-WRL-006` | Defensive Cybersecurity `PD-WRL-001`; Insider Threat Analysis `PD-WRL-005` | Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur. |
| `T13`, `T14` | Phase 3 — Define scope and collection limits | Autopsy — “Inspect acquired process-log records”; “Inspect acquired task-log records” | Digital Forensics `PD-WRL-002` | Incident Response `PD-WRL-003` | Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash. |
| `T15` | Phase 3 — Define scope and collection limits | Autopsy — “Inspect the prepared memory process tree” | Digital Forensics `PD-WRL-002` | Incident Response `PD-WRL-003` | Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash. |
| `T16` | Phase 4 — Correlate and state the defensible conclusion | Autopsy — “Correlate the acquired connection snapshot” | Digital Forensics `PD-WRL-002` | Incident Response `PD-WRL-003` | Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash. |
| `T17`, `T18` | Phase 4 — Correlate and state the defensible conclusion | Cutter — static binary inspection | Digital Forensics `PD-WRL-002` | Vulnerability Analysis `PD-WRL-007` | This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable. |
| `T19` | Phase 4 — Correlate and state the defensible conclusion | File manager — payload/hash comparison | Defensive Cybersecurity `PD-WRL-001` | Vulnerability Analysis `PD-WRL-007` | The supplied document or export supports only the stated comparison, not human receipt or adversary intent. |
| `T20` | Phase 4 — Correlate and state the defensible conclusion | Cross-source synthesis — limits of the overall exposure conclusion | Incident Response `PD-WRL-003` | Defensive Cybersecurity `PD-WRL-001`; Threat Analysis `PD-WRL-006` | Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur. |

## How the after-action review revisits the objectives

There is no rubric; `facilitator/assessment-aar.md` uses the scoreboard and shared
IRIS findings for discussion. Each AAR prompt exercises one or more objectives:

| AAR prompt | Objectives most exercised |
|---|---|
| How source-time interpretation or a cross-source correlation changed an assessment | LO1, LO2 |
| What versions, sessions, denied accesses and collection gaps establish | LO2, LO4, LO5 |
| Which uncertainties remain and what further evidence would resolve them | LO5, LO6 |
| Whether shared findings and ownership transfers helped other teams | LO7, LO8 |
| Which tool instructions or exercise defects need improvement | LO1, LO3, LO7 |

## Out of scope and current limits

The exercise is defensive and synthetic. It does not teach or assess offensive
access, malware reverse engineering, or live imaging; the Cutter binary is a harmless
training surrogate that performs no network or persistence behaviour.

Three limits matter for formal training credit:

- **Artifacts exist; whole-event acceptance does not.** The native Windows
  reconstruction (`assets/native-windows-v1/manifest.json`), the prepared Autopsy
  case (`assets/autopsy-case-v2.json`) and the offline desktop image
  (`assets/desktop-v1.json`) are published and checksummed, so tickets `T13`–`T16`
  have prepared artifacts to reference. That is not a validated deployment: per
  `docs/expanded-validation.md`, every question has not yet been navigated and
  answered on the exact installed tools, and Hyper-V/AWS boot, Guacamole sessions
  and live IRIS/CTFd behavior remain unverified.
- **Practice is not assessment.** The free hints and walkthroughs and the supplied
  read-only originals support coached practice; reading a supplied original does not
  by itself demonstrate acquiring a forensic duplicate or unaided mastery, and no
  scored item treats it as such.
- **The workload is an estimate.** The 1,300 team-minute figure is arithmetic, not a
  measurement. With ten teams and current dependencies, the scheduling model has a
  195-minute simulated makespan and critical path. The event target is 240–300
  minutes, with a 270-minute planning midpoint, including facilitated segments;
  beginner rehearsal is still required before relying on those figures. The NICE
  Work Role and Task IDs above are pinned to Components version 2.2.0 and checked
  against the compact official-source receipt named above.

## Maintenance

Work role and task IDs track NICE Framework Components version 2.2.0 (SP 800-181
Rev. 1). When NIST publishes a new Components version, re-verify the `PD-WRL-*`
IDs and task statements against the [NICE Framework Resource
Center](https://www.nist.gov/itl/applied-cybersecurity/nice/resources/nice-framework)
and replace `docs/nice-components-2.2.0-mapping.json` before reusing this mapping.
When tickets are added or retitled in `expanded/author.py`, update the crosswalk
above.
