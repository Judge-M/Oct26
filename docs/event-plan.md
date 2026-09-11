# October 2026 company cyber lane

This lane trains an incoming SOC shift to investigate a disclosure affecting a
fictional patrol already in the field, report credible risk with incomplete evidence,
and recommend defensive actions through simulated command. It is a cooperative
CND/DFIR simulation. No offensive access, live adversary systems or real personnel
are part of the exercise.

## Planning assumptions and ownership

`config.json` proposes 15 October 2026, 180 minutes, 20 participants (four per cell),
and injects at elapsed minutes 35, 75 and 115. These are configurable assumptions,
not confirmed event arrangements. The cyber lane owner must confirm the actual date,
attendance, duration, skill mix, hardware and Jira availability before rehearsal.
Changing the date and reinitializing regenerates all evidence timestamps. Changing
duration or inject minutes changes the controller's schedule, not automated release;
preserve at least 10 minutes after injects 1/2 and 15 after inject 3 for reporting.
No absolute calendar scheduling runs in the application.

Proposed host: Linux container engine with 2 CPU cores, 4 GB RAM, 2 GB free disk,
plus one browser per cell (prefer one per analyst) on an isolated training network.
The service is small; the rehearsal must confirm performance on actual equipment.
Wireshark, a SQLite viewer and a text editor suffice; Python 3.12 can replace GUI
analysis tools. No Kali, malware, exploitation framework or paid forensic suite is
required. Beginner cells receive hint 1 early; experienced cells must test alternatives.

Staff: one lead controller playing command, one technical facilitator maintaining
the host and evidence, and ideally two roving coaches (roughly two to three cells
each). Minimum two staff: combine coaching with control and technical duties;
record reduced observation coverage. Each cell has an analyst, recorder and reporter;
the fourth member checks conclusions. With 10 participants, pair analysts and combine
recorder/reporter; with 30, add paired evidence checks rather than competitive teams.

## Two-day context and optional connections

Day 1: everyone attends IPOE and LandNav under those instructors. Day 2: personnel
split between this cyber lane and reporting training. The cyber lane requires no
Day 1 product or product from the other Day 2 lane.

Optional offers to the other instructors: reuse the fictional patrol name LANTERN,
the need to distinguish observations from assessments, and the abstract AMBER/BLUE
sector labels. Reporting instructors may optionally use the cyber report template
with their own facts. These are narrative options, not prescribed objectives,
tasks, terrain, routes or instructor conduct. Do not use the attached Word document's
targeting tasking in this lane.

## Proposed cyber schedule

| Elapsed minute | Activity | Output / owner |
|---|---|---|
| 0–10 | Safety, access, incoming shift handover | Lead confirms all five cells connected |
| 10–25 | Independent triage | Each cell posts first evidence-based report at 25 |
| 25–35 | Cross-cell sharing | Reporter checks another ticket; coach logs observations |
| 35 | Inject 1 | DLP body; command exposure report due at 45 |
| 45–65 | Correlate file identity and access scope | Updated shared exposure assessment |
| 65–75 | Brief pause / controller collection requests | Lead resolves workflow problems |
| 75 | Inject 2 | Persistent session and version change; recommendation due at 85 |
| 85–115 | Containment and competing hypotheses | Written requests with costs and verification |
| 115 | Inject 3 | Broader scope and false positive; priorities due at 130 |
| 130–150 | Final synthesis | Joint report and five ticket handovers |
| 150–175 | AAR | Evidence-based discussion and improvement actions |
| 175–180 | Export and close | Technical facilitator secures work and shuts down |

For 120 minutes: brief 0–10, initial report 20, injects 25/50/75, final 95,
AAR 100–120. For 240 minutes: keep decision deadlines early and spend additional
time on independent query reproduction, recovery planning and AAR. State the
chosen elapsed schedule before distributing handouts; the 09:30Z scenario start
and relative evidence facts stay fixed.

## Preparation checklist

- T−14 days: confirm assumptions, staff and accessibility needs; choose Jira or
  fallback; inspect public-repository answer exposure; decide whether a private
  variation is required for participants who have seen the material.
- T−7 days: build images while internet is available; rehearse all commands; verify
  access from each seat; preload offline analysis tools; print handouts if desired.
- T−2 days: run tests and a timed rehearsal with one person per cell; confirm each
  cell can independently produce its first report; import Jira tickets into a fresh
  training project; test cross-cell permissions; record tool versions and image ID.
- T−1 day: reset; verify only initial files are public; issue cell credentials privately;
  check clock conventions; prepare controller-only copies of solutions and injects.
- T−30 minutes: verify service health, download hashes, five accounts, projector or
  command communication method, facilitator staffing and backup host/export location.
- After: export private participant work, conduct AAR, stop service, retain or dispose
  of runtime archives under the event owner's retention decision.
