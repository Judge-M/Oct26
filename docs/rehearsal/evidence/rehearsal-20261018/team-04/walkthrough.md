# Operation Silent Ridge — Team 4 rehearsal walkthrough

Event: `ridge-oct26-fresh`  
Role: Team 4  
Assigned tickets: T04 and T14  
Rehearsal date: 2026-10-18

## Result

T04 was claimed successfully in IRIS and remains held by `team-04`. T14 was
not claimed because the participant workflow permits one held ticket and T04
could not be completed. CTFd authentication succeeded on the corrected public
hostname, but `/silent-ridge` rendered a visible HTTP 500 error, so none of
the eight questions could be submitted and no `Correct` result was observed.

The IRIS queue and desktop evidence were inspected through the isolated
in-app browser. No credentials or secrets are included in this walkthrough.

## Observed navigation and claim evidence

1. Opened IRIS at `https://desktop-t5pf26o.tail799fee.ts.net:8081`.
2. The supplied `team-04` username was rejected by the live login form. The
   memorable Team 4 username `team4` authenticated and the queue identified
   the participant as `team-04`.
3. Opened the Silent Ridge queue. Before claiming, the page showed Team
   `team-04`, exercise `running`, and T04 available.
4. Claimed T04. The queue then showed `You hold: T04`, T04 active with owner
   `team-04`, and T14 still available.
5. Opened Guacamole at the corrected public hostname. Port root returned a
   Tomcat 404, while the documented `/guacamole/` path opened the Team 4
   desktop session.
6. Opened the desktop `Evidence` shortcut and visually inspected the evidence
   tree. `/evidence/endpoint` contained `events.csv`; `/evidence/prepared`
   contained `windows-task.json`.
7. CTFd login at
   `https://desktop-t5pf26o.tail799fee.ts.net:8083/login` succeeded, but the
   corrected public `/silent-ridge` page returned `500 An Internal Server Error`.
8. The IRIS question link visibly points to the private/raw CTFd address. It
   was not followed through the certificate error; no TLS safety barrier was
   bypassed.

Claim and queue screenshots:

- `01-iris-team04-queue-before-claim.jpg` — T04 available before claim.
- `02-iris-team04-T04-claimed.jpg` — T04 claimed by team-04.
- `03-iris-team04-queue-raw-links.jpg` — claimed state, T14 available, and raw
  private-IP links visible.
- `00-iris-team4-dashboard-queue.jpg` — initial IRIS participant dashboard.

## T04 — Investigate persistence

Evidence route: Autopsy, `/evidence/endpoint/events.csv`, selecting
`endpoint/events.csv`. The coached evidence folder was visible in the Team 4
desktop as `events.csv`.

| Question | Intended answer | Explanation and justification | Submission result | Screenshot |
|---|---|---|---|---|
| T04-Q1 | `BriefSync` | Use the product/application field in the endpoint event record. The matrix identifies the `BriefSync` value as the supported application associated with the record. | Not submitted: CTFd `/silent-ridge` returned HTTP 500; no `Correct` result. | `06-guacamole-team4-endpoint-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T04-Q2 | `brief-viewer.exe` | Use the process/image field from the same endpoint event record. This is the executable named by the coached evidence and matrix. | Not submitted: CTFd HTTP 500; no `Correct` result. | `06-guacamole-team4-endpoint-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T04-Q3 | `user logon` | Use the event-type field. The event is labeled `user logon`; do not infer a broader action from the presence of the executable alone. | Not submitted: CTFd HTTP 500; no `Correct` result. | `06-guacamole-team4-endpoint-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T04-Q4 | `09:08:00` | Use the endpoint event timestamp after applying the documented WS-17 device-time correction once. The matrix gives the corrected visible time. | Not submitted: CTFd HTTP 500; no `Correct` result. | `06-guacamole-team4-endpoint-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |

Limitation: prepared endpoint evidence is limited to collection. Artifact
presence alone does not prove the related action occurred.

