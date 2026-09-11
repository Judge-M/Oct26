# Validation record

Initial local validation: 10 September 2026 (America/New_York; tool logs after
midnight UTC), Windows, bundled Python 3.12 runtime. No repository-specific
AGENTS.md or pre-existing implementation/test requirements were found.

| Check | Result |
|---|---|
| 10 automated evidence/runtime tests | Passed |
| Deterministic regeneration and tamper detection | Passed; same runtime/config |
| Cross-source file hashes, request IDs, sessions and clock offsets | Passed |
| PCAP framing, IPv4 checksum, lengths and timestamps | Passed |
| SQLite forensic artifact integrity and downloads query | Passed |
| Date reconfiguration across initial and late evidence | Passed |
| Five authenticated cells, unauthenticated denial and traversal attempts | Passed over HTTP |
| Cross-cell comments and owner-only status mutation | Passed over HTTP |
| Inject order, repeat release, future-file denial and release visibility | Passed |
| Process restart persistence, export, reset and old-password rejection | Passed automated integration tests |
| Standalone portable server and separate smoke client | Passed before/after inject 1; export passed |
| JavaScript syntax | Passed Node --check |
| Compose configuration parsing | Passed docker compose config --quiet |
| Local Docker build/start | Not executed successfully: desktop-linux engine pipe unavailable, including after attempting Docker Desktop startup |
| Live Jira import/permissions/export | Not executed; no training project supplied |
| Multi-seat lab routing, firewall/TLS and timed human rehearsal | Not executed; hardware/participants unspecified |

The first test run exposed SQLite handles left open during Windows export/reset;
explicit connection closure fixed it and the full suite passed afterward. CI is
configured for Windows/Linux portable tests and Linux container build, health,
HTTP boundaries, release, restart persistence, export and reset. Record the actual
CI result from the PR before rehearsal; configuration alone is not a passing run.

Manual content review confirms each cell has an independent initial evidence path
and useful findings before correlation. Inject 1 resolves payload identity, inject 2
changes containment/version assessment, and inject 3 changes scope/false-positive
reasoning. Automated checks establish internal consistency, not training difficulty;
a timed human rehearsal remains necessary.

Do not describe this initial implementation as live-event validated. Use the README
and preparation checklist to close Docker/Jira/network/human-rehearsal gaps on the
actual host. No student data, runtime credentials or private reference document is
included in the source commit.
