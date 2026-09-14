# Browser analysis workspace

Sign in, open Analysis workspace, select a released artifact, and choose Open evidence.

- CSV and JSON/JSONL: search across fields and sort a column in either direction.
  Searches operate on the loaded records, not on files you have not opened.
- SQLite: inspect the displayed table definitions, then enter a read-only SELECT.
  The query runs against that evidence database only. Other files and databases
  cannot be attached. Source databases are opened read-only.
- PCAP: inspect packet timestamps, addresses, ports, sizes, and reconstructed
  sensor payloads. This viewer supports the exercise's Ethernet/IPv4/UDP PCAP,
  not full Wireshark decoding or arbitrary capture formats.
- Text: read the artifact directly. No executable content is run.
- SHA-256: compare the original artifact's digest with another digest.
- UTC calculator: enter an ISO timestamp with Z or a timezone offset and a
  correction in seconds. The calculator never alters the source evidence.
- Cite: adds the file, original digest, record, and active query/filter to the
  current ticket draft. Review your assessment and save the update to preserve it.
  Unsaved drafts and viewer state are not assessment records.

The viewer limits files to 5 MB and results to 1,000 rows. SQLite queries also
have execution and result-size limits. Truncation is shown explicitly. Downloads
remain available for independent analysis. No external services or packages
are required by these tools.

Only runtime/public artifacts are accepted, after authentication. Instruction
documents, integrity manifests, and command briefings are not analysis inputs.
Private vault, controller files, and unreleased injects are outside the accessible
root. The tools do not identify suspicious rows or produce conclusions.

Validation: 23 Python tests passed locally, including released-file boundaries,
unauthenticated access rejection, unchanged database bytes, blocked SQL writes,
ATTACH/PRAGMA/extension rejection, expensive query interruption, and packet decoding.
Headless Edge verified filtering, citations, SQLite query results, UTC correction,
and desktop/tablet/mobile layout. Container and multi-seat event validation for
these additions remain outstanding.
