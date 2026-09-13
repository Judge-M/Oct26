# October 2026 company cyber lane

This lane trains an incoming SOC shift to investigate a disclosure affecting a
fictional patrol already in the field, report credible risk with incomplete evidence,
and recommend defensive actions through simulated command. It is a cooperative
CND/DFIR simulation. No offensive access, live adversary systems or real personnel
are part of the exercise.

## Planning assumptions and ownership

`config.json` is the planning authority. `python scripts/schedule.py` validates it
and prints the run schedule. Duration 180 selects the standard profile; duration
120 selects the compressed profile, including all reporting and closure times.
Optional `timing` overrides are validated as a complete ordered schedule. Other
durations require all timing fields. Unknown fields, overlapping deadlines and
insufficient response windows are rejected before initialization.

Initialization writes the resolved configuration to runtime/run-config.json,
controller schedule to runtime/vault/controller-schedule.md, and participant schedule
to runtime/public/common/schedule.md. It also renders handout deadlines and inject
headings from the same schedule. Source handouts contain template fields; distribute
the rendered copies. Configuration changes require a new run. The scenario clock
starts at 09:30Z and advances with exercise elapsed minutes; historical evidence
remains on its original timeline. The actual UTC clock is recorded separately.

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
tasks, terrain, routes or instructor conduct.

## Cyber schedule and joint report

Use the generated controller and participant schedules for every deadline. They
cover briefing, initial reports, three staged injects and responses, contributions,
joint assessment, investigation closure, AAR and export. Record start, pause and
resume in the controller ledger. A pause freezes elapsed time and shifts actual UTC
deadlines; it never rewrites historical evidence. For late releases, record an
explicit revised response deadline as a controller note and announce it to all cells.

The hunting reporter owns the joint assessment on ticket 5 (the hunting Jira issue
or fallback ticket 5). Each cell posts its contribution there by `cell_handover`,
linking its evidence and own ticket/comment IDs. The hunting reporter posts JOINT
ASSESSMENT by `joint_report`, reconciling facts and retaining unresolved differences.
The controller records receipt and any decisions in the external ledger. The five
specialist tickets remain open for their own investigations; there is no sixth cell.

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
