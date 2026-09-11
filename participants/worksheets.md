# Investigation and reporting templates

Copy these sections into your cell's Jira ticket (or the rehearsal board).

## Evidence handling log

| Artifact path | SHA-256 at receipt | Collector / receipt UTC | Working-copy location | Tool and version | Changes made |
|---|---|---|---|---|---|
| | | | | | |

Keep the downloaded original read-only and analyze a copy. Compare hashes with
SHA256SUMS.json in the same release package (`Get-FileHash -Algorithm SHA256` on
PowerShell, `sha256sum` on Linux). A mismatch is a collection issue: notify control,
retain both versions, and do not silently replace evidence. Record every derived
filter or SQL query so another cell can reproduce it. Never upload evidence to
public analysis services. Cite filenames and stable row IDs, not screenshots alone.

## Analysis worksheet

Question / hypothesis:

| UTC time (normalization recorded) | Source and row ID | Observation | Interpretation and confidence | Alternative explanation | Missing evidence / next test |
|---|---|---|---|---|---|
| | | | | | |

Scope table: host / account / object; confirmed, assessed, or unknown; evidence;
coverage limitations; requested collection; responsible cell.

## Ticket update

Exercise elapsed time / author / cell:

Confirmed facts (filename + row IDs):

Assessment and confidence (high / medium / low, with reason):

Contradicting evidence and alternatives:

Potential impact to LANTERN:

Recommended defensive action; rationale; dependency; availability cost:

Unknowns; request to another cell; next test; next update time:

## Initial command report (60 seconds)

As of [UTC / elapsed time], we confirm [facts]. We assess [risk] with [confidence]
because [evidence]. We cannot yet establish [gap]. We recommend exercise control
consider [defensive action] with [tradeoff]. We need [decision/collection] by [time].
Next update at [time].

## Action request and acknowledgment

Request ID / requesting cell / submitted elapsed time:

Proposed action and affected fictional systems:

Expected benefit / disruption / evidence-preservation plan / rollback:

Controller acknowledgment, decision and effective exercise time:

Observation needed to verify success:

A request is not an executed action. Only controller acknowledgment changes the
simulation state. Record the controller's response in the shared ticket.

## Final shift handover

Incident summary and exposure boundaries; normalized timeline with citations;
current scope; actions requested versus acknowledged; containment verification;
unresolved risks; recovery priorities; collection owners and next deadlines.
Include one paragraph revising an earlier assessment in light of new evidence.
