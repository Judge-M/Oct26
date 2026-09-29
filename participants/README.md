# Participant materials

Read [`handover.md`](handover.md) first — it is the fictional shift handover that
opens the exercise. [`cells.md`](cells.md) explains how your team actually works
(claim IRIS tickets, answer in CTFd, findings publish automatically), and
[`worksheets.md`](worksheets.md) is an optional notes template for your team
workspace.

> **Note for maintainers:** `handover.md` is also a *timing template* — the
> legacy evidence generator (`scripts/generate.py`) copies this folder and
> substitutes the `{{initial_report}}`, `{{cell_handover}}` and
> `{{joint_report}}` placeholders with computed minutes. Keep those
> placeholder tokens intact when editing the fiction, or the generator's
> integrity tests will fail. The current IRIS/CTFd mechanics in `cells.md`
> are authoritative for how the event runs; the older cell/report wording in
> the handover narrative is retained for fixture compatibility.
