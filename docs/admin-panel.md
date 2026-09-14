# Facilitator panel

Run on the controller host from the repository root:

    python scripts/admin_server.py --add-user facilitator-name
    python scripts/admin_server.py

Create a different named account for each facilitator. Passwords are stored for
distribution in runtime/admin-logins.txt; password hashes are separate from
participant credentials. Account creation refuses to overwrite an existing name.
Keep the controller host and runtime private.

Open http://127.0.0.1:8082 on that computer. The service intentionally binds only
to loopback. It is not part of the participant container image or gateway.
Participant passwords and participant bearer tokens do not grant admin access.

The panel supports start/pause/resume, sequential release with typed confirmation,
private notes, published decisions with typed confirmation, full private scenario
documents, ticket/comment review, exports, and explicit cell-login reveal/hide.
Admin identity is taken from the authenticated account, not an entered operator
field. The complete ledger and export retain that identity.

Decision text is published to participants. Notes and clock reasons are private.
Future command briefs, coaching prompts and solutions are admin-only.
Participant data is rendered as text in the panel.

Exports are saved in the repository's private exports directory. Reset and password
rotation require stopping both services and using the existing host CLI. An event
reset creates a new runtime: provision facilitator accounts for the new run.
No browser reset is provided. No remote-admin/TLS deployment is configured.

Validation: use isolated temporary runs for destructive workflow tests. Never
start the actual event clock or release real-run injects merely to test the panel.
