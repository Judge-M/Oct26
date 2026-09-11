# Facilitator-only scenario and ground truth

Do not distribute this file to participants. A public GitHub repository cannot hide
these answers. Serve only `runtime/public`; never give the repository or image-build
context to participants as their evidence package. For an assessment where prior
access matters, prepare a private variant and rehearse it; changing names alone does
not protect conclusions. This public version is best treated as a coached exercise.

## Implementation decisions

The user-authorized SOC disclosure scenario is the sole narrative foundation.
The attached Operation Silent Ridge document was reviewed as reference; its separate
targeting, location-finding and exploitation tasking was not adopted. Silent Ridge
is a working event name only. All accounts, hosts, patrol names, plan details and
technical events here were invented for this defensive exercise. No real route,
coordinates, unit, person or adversary is represented.

Fictional clerk m.ellis uses WS-17 and DOCS-1; planner r.chen uses WS-22. The program
brief-viewer.exe is modeled as an unauthorized session-stealing utility, but no
executable or operational attack procedure exists in the repository. It downloads
plan-v3 using session S-41 and sends its body out through a lab TLS-inspecting proxy.
The same session is refreshed remotely. Initial evidence supports this assessment
but does not establish the original delivery mechanism or human attribution.

LANTERN's v3 movement brief contains abstract sector AMBER, 10:00–11:00Z window and
check-in word CEDAR. v4 changes the sector and window but retains the word. Command
alone decides any patrol response. No physical harm, adversary intent or actual
use of exposed information is assumed. WS-31 is an unresolved scope lead; its
inventory match is not proof of compromise. WS-22's similar task name is benign.

## Canonical timeline (configured exercise date, UTC)

| UTC | Ground truth | Participant support / release |
|---|---|---|
| 08:40 | m.ellis completes MFA, S-41 issued on WS-17 | I101 initial |
| 08:45 | WS-31 has suspicious task inventory; WS-22 approved task shares name | H201/H202 inject 3 |
| 08:50 | WS-31 endpoint telemetry stops | coverage.csv initial |
| 08:57 | Viewer downloaded | browser.sqlite initial |
| 08:58 | Viewer starts on WS-17 | E101 clock corrected; H101 initial |
| 08:59 | Viewer accesses browser session store | E102 clock corrected; no token content |
| 09:03 | S-41 refreshed externally without fresh MFA | I102, H102 initial |
| 09:04 | Viewer downloads plan-v3 and creates cache | N101/S101 req-71; E103 hash initial |
| 09:04:30 | Remote S-41 request for roster denied | S102 initial |
| 09:05 | Remote password login fails | I103 initial; distinct from session success |
| 09:06 | WS-17 uploads plan-v3 body | N102, corrected E104, H103; exact body inject 1 |
| 09:07 | Remote endpoint acknowledges request | N103 initial; not proof of a human reading |
| 09:08 | Viewer registers BriefSync persistence | E105 corrected, H104 initial |
| 09:10 | v4 supersedes v3 | planner confirmation inject 2 |
| 09:12 | Authorized planner reads v4 | N104/S103/H105 initial |
| 09:14–09:18 | DOCS collector gap | server collection note initial |
| 09:20 | Password reset, sessions remain valid under fictional policy | I104 and policy initial |
| 09:26 | External S-41 refresh still succeeds | I201 inject 2 |
| 09:30 | Incoming shift begins | handover |

WS-17 event timestamps are 120 seconds fast, consistently; subtract two minutes.
The browser export, SIEM and other sources already use normalized UTC. Avoid a
second correction. The event-day assumption shifts calendar dates together.

Initial evidence proves successful document delivery to WS-17 and subsequent egress
of the same size; it does not prove identical payloads until the DLP body arrives.
After inject 1, the matching SHA-256 and req-72 establish transmission of v3 from
the monitored workstation to the example external destination. This does not prove
who received or read it, nor that v4 or the roster was disclosed elsewhere.

Intentional gaps: initial delivery path, token contents, human attribution, activity
inside the DOCS audit gap, WS-31 runtime activity, uncollected systems and actual
use of disclosed information. These remain gaps at ENDEX unless expressly addressed
by a controller response in the action ledger. Do not invent forensic confirmation.
