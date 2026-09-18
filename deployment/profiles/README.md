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
  configured desktops.
- `capacity.host` must fit the central services plus one desktop per team; the
  ten-team example is a planning envelope, not a measured host.

## Required fields

`schema_version`, `profile_id`, `provider`, `event`, `desktops`, `capacity`,
`addresses`, `secret_refs`, `retention`, `spending`. `roster` is optional. Error
messages from `ProfileError` name the exact JSON field.
