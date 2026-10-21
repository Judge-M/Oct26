# Deployment profiles

A deployment profile is one private, versioned description of an event deployment.
The schema and validator live in `ridge/deploy/config.py` (`SCHEMA_VERSION = 1`,
frozen for Wave 0). Validate with:

```text
python -c "import json; from ridge.deploy import validate; print(validate(json.load(open('deployment/profiles/example-dynamic-two-host-11-team.json'))))"
```

The files here are `profile_kind: example`; they use documentation-only
addresses and are safe to publish. A real event profile must set
`profile_kind: production`, use routable addresses, and stay outside Git.

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
  Capacity is checked against the full pool so event-day registration cannot
  overcommit memory or CPU. Local slots use `capacity.host`; remote slots name
  a `worker` and require a matching `capacity.workers.<worker>` entry.
- A desktop without `worker` remains local and uses the internal VNC port 5901.
  A remote desktop sets `worker` plus a unique `address`/`vnc_port` pair. The
  corresponding Docker context and remote bind-mount paths live only in private
  `RUNTIME/local.json`; see `docs/multi-host-desktops.md`.

## Required fields

`schema_version`, `profile_id`, `provider`, `event`, `desktops`, `capacity`,
`addresses`, `secret_refs`, `retention`, `spending`. `roster` is optional. Error
messages from `ProfileError` name the exact JSON field.

`deployment/profiles/example-dynamic-two-host-11-team.json` is the current
two-host reference shape: eleven teams, five members per team, three GUI-only
desktops per team, 14 local slots, and 19 `worker-02` slots. Pair it with
`deployment/examples/two-host-11-team.local.example.json`; that host-local file
contains the Docker context, worker paths, Guacamole relay map, and external TLS
paths that do not belong in a reusable profile. The shape is capacity-valid and
representable by the 33-slot Compose pool, but remains performance-uncertified
until the human/load rehearsal passes.

`deployment/profiles/example-dynamic.json` remains the smaller historical
single-host dynamic example. Do not use it as the current event-day profile.
