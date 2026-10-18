# Team 4 rehearsal defects and blockers

1. **Blocking — CTFd custom event route fails on the corrected public host.**
   Login at the public `/login` route succeeds, but the public
   `/silent-ridge` route renders `500 An Internal Server Error`. This blocks
   all eight T04/T14 answer submissions and prevents visible `Correct` results.
   Evidence: `ctfd-500-silent-ridge.jpg`.

2. **Blocking/safety — IRIS emits private-IP links.** The corrected public
   IRIS queue visibly links Questions and help, the scoreboard, and T04's
   question start to `192.168.1.200`. Following the CTFd link produces
   `ERR_CERT_COMMON_NAME_INVALID` because the public certificate does not
   match that raw address. The interstitial was not bypassed. Evidence:
   `03-iris-team04-queue-raw-links.jpg`.

3. **Workflow discrepancy — IRIS Team 4 username.** The supplied
   `team-04` username was rejected by the live IRIS login form. The memorable
   `team4` username authenticated and the queue mapped it to visible team
   `team-04`. The password is intentionally omitted from this report.

4. **Desktop usability — coached native tools are incomplete.** The Team 4
   desktop exposes an Autopsy shortcut, but the Application Finder returned no
   Autopsy result. Opening `events.csv` also showed no recommended CSV
   application. The evidence folders were still visually reachable, but the
   coached Autopsy/CSV inspection could not be completed as a human through
   the supplied desktop image. Evidence: `04-guacamole-team4-evidence-folder.jpg`,
   `05-guacamole-team4-prepared-evidence.jpg`, and
   `06-guacamole-team4-endpoint-evidence.jpg`.

5. **Guacamole path usability — root 404.** The published `:8082` root
   returned a Tomcat 404; the application worked at the documented
   `/guacamole/` path. This is recoverable but should be reflected in the
   participant landing instructions.

6. **Wazuh read-only surface — no data and repeated 403 UI-setting errors.**
   The public dashboard loaded but showed no results and repeated
   `Unable to update UI setting` notifications with HTTP 403. Evidence:
   `08-wazuh-overview-no-results-403.jpg`.

7. **IRIS admin check unavailable.** The documented classroom organizer login
   was rejected by the live IRIS login form. The participant queue remained
   reachable, but no IRIS facilitator/admin check could be completed.

8. **Wazuh admin check is not non-destructive.** The organizer login succeeded,
   but the post-login health-check page visibly performed an automatic
   `Updating [timeline:max_buckets] setting...` action. No further admin
   controls were clicked, and the final completion state of that automatic
   write was not independently verified. This should be fixed so a health
   check cannot write configuration during a read-only rehearsal.

9. **Admin reachability — separate facilitator service is not participant-
   reachable.** The repository describes the facilitator service as host-only
   on port 8084; the corrected public hostname timed out. No event
   configuration, password, ticket, or data was intentionally changed.

