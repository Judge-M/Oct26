# Ten-team rehearsal worksheet

Record observations here during a beginner rehearsal. Estimated columns come from `docs/workload.md` and are arithmetic; the measured columns are the evidence.

Duration target: 360 minutes. Estimated makespan: 585 minutes. Estimated team-minutes: 1300 (1300/team).

## Per-team summary

| Team | Estimated tickets | Estimated minutes | Active minutes | Idle minutes | Help used | Tool failures | Notes |
|---|---|---|---|---|---|---|---|
| team-01 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-02 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-03 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-04 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-05 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-06 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-07 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-08 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-09 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |
| team-10 | T01, T02, T03, T04, T05, T06, T07, T08, T10, T09, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20 | 1300 | | | | | |

## Per-ticket observations

| Ticket | Tool | Prerequisites | Estimated minutes | Team | Start | End | Active | Idle | Help used | Tool failures | Blocked by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T01 | Wireshark | - | 65 | | | | | | | | |
| T02 | Wireshark | - | 65 | | | | | | | | |
| T03 | Autopsy | - | 65 | | | | | | | | |
| T04 | Autopsy | - | 65 | | | | | | | | |
| T05 | Autopsy | - | 65 | | | | | | | | |
| T06 | Wazuh | - | 65 | | | | | | | | |
| T07 | Wazuh | T06 | 65 | | | | | | | | |
| T08 | Autopsy | - | 65 | | | | | | | | |
| T09 | Linux file manager | T08 | 65 | | | | | | | | |
| T10 | Wazuh | - | 65 | | | | | | | | |
| T11 | Wazuh | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10 | 65 | | | | | | | | |
| T12 | Wazuh | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10 | 65 | | | | | | | | |
| T13 | Autopsy | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10 | 65 | | | | | | | | |
| T14 | Autopsy | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10 | 65 | | | | | | | | |
| T15 | Autopsy | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10 | 65 | | | | | | | | |
| T16 | Autopsy | T11, T12, T13, T14, T15 | 65 | | | | | | | | |
| T17 | Cutter | T11, T12, T13, T14, T15 | 65 | | | | | | | | |
| T18 | Cutter | T11, T12, T13, T14, T15 | 65 | | | | | | | | |
| T19 | Linux file manager | T01, T05, T11, T12, T13, T14, T15 | 65 | | | | | | | | |
| T20 | Wazuh | T07, T09, T11, T16, T17, T18, T19 | 65 | | | | | | | | |

## Rehearsal questions

- Did measured active time per team reach the duration target?
- Which dependencies stalled teams, and for how long?
- Which questions were answered from a free walkthrough without investigation?
- Which duplicate or yes/no questions should be replaced or deepened?
- Which tool instructions failed, and what is the observable fix?
