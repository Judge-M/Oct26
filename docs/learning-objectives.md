# Learning objectives and NICE Framework mapping

Operation Silent Ridge is a cooperative defensive exercise. This document states
what participants should be able to do afterwards, maps each objective to the NICE
Framework, and names the exercise mechanism that produces the learning rather than
merely describing the topic.

Framework reference: [NIST SP 800-181 Rev. 1, Workforce Framework for Cybersecurity
(NICE Framework)](https://csrc.nist.gov/pubs/sp/800/181/r1/final), NICE Framework
Components version 2.2.0. Work Role IDs use the current `CATEGORY-WRL-NNN` form.
The 2017 IDs are deprecated; where an organization still reports them, the two most
common equivalents are Cyber Defense Analyst `PR-CDA-001` (now Defensive
Cybersecurity `PD-WRL-001`) and Cyber Defense Incident Responder `PR-CIR-001` (now
Incident Response `PD-WRL-003`). Task IDs are stable across the revision.

## How learning is facilitated

The exercise is built so that the mechanism *is* the objective, not a lecture around
it. Five design choices carry the teaching load:

1. **Authentic, deterministic artifacts.** Each cell receives native-feeling evidence
   (CSV, JSONL, a purpose-built SQLite database, and a valid Ethernet/IPv4/UDP PCAP)
   with a per-bundle `SHA256SUMS.json`. Conclusions require real joins, not recall.
2. **Staged injects that force revision.** Injects 1–3 are released manually by the
   controller on a schedule. Each adds evidence that changes a prior assessment
   (payload identity, session validity after a reset, a new host), so participants
   practise updating a position instead of defending a first guess.
3. **A shared work surface.** All five cells read and comment on all tickets; only
   the owning cell changes status. The joint assessment is produced on ticket 5,
   which makes cross-cell reconciliation a graded behaviour.
4. **Read-only analysis tooling.** The browser workspace opens artifacts read-only
   (SQLite via an authorizer that denies writes/ATTACH/PRAGMA/extensions), offers a
   hash comparator and a non-destructive UTC calculator, and a Cite action that
   pastes file, digest, row and query into the draft. Unsafe analysis is impossible
   by construction, so attention stays on reasoning.
5. **Simulated command with an external ledger.** Participants request actions; only
   a named controller acknowledgment in the ledger changes simulation state. This
   separates "we recommended" from "it happened" and is where proportionality is
   coached.

Assessment uses `facilitator/assessment-aar.md`; the five-phase AAR is the
reflection mechanism that converts the run into transferable practice.

## Objectives

### LO1 — Normalize and correlate time across heterogeneous sources

Reconstruct a single UTC timeline from sources with different clocks and
conventions, recording every correction and never editing the source.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T0173 Perform timeline analysis; T0168 Perform data comparison against established database |
| Defensive Cybersecurity `PD-WRL-001` | T1084 Identify anomalous network activity; T1386 Analyze network traffic anomalies |

**Mechanism.** `endpoint/clock.txt` states WS-17 runs 120 seconds fast; the browser
UTC calculator applies an offset without altering evidence; the analysis workspace
shows normalized and raw times side by side; worksheets require the correction to be
written down. The rubric's "Evidence and reproducibility" dimension scores incorrect
normalization, and solutions require the corrected E-series times to align with the
network and server records.

**Achievement evidence.** Corrected E101–E105 timestamps, the stated offset, and a
ticket timeline whose UTC values reconcile across at least two sources.

### LO2 — Reconstruct an intrusion chain and separate observation from inference

Build and defend a causal sequence from independent telemetry, and state precisely
what the evidence does and does not establish.

| Work role | Tasks |
|---|---|
| Defensive Cybersecurity `PD-WRL-001` | T1391 Reconstruct malicious attacks; T1348 Distinguish between benign and potentially malicious attacks and intrusions; T1351 Determine impact of malicious activity |
| Incident Response `PD-WRL-003` | T1489 Correlate incident data; T1252 Determine the scope, urgency, and impact of cyber defense incidents |

**Mechanism.** The chain only closes when rows are joined by identifiers: `req-71`
links N101 to S101; session `S-41` spans identity, endpoint and server; the cached
file hash links E103 to the catalog. Injects 1 and 2 add the DLP body and a version
comparison, so payload identity and current sensitivity are established in stages.
The controller-guide adjudication table explicitly asks what each source cannot
prove (for example, N103 acknowledges a request but not a human reading it).

**Achievement evidence.** A cited timeline that names supporting *and* contradicting
records, with confidence labels and an explicit statement of the remaining gap.

### LO3 — Preserve and handle digital evidence defensibly

Treat originals as immutable, verify integrity, work from copies, and justify
preservation before remediation.

| Work role | Tasks |
|---|---|
| Digital Forensics `PD-WRL-002` | T1120 Create forensically sound duplicates of evidence; T1510 Preserve digital evidence; T1199 Identify digital evidence for analysis; T0167 Perform file signature analysis; T1607 Recover information from forensic data sources |

**Mechanism.** Every bundle ships `SHA256SUMS.json`; the workspace's hash comparator
checks a digest against the opened artifact; worksheets instruct participants to keep
the download read-only and analyze a copy; `exercise.py verify` enforces byte
equality between the vault and the published tree. The controller's default response
to "isolate WS-17" requires a preservation plan and a verification method. No
executable is supplied, which keeps the focus on evidence handling rather than
running the artifact.

**Achievement evidence.** Recorded receipt hashes, use of a working copy, and a
containment recommendation that preserves volatile evidence and states how success
will be verified.

### LO4 — Assess identity and session activity, and judge control efficacy

Reconstruct session use, interpret MFA semantics, and determine whether a credential
action actually contains the incident.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T1250 Perform incident triage; T1251 Recommend incident remediation strategies; T1252 Determine scope, urgency and impact |
| Defensive Cybersecurity `PD-WRL-001` | T1548 Determine adequacy of access controls |
| Insider Threat Analysis `PD-WRL-005` | T1084 Identify anomalous network activity; T1324 Process digital evidence |

**Mechanism.** `identity/policy.txt` states that a password reset does not invalidate
issued sessions. Inject 2 adds `I201`, a later successful refresh of `S-41`, so the
grouping-by-session lesson has a concrete outcome. The controller records revocation
as a *simulated* control and asks participants to distinguish a control assertion
from logged evidence.

**Achievement evidence.** Session-centric analysis that correctly concludes the reset
is insufficient, recommends explicit revocation, and flags IP addresses as
non-attributive.

### LO5 — Bound disclosure scope and avoid absence-of-evidence fallacies

Quantify what was exposed using response codes, byte counts, object versions and
stated collection limits, and refuse to over-claim from missing data.

| Work role | Tasks |
|---|---|
| Defensive Cybersecurity `PD-WRL-001` | T1351 Determine impact of malicious activity; T1548 Determine adequacy of access controls |
| Incident Response `PD-WRL-003` | T1252 Determine scope, urgency and impact |
| Vulnerability Analysis `PD-WRL-007` | T1020 Determine the operational and safety impacts of cybersecurity lapses |

**Mechanism.** `server/access.csv` separates HTTP 200 with bytes from HTTP 403 with
zero bytes; `server/catalog.csv` ties objects to versions and hashes;
`server/collection.txt` declares a 09:14–09:18 audit gap; `hunting/coverage.csv`
marks WS-31 as unobservable after 08:50. The rubric awards full reasoning credit for
a well-justified "unknown," and the AAR revisits the gap between v3 and v4.

**Achievement evidence.** A scope statement that distinguishes disclosed from denied
objects, names the collection gaps, and avoids an enterprise-wide all-clear.

### LO6 — Hunt across the enterprise with an explicit coverage model

Test competing hypotheses about scope with reproducible queries and state where no
conclusion is possible.

| Work role | Tasks |
|---|---|
| Threat Analysis `PD-WRL-006` | T1053 Identify and characterize intrusion activities; T0718 Identify intelligence gaps and shortfalls; T1054 Scope analysis reports to audiences; T1768 Prepare threat activity reports |
| Defensive Cybersecurity `PD-WRL-001` | T1350 Perform continuous monitoring of system activity |
| Insider Threat Analysis `PD-WRL-005` | T1743 Identify information collection gaps |

**Mechanism.** `hunting/siem.jsonl` and `coverage.csv` must be read together; the
solutions show a cross-host query that includes IDP-1's H102, so a host-only filter
misses the account event. Inject 3's H201/H202 pair is a deliberate name-match
counterexample that punishes detection by artifact name alone. The hunting reporter
owns the joint assessment, which forces the coverage model to be written down.

**Achievement evidence.** A scope matrix (supported / suspected / benign /
unobservable) with a reproducible query or filter per hypothesis.

### LO7 — Report under time pressure and recommend proportionately

Deliver actionable, evidence-cited updates on deadline and propose defensive actions
with benefit, cost and a verification step.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T1332 Produce incident findings reports; T1333 Communicate incident findings; T1316 Document incidents; T1251 Recommend remediation strategies |
| Defensive Cybersecurity `PD-WRL-001` | T1241 Document cybersecurity incidents; T1428 Notify designated managers of suspected incidents; T1603 Recommend threat and vulnerability risk mitigation strategies |

**Mechanism.** `schedule.py` derives hard deadlines for the initial report and each
inject response; the worksheet supplies a 60-second report template; the Cite action
attaches source and query to the draft; the controller ledger is the only place an
action becomes real. The rubric scores timeliness and penalizes treating a request as
completed containment.

**Achievement evidence.** An initial report by the deadline, every claim carrying a
source and row ID, and an action request that cites its CTL acknowledgment ID.

### LO8 — Reconcile findings across teams and run an after-action review

Produce a joint assessment that preserves disagreement, then convert the run into
specific improvements.

| Work role | Tasks |
|---|---|
| Incident Response `PD-WRL-003` | T0510 Coordinate incident response functions; T1485 Prepare after action reviews; T1333 Communicate incident findings |
| Threat Analysis `PD-WRL-006` | T1643 Develop common operational pictures; T1054 Scope analysis reports to audiences |
| Insider Threat Analysis `PD-WRL-005` | T1986 Develop a continuously updated overview of an incident throughout its life cycle |

**Mechanism.** All cells contribute to ticket 5 by `cell_handover` and the hunting
reporter posts the JOINT ASSESSMENT by `joint_report`; unresolved differences are
kept rather than averaged. `assessment-aar.md` divides the AAR into five phases that
each end with an owner, a date and an observable success criterion.

**Achievement evidence.** A cross-cell comment that changed another cell's analysis,
a joint assessment that lists unresolved disagreements, and AAR improvement items
with owners.

## Cell-to-role crosswalk

| Cell (ticket) | Primary work role | Supporting roles |
|---|---|---|
| Network (1) | Defensive Cybersecurity `PD-WRL-001` | Digital Forensics `PD-WRL-002` |
| Endpoint (2) | Digital Forensics `PD-WRL-002` | Defensive Cybersecurity `PD-WRL-001` |
| Identity (3) | Incident Response `PD-WRL-003` | Insider Threat Analysis `PD-WRL-005`; Defensive Cybersecurity `PD-WRL-001` |
| Server and data (4) | Defensive Cybersecurity `PD-WRL-001` | Incident Response `PD-WRL-003`; Vulnerability Analysis `PD-WRL-007` |
| Threat hunting (5) | Threat Analysis `PD-WRL-006` | Defensive Cybersecurity `PD-WRL-001`; Insider Threat Analysis `PD-WRL-005` |
| Joint assessment / AAR | Incident Response `PD-WRL-003` | Threat Analysis `PD-WRL-006` |

## Assessment alignment

The rubric dimensions in `facilitator/assessment-aar.md` map to the objectives as
follows; a cell does not need to complete every objective to earn full marks in a
dimension, but the evidence it cites should come from one.

| Rubric dimension | Objectives most exercised |
|---|---|
| Evidence and reproducibility | LO1, LO2, LO3 |
| Reasoning and scope | LO2, LO5, LO6 |
| Timely command reporting | LO7 |
| Collaboration | LO8 |
| Defensive recommendations | LO3, LO4, LO7 |

## Out of scope

The exercise is defensive and synthetic. It does not teach or assess offensive
access, malware reverse engineering (`PD-WRL-002` T0182), live disk or memory
imaging (`PD-WRL-003` T1256 is *requested and adjudicated*, not performed), real
law-enforcement referral, or tool-specific certification. Collection is represented
by simplified exports and a reconstructed sensor PCAP, so packet-level or
filesystem-level tooling depth is intentionally limited. State these limits when
using the mapping for formal training credit.

## Maintenance

Work role and task IDs track NICE Framework Components version 2.2.0 (SP 800-181
Rev. 1). When NIST publishes a new Components version, re-verify the `PD-WRL-*`
IDs and task statements against the [NICE Framework Resource
Center](https://www.nist.gov/itl/applied-cybersecurity/nice/resources/nice-framework)
before reusing this mapping.
