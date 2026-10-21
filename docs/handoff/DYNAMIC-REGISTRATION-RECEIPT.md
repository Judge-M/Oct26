# Dynamic registration implementation receipt

## Objective

Replace the fixed team roster with a self-service event entry point whose team
count is bounded by validated host resources and the declared desktop pool. The
current pool supports up to eleven teams of five. A team registers once, receives a durable retrieval link,
and is assigned three GUI-only desktop slots:

- two Autopsy/evidence-browser desktops;
- one Wireshark/Cutter/Linux evidence-tools desktop.

CTFd, IRIS, Wazuh, Guacamole, and the event services remain centralized. The
participant laptops use their browsers for those services; Guacamole is used only
when a task needs one of the assigned GUI desktops.

## Implemented flow

1. The CTFd integration serves `/silent-ridge/register` with the participant brief,
   service overview, and registration form.
2. Registration is stored in a private SQLite database mounted at
   `/registration/registrations.sqlite`. Reservation is atomic and capped at
   `max_teams`; no participant request receives Docker access.
3. The host-side registration worker claims pending registrations, starts exactly
   the assigned three slot services, creates the CTFd and IRIS identities, grants
   the team those three Guacamole connections, and marks the handout ready.
4. The retrieval page shows the team’s CTFd, IRIS, and Guacamole credentials plus
   the three desktop roles and links. The access code is stored hashed; the
   retrieval URL is the team’s durable bookmark for the event.
5. The desktop Compose file predeclares a 33-slot capacity pool but starts no
   dynamic desktops at initial event startup. Registration lazily starts only the
   three slots assigned to that team.

## Main files

- `ridge/registration.py`: persistent allocator and credential handout model.
- `integrations/ctfd_silent_ridge/__init__.py`: public landing and retrieval pages.
- `ridge/deploy/registration_worker.py`: host-side provisioning worker.
- `ridge/deploy/local.py`: dynamic lifecycle, slot startup, application identity,
  Guacamole, and state integration.
- `deployment/expanded/compose.desktops.yaml`: 33 lazy-start desktop slots.
- `deployment/profiles/example-dynamic.json`: capacity-validated dynamic example profile.

## Validation performed

- Targeted registration, state, profile, CTFd, and IRIS tests: passing.
- Python compilation for changed registration/deployment/integration modules:
  passing.
- Full test discovery should be run with a writable Windows temporary directory;
  the default sandbox temp location is not writable in this environment.
- Compose YAML tests remain dependency-gated when PyYAML is unavailable.

## Explicit limits and operational notes

- The original implementation used one Docker host. Optional named desktop
  workers now extend the same lazy-start pool through SSH-backed Docker
  contexts; see `docs/multi-host-desktops.md`. Single-host profiles remain the
  default.
- Recovery schema 1 does not archive named volumes on remote workers, so
  `down --volumes` refuses to run while workers are configured. Central state
  remains covered; export or preserve worker workspaces separately.
- Existing ticket/answer semantics remain unchanged. This removes fixed team
  provisioning; it does not yet convert the challenge into independent per-team
  copies of all 80 globally unique tickets.
- The dynamic profile is a fresh-runtime path. Do not point it at an old static
  roster database without backing up and intentionally migrating that state.
- No live event deployment, DNS change, certificate change, or password rotation
  was performed by this source change.
