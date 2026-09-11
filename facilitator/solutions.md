# Facilitator-only exercise solutions and graduated hints

Require citations, reproducible analysis and justified uncertainty. These examples
are minimum findings, not a mandatory wording or a requirement to use one tool.

## 1 Network forensics

Task: reconstruct download/egress sequence, evaluate disclosure evidence and tell
command what the network can establish independently. Filter proxy rows with an
external destination or `/files/`, join by request IDs, compare body sizes and UTC.
Open sensor.pcap with Wireshark (`udp.port == 514`) or tshark; inspect N101–N104 in
syslog payloads and compare packet times to CSV. The PCAP has 24 packets and valid
Ethernet/IPv4/UDP framing but is a reconstructed sensor export.

Expected: N101 returns plan-v3 at 09:04; N102 uploads the same number of bytes to
198.51.100.77 at 09:06; N103 is an acknowledgment. D01 maps the example domain.
Initial high-confidence egress observation supports medium-confidence disclosure
assessment. Equal size and HTTP 201 alone do not establish payload identity. Inject 1
DLP req-72 hash equals server catalog and endpoint cache, raising confidence in
exact v3 transmission. v4 traffic N104 is internal and on a different workstation.

Alternative: an authorized upload or unrelated same-size body. Ask for approved
egress purpose and DLP content; the released body resolves identity, not intent or
human receipt. TLS reconstruction is not a complete original network capture.
Recommend preservation and scoped egress control alongside identity/endpoint actions.

Hints: (1) Separate internal and example external destinations. (2) Compare N101
and N102 and ask what equal lengths fail to prove. (3) After release, hash dlp-body.txt
and join req-72 with DLP metadata; report the remaining attribution gap.

## 2 Endpoint forensics

Task: normalize time, explain execution chain, identify potential persistence and
request defensible preservation/containment. Query the SQLite downloads table:
`SELECT start_time_utc,url,target_path FROM downloads ORDER BY start_time_utc;`
Subtract 120 seconds from events.csv device_time only, yielding E101 08:58, E102
08:59, E103 09:04, E104 09:06, E105 09:08. Compare the cache SHA-256 to catalog.

Expected: browser-launched unsigned viewer, session-store access, matching cached
movement file, external connection and BriefSync scheduled task justify a strong
compromise assessment for WS-17 and a persistence investigation. Browser URL records
a download location, not proof of the original lure or human intent. No executable
or full disk/memory image is supplied, so reverse engineering is out of scope.

Alternative: authorized viewer or session backup utility; request approval/signature
records and task definition. The correlation with unauthorized file egress makes
benign explanation less plausible, but no token bytes prove the theft mechanism.
Recommend isolation with availability coordination and preservation before rebuilding.

Hints: (1) Read clock.txt before ordering events. (2) Compare process ancestry and
the cache hash. (3) E102 precedes I102 after correction; E105 aligns with H104, but
sequence alone does not prove causation. State that limit explicitly.

## 3 Identity and authentication

Task: reconstruct S-41 use, interpret MFA and distinguish credential actions from
session containment. Group auth.csv by session and order times. I101 is fresh MFA
on WS-17; I102 refreshes the same session from the external address. I103's failed
password login does not undo I102's successful refresh. I104 resets the password.

Expected: high-confidence anomalous session use, plausible session reuse/theft,
no approved egress/VPN explanation in supplied policy. `previous_claim` does not
mean an attacker completed fresh MFA. Under the fictional policy, resetting the
password leaves S-41 valid. I201 explicitly demonstrates later successful refresh.
Recommend explicit revocation plus endpoint containment and credential review;
verify results and avoid declaring containment solely from reset success.

Alternative: approved roaming or proxy use; policy contradicts that for this address
but IP still cannot identify a person. Initial token delivery mechanism is unknown.
All initial rows alone support meaningful independent reporting before inject 2.

Hints: (1) Group by session rather than failed logins. (2) Read the policy distinction
between reset and revocation. (3) Compare I102 and I201 with I104 and label the latter
refresh historical if cells have already recommended a later revocation.

## 4 Server and data access

Task: bound disclosure scope using response codes, byte counts, catalog metadata and
collection limits. Join access.object to catalog.object. S101 successfully returns
plan-v3 to WS-17, correlating req-71 with N101. S102 denies roster-v2 with zero bytes;
metadata reads by svc-index are ordinary indexing, not roster body disclosure.
S103 returns v4 to authorized r.chen on WS-22 at 09:12.

Expected: initial confirmed v3 delivery to workstation, no evidence of roster body
delivery in this log, and no basis for enterprise-wide absence claims because of
the 09:14–09:18 gap and uncollected sources. Inject 1 confirms external transmission
of v3 via hash. Inject 2 establishes v3's movement details are superseded while
CEDAR remains current: exposure is narrowed, not eliminated. Request simulated
command review of retained information, not operational patrol instructions.

Alternative: authorized planner activity explains v4 access; S101 alone could be
legitimate clerk use. Cross-cell correlation changes that assessment. Lack of v4
egress in these records is not proof v4 was never exposed anywhere.

Hints: (1) Separate 200 and 403 before counting objects. (2) Join versions and hashes,
not filenames alone. (3) Compare the version-comparison fields individually; the
retained check-in word prevents an unsupported all-clear.

## 5 Threat hunting and enterprise correlation

Task: test “WS-17 activity belongs to one incident” and “the compromise is confined
to WS-17.” Parse siem.jsonl, group by host/user, sort UTC, inspect rare egress and
unsigned processes, and compare coverage before interpreting absence.

Expected: H101–H104 independently support a linked WS-17 execution/session/egress/
persistence hypothesis. H105 on WS-22 is consistent with approved planning work.
The normalized SIEM timestamps align with the corrected endpoint timeline. WS-31
is unobservable after 08:50 and cannot be cleared. Inject 3 adds an inventory lead
on WS-31, while H202 demonstrates why matching BriefSync by name over-scopes.

Query example: filter rows where `host == 'WS-17'`, sort by `time`, then separately
enumerate coverage rows with `offline` or `not collected`. For inject 3 compare
artifact + path + publisher, not artifact name alone. This yields an explicit matrix:
WS-17 strongly supported; WS-31 suspected/pending collection; WS-22 observed benign
comparator; DOCS-1 affected data service with no demonstrated host compromise.

Alternative: common authorized software rollout could explain names; divergent
paths/publishers and missing telemetry require collection, not blanket conviction.
Do not equate the incident's affected data service with malware on that server.
Final report should assign owners to outstanding evidence requests and avoid an
enterprise all-clear.

Hints: (1) Read coverage before counting matching hosts. (2) Compare normalized H
timestamps with E clock correction. (3) H201 is a lead; H202 is a counterexample to
a name-only detection. Ask what observation would confirm or refute WS-31 compromise.
