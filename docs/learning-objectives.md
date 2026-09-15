# Learning objectives and NICE Framework mapping

Operation Silent Ridge is a cooperative defensive exercise. This document states
what participants should be able to do afterwards, maps each objective to the NICE
Framework, and names the exercise mechanism that produces the learning rather than
merely describing the topic. It is written for the expanded implementation:
twenty IRIS tickets, each with four CTFd coached questions, analysed with
Wireshark, Autopsy, Wazuh, Cutter and a Linux file manager.

Framework reference: [NIST SP 800-181 Rev. 1, Workforce Framework for Cybersecurity
(NICE Framework)](https://csrc.nist.gov/pubs/sp/800/181/r1/final), NICE Framework
Components version 2.2.0. Work Role IDs use the current `CATEGORY-WRL-NNN` form.
The 2017 IDs are deprecated; where an organization still reports them, the two most
common equivalents are Cyber Defense Analyst `PR-CDA-001` (now Defensive
Cybersecurity `PD-WRL-001`) and Cyber Defense Incident Responder `PR-CIR-001` (now
Incident Response `PD-WRL-003`). Task IDs are stable across the revision.

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
   memory sources), Wazuh (a `silent-ridge-*` historical data view), Cutter (a
   harmless static training binary) and the Linux file manager (CSV). Participants
   learn the tool by answering a specific, evidence-bounded question.
3. **Coached, gated questions.** Teams claim one IRIS ticket at a time. Its four
   CTFd questions are answerable only by the owner. Hints and the full walkthrough
   are free. A correct answer earns one point, queues an authored finding for IRIS,
   and persists globally; the last answer closes the ticket and unlocks authored
   follow-ups (for example `T07` requires `T06`; `T20` requires `T07`, `T09`, `T11`
   and `T19`).
4. **Exactly-once shared findings.** Accepted answers post native IRIS findings and
   CTFd awards through atomic application-side receipts, so other teams inherit
   findings without duplicate awards. Relinquishing a ticket retains answers and
   findings; the replacement owner completes the remainder.
