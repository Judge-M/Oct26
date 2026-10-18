# Team 6 rehearsal defects and blockers

No credentials or secret values are recorded here.

1. **CTFd question route returns HTTP 500 — blocking.** After participant authentication, `/silent-ridge` renders `500 — An Internal Server Error has occurred`. The result persisted after re-authentication in a second isolated CTFd tab. This prevents the question form, every answer submission, and visible `Correct` verification. Evidence: `ctfd-internal-error-team6.png`, `ctfd-500-after-relogin.png`.

2. **Wazuh participant access is unavailable — blocking T06 evidence inspection.** The Team 6 participant login is rejected by Wazuh. The runbook states that Wazuh uses a separate shared read-only runtime credential, which was not part of the public Team 6 role handoff. Evidence: `wazuh-team6-login-error.png`.

3. **IRIS identity drift — integrity risk.** A fresh queue load displayed `Team: team-04` while T06 remained owned by `team-06`. Re-authentication restored `Team: team-06`. No ticket was claimed while the wrong identity was displayed. Evidence: `iris-identity-switched-to-team04.png`, `iris-team06-queue-after-relogin.png`.

4. **T16 claim is rejected while visibly available — blocking T16.** The queue listed T16 as available, but the claim action returned: “Ticket unavailable, another team claimed it, or exercise paused. Reload the queue.” T06 was already held by Team 6, so no other team ticket was attempted. Evidence: `iris-t16-claim-error.png`.

5. **Autopsy launch/file association is unavailable — blocking T16 human evidence inspection.** The Team 6 desktop exposed the prepared evidence directory, but opening `windows-connections.json` produced a Set Default Application dialog with no recommended viewer, and the Autopsy launcher did not open. Evidence: `guacamole-team6-desktop.png` and the desktop launcher state in `guacamole-wazuh-launcher-noop.png`.

6. **Desktop browser launcher fails.** The desktop Web Browser launcher displayed “Failed to execute default Web Browser. Input/output error.” This prevents using the desktop’s coached browser route.

7. **Admin checks not executed.** No facilitator/admin credentials or admin surface were supplied for this continuation, so CTFd, IRIS, Guacamole, and Wazuh admin checks could not be performed without guessing or expanding scope.
