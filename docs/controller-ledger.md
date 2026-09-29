# Controller visibility

The expanded implementation uses the private integration audit and the public announcement projection described in [expanded operations](expanded-operations.md). Participants can read published announcements, current ownership, earned points and released findings. The complete audit, controller notes, credentials and unreleased evidence are private.

Publish deadline changes explicitly:

```text
python -m ridge.cli announce --operator EXCON-A --text "Revised activity end is 14:40 local."
```

A private note does not notify participants. The expanded exercise has no containment-approval, report or joint-assessment gate.

For historical baseline interpretation only: the old `/api/control` endpoint filtered out private notes and host usernames. Its entire host ledger was never participant-visible. The former documentation claiming otherwise was incorrect.