## T14 — Inspect acquired task-log records

Evidence route: Autopsy, `/evidence/prepared/windows-task.json`, selecting
`prepared/windows-task.json`. The coached evidence folder was visible in the
Team 4 desktop as `windows-task.json`.

T14 uses the actual acquisition UTC. The T04 WS-17 device-time correction
must not be applied to this acquired task record.

| Question | Intended answer | Explanation and justification | Submission result | Screenshot |
|---|---|---|---|---|
| T14-Q1 | `BriefSync` | Use the task name field in the acquired Windows task record. | Not submitted: T14 could not be claimed while T04 was held, and CTFd was HTTP 500. | `05-guacamole-team4-prepared-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T14-Q2 | `brief-viewer.exe` | Use the task action field; this is the executable named by the acquired task record. | Not submitted: T14 could not be claimed while T04 was held, and CTFd was HTTP 500. | `05-guacamole-team4-prepared-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T14-Q3 | `23:22:01` | Use the task timestamp from the acquired record in actual acquisition UTC. Do not carry over the T04 device-time correction. | Not submitted: T14 could not be claimed while T04 was held, and CTFd was HTTP 500. | `05-guacamole-team4-prepared-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |
| T14-Q4 | `no` | The task record does not contain the requested external-transfer field. Absence of that field is the bounded answer; it is not proof that no transfer occurred elsewhere. | Not submitted: T14 could not be claimed while T04 was held, and CTFd was HTTP 500. | `05-guacamole-team4-prepared-evidence.jpg`, `ctfd-500-silent-ridge.jpg` |

Limitation: this is an isolated native training reconstruction with an actual
acquisition UTC timestamp. It does not replace the historical incident
timeline; provenance and the original hash remain relevant.

## Admin/read-only checks

- CTFd: participant login succeeded, but the public custom event route returned
  HTTP 500. The facilitator login reached the read-only Statistics page, which
  showed 31 users, 10 teams, 0 challenges, and 0 total possible points. No
  admin control was clicked.
- IRIS: the participant dashboard and queue were reachable and showed the
  Team 4 role and T04 ownership. The documented classroom organizer login was
  rejected, so no IRIS admin panel was available. No case, task, or
  configuration mutation was attempted.
- Guacamole: the participant `/guacamole/` session opened the Team 4 desktop;
  the root port path returned 404. The session exposed only the participant
  desktop and no facilitator controls. No connection or permission change was
  attempted.
- Wazuh: the public dashboard loaded in a participant session, showed `No
  results`, and raised repeated `Unable to update UI setting` / HTTP 403
  notifications. The facilitator login then redirected to a health-check view
  whose visible diagnostics included an automatic `Updating
  [timeline:max_buckets] setting...` action. No further admin clicks were made.
- Separate facilitator service: repository documentation describes an
  additional host-only admin service on port 8084. The corrected public
  hostname timed out when checked, so that service was not reachable from this
  participant browser.

## Evidence screenshots

- `04-guacamole-team4-evidence-folder.jpg` — Team 4 desktop `/evidence/` tree.
- `05-guacamole-team4-prepared-evidence.jpg` — `/evidence/prepared/` with
  `windows-task.json` visible.
- `06-guacamole-team4-endpoint-evidence.jpg` — `/evidence/endpoint/` with
  `events.csv` visible.
- `08-wazuh-overview-no-results-403.jpg` — Wazuh overview with no results.
- `09-ctfd-admin-statistics.jpg` — facilitator CTFd Statistics page.
- `10-iris-admin-login-rejected.jpg` — IRIS organizer login rejection.
- `11-guacamole-facilitator-check-desktop.jpg` — Guacamole participant desktop
  surface; no facilitator controls exposed.
- `12-wazuh-admin-health-check-write.jpg` — Wazuh view after facilitator login;
  the preceding AX state showed the automatic health-check setting action.
- `ctfd-500-silent-ridge.jpg` — CTFd custom route HTTP 500.

