# Jira shared incident workflow

Jira is the intended work surface; this repository does not bundle a Jira license,
provision accounts, or connect automatically to an organization. The Docker board
is a functional offline rehearsal fallback, not a Jira emulator or synchronized copy.
Choose one authoritative ticket surface before start. When Jira is selected, use
the portal only for evidence and use Jira for all updates and action acknowledgments.

In a dedicated training project, an authorized Jira administrator imports
`jira/tickets.csv` with the CSV importer. Map Summary → Summary, Issue Type → an
available Task type, Description → Description and Labels → Labels. Choose the
training project, preview the five rows, and confirm the import. Record the generated
issue keys against cells 1–5; IDs depend on the project and are not hard-coded.
Reimport only into a new project/run or after checking for the five existing labels;
the CSV import is not an idempotent upsert and could create duplicates.

Assign each issue to its cell lead or designated training account. Grant every cell
Browse Projects and Add Comments on the whole training project. Permit owners to
maintain their incident status with the workflow Investigating → Assessment sent →
Closed (or mapped equivalents). In a company-managed project, administrators can
configure transition conditions for assignee/project roles; rehearse the exact
permissions in the chosen Jira project type. If owner-only transitions cannot be
enforced there, document a procedural owner-only convention and controller review.
Do not claim the CSV establishes access control or creates this workflow.

Paste the worksheet template in each issue or save it as the project's description
template. Link the evidence portal's initial files; add released inject links only
when control releases them. Cross-cell comments should cite source + row ID, state
what changes, and link the related issue. The owner reconciles findings in updates;
other cells never need private tickets to contribute.

Before rehearsal, sign in as each cell and verify: five tickets visible, comment on
another cell's ticket succeeds, ownership/status behavior matches the chosen policy,
facilitator material is absent, links resolve from participant workstations, and
exports preserve comments and timestamps. Have two cells post in succession and
confirm both updates persist after logout/login. Record the project URL and key map
privately in the run records.

Cloud Jira requires internet connectivity, so keep it outside the isolated Docker
network. Participant workstations may need a separately approved path to Jira.
Do not open container egress to accommodate it. Only synthetic training content
belongs in tickets. Configure project visibility to the exercise group, and export
work through the organization's Jira export process at ENDEX; confirm comments are
included (issue-list CSV views may omit them). Store that export privately alongside
the portal export. Jira setup, licensing, permissions, network routing, and export
must be rehearsed in the actual tenant; they are not covered by local fallback tests.

Fallback: distribute portal URL plus one account per cell from cell-logins.txt.
The board seeds five tickets, permits all cells to read/comment on all five, and
restricts status changes to the owning cell. Updates are append-only. A shared
cell login attributes to the cell rather than an individual; put initials in text
if local assessment needs them. There is no attachment upload: evidence is linked
by path and worksheets are posted as text. Export SQLite for complete comments;
for analysis use `SELECT * FROM comments ORDER BY id` in a SQLite viewer.

Reference checked 10 September 2026:
[Atlassian CSV import documentation](https://support.atlassian.com/jira-cloud-administration/docs/import-data-from-a-csv-file/).
The importer maps columns to Jira fields; project permission and workflow setup
are separate administrator tasks. UI labels may differ by Jira deployment.
