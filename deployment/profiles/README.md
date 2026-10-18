# Deployment profiles

A deployment profile is one private, versioned description of an event deployment.
The schema and validator live in `ridge/deploy/config.py` (`SCHEMA_VERSION = 1`,
frozen for Wave 0). Validate with:

```text
python -c "import json; from ridge.deploy import validate; print(validate(json.load(open('deployment/profiles/example-ten-team-aws.json'))))"
```

The two files here are `profile_kind: example`; they use documentation-only addresses
and are safe to publish. A real event profile must set `profile_kind: production`,
use routable addresses, and stay outside Git.

## Contract

- Profiles carry **no fixed application IDs**: no `iris`, `iris_id`, `ctfd` or
  `ctfd_id` anywhere. Those are resolved after provisioning through
  `resolve_inventory(profile, resolved)`.
- Secrets are **references only** (`env:NAME`, `file:/path`, `vault:path`). Embedded
  secret values are rejected.
- `event.incident_date` (the scenario date) and `event.event_start` (the wall-clock
  event date) are separate fields.
- A missing `roster` generates neutral teams and participant accounts from the
  configured desktops for the legacy fixed-roster path.
- With `registration.enabled: true`, the roster is intentionally empty at boot.
  The host allocator admits up to `registration.max_teams`, creates five
  participant seats per team, and starts exactly three of the predeclared
  desktop slots for each registered team.
- A dynamic profile must declare `max_teams * desktops_per_team` desktop slots.
  `capacity.host` is checked against the full pool so event-day registration
  cannot overcommit memory or CPU.

## Required fields

`schema_version`, `profile_id`, `provider`, `event`, `desktops`, `capacity`,
`addresses`, `secret_refs`, `retention`, `spending`. `roster` is optional. Error
messages from `ProfileError` name the exact JSON field.

`deployment/profiles/example-dynamic.json` is the reference ten-team shape:
five members per team, three GUI-only desktops per team, and a persistent
registration handout at CTFd `/silent-ridge/register`.