5. **Explicit evidence limits.** Every finding carries a `limitation`, and questions
   repeatedly ask what the evidence does *not* establish ("does a connection entry
   prove a human read the payload?", "is roster disclosure established by the denied
   request?"). Prepared and replayed material is labelled as such.

The after-action review in `facilitator/assessment-aar.md` is the reflection
mechanism; there is no report, grading or approval gate.

## Objectives

### LO1 — Normalize and correlate time across heterogeneous sources

Reconstruct a single UTC timeline from sources with different clocks and
conventions, recording every correction and never editing the source.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T0173 Perform timeline analysis; T0168 Perform data comparison against established database |
| Defensive Cybersecurity `PD-WRL-001` | T1084 Identify anomalous network activity; T1386 Analyze network traffic anomalies |

**Mechanism.** Tickets `T01`/`T02` (Wireshark), `T03`/`T04` (Autopsy), `T12`
(coverage) and `T13`/`T14` (prepared device logs) require corrected times. WS-17
device times are 120 seconds fast; Wazuh/SIEM times are already normalized.
`expanded/guides.md` instructs participants to correct only when a source gives an
offset and never to re-correct normalized records; the authored findings record the
correction.

**Achievement evidence.** Corrected times that reconcile across at least two tools
(for example the corrected viewer start and task registration), with the offset
stated and no double correction.

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
catalog; `T19` compares the DLP body hash with `server/catalog.csv`. `T20` is a
synthesis ticket that requires `T07`, `T09`, `T11` and `T19` before it unlocks.

**Achievement evidence.** Answers that cite the joining identifier and each finding's
stated limitation, plus the `T20` conclusion that distinguishes transmission from
human receipt and intent.

### LO3 — Preserve and handle digital evidence defensibly

Treat originals as immutable, verify integrity, work from copies, and respect
prepared artifacts.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T1120 Create forensically sound duplicates of evidence; T1510 Preserve digital evidence; T1199 Identify digital evidence for analysis; T0167 Perform file signature analysis; T1607 Recover information from forensic data sources |

**Mechanism.** Autopsy tickets open a **copy** of a closed prepared case while
`/evidence` stays mounted read-only; `T05` recovers a deleted cache entry by
searching a surviving suffix. `expanded/guides.md` states that imaging, live
containment, agent installation and large ingest jobs are out of scope. The artifact
manifest and verifier enforce integrity, and `T17`/`T18` inspect a harmless training
binary statically in Cutter without executing it.

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

### LO6 — Hunt across the enterprise with an explicit coverage model

Test competing hypotheses about scope with reproducible queries and state where no
conclusion is possible.

| Work role | Tasks |
|---|---|
| Threat Analysis `PD-WRL-006` | T1053 Identify and characterize intrusion activities; T0718 Identify intelligence gaps and shortfalls; T1054 Scope analysis reports to audiences; T1768 Prepare threat activity reports |
| Defensive Cybersecurity `PD-WRL-001` | T1350 Perform continuous monitoring of system activity |
| Insider Threat Analysis `PD-WRL-005` | T1743 Identify information collection gaps |

**Mechanism.** Wazuh tickets use an absolute scenario-date UTC range against the
`silent-ridge-*` view; `T10` establishes a benign host, `T11` an unresolved lead and
`T12` the coverage map. The `T11` and `T20` questions require a host-versus-IP
inventory comparison and explicitly forbid clearing an unobservable host.

**Achievement evidence.** Reproducible queries or filters per hypothesis and a scope
position (supported / suspected / benign / unobservable) that keeps unresolved hosts
open.

### LO7 — Produce precise, evidence-bounded findings and share them durably

Answer a specific question with the exact requested value and record a finding whose
evidence and limits are explicit, without a manual report.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T1332 Produce incident findings reports; T1333 Communicate incident findings; T1316 Document incidents; T1251 Recommend remediation strategies |
| Defensive Cybersecurity `PD-WRL-001` | T1241 Document cybersecurity incidents; T1428 Notify designated managers of suspected incidents; T1603 Recommend threat and vulnerability risk mitigation strategies |

**Mechanism.** Each CTFd question states a format ("Enter only the requested value;
times use HH:MM:SS UTC") and is graded against a normalized answer. A correct answer
queues an authored IRIS finding that includes `text`, `evidence` and `limitation`.
The queue's one-ticket-at-a-time gating and the dependency chain pace the work; the
exactly-once outbox keeps accepted findings durable across outages.

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

Twenty tickets group by tool and theme. The primary role is the strongest match; the
tool is the analysis mechanism.

| Tickets | Tool / theme | Primary work role | Supporting roles |
|---|---|---|---|
| `T01`, `T02` | Wireshark — packet and DNS correlation | Defensive Cybersecurity `PD-WRL-001` | Digital Forensics `PD-WRL-002` |
| `T03`, `T04`, `T05`, `T08` | Autopsy — disk, browser, persistence, access | Digital Forensics `PD-WRL-002` | Defensive Cybersecurity `PD-WRL-001` |
| `T13`, `T14` | Autopsy — prepared process/task logs | Digital Forensics `PD-WRL-002` | Incident Response `PD-WRL-003` |
| `T15`, `T16` | Autopsy — prepared memory tree/connections | Digital Forensics `PD-WRL-002` | Incident Response `PD-WRL-003` |
| `T06`, `T07` | Wazuh — session and credential actions | Incident Response `PD-WRL-003` | Insider Threat Analysis `PD-WRL-005`; Defensive Cybersecurity `PD-WRL-001` |
| `T09`, `T19` | File manager — version and payload comparison | Defensive Cybersecurity `PD-WRL-001` | Vulnerability Analysis `PD-WRL-007` |
| `T10`, `T11`, `T12`, `T20` | Wazuh — hunting, coverage and synthesis | Threat Analysis `PD-WRL-006` | Defensive Cybersecurity `PD-WRL-001`; Insider Threat Analysis `PD-WRL-005` |
| `T17`, `T18` | Cutter — static binary inspection | Digital Forensics `PD-WRL-002` | Vulnerability Analysis `PD-WRL-007` |

## How the after-action review revisits the objectives

There is no rubric; `facilitator/assessment-aar.md` uses the scoreboard and shared
IRIS findings for discussion. Each AAR prompt exercises one or more objectives:

| AAR prompt | Objectives most exercised |
|---|---|
| How clock normalization or a cross-source correlation changed an assessment | LO1, LO2 |
| What versions, sessions, denied accesses and collection gaps establish | LO2, LO4, LO5 |
| Which uncertainties remain and what further evidence would resolve them | LO5, LO6 |
| Whether shared findings and ownership transfers helped other teams | LO7, LO8 |
| Which tool instructions or exercise defects need improvement | LO1, LO3, LO7 |

## Out of scope and current limits

The exercise is defensive and synthetic. It does not teach or assess offensive
access, malware reverse engineering, or live imaging; the Cutter binary is a harmless
training surrogate that performs no network or persistence behaviour.

Two limits matter for formal training credit:

- **Some tickets are not yet runnable.** Per `docs/expanded-evidence.md` and
  `docs/expanded-validation.md`, native Windows EVTX and memory sources and
  ready-to-open Autopsy cases are still required. Tickets targeting prepared
  process, task and memory records (`T13`–`T16`) and Autopsy disk/log workflows
  cannot be completed until those artifacts exist.
- **The workload is an estimate.** The 1,300 team-minute figure is arithmetic, not a
  measurement; beginner rehearsal is required before relying on it.

## Maintenance

Work role and task IDs track NICE Framework Components version 2.2.0 (SP 800-181
Rev. 1). When NIST publishes a new Components version, re-verify the `PD-WRL-*`
IDs and task statements against the [NICE Framework Resource
Center](https://www.nist.gov/itl/applied-cybersecurity/nice/resources/nice-framework)
before reusing this mapping. When tickets are added or retitled in
`expanded/author.py`, update the crosswalk above.
