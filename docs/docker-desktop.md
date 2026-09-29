# Container desktop candidate

The container path supplements the published VM; it has not completed whole-event
acceptance. See [Build first](handoff/BUILD-FIRST.md) for the exact build sequence,
checksums, case preparation and runtime mount contract. Do not start an unbuilt image.

`DockerDesktopProvider` scopes Compose operations to an explicit project and refuses
an absent image or an unhealthy desktop. Set RIDGE_PROJECT and RIDGE_DESKTOP_NETWORK
per event; use distinct private per-team volumes and VNC secrets. Build and verify the
image first. The published case is seeded once into each team's writable volume;
restarting preserves participant work. Controller evidence must be mounted read-only
from the actual public release directory, not a frozen copy of initial evidence.

The CI desktop smoke is an isolated build/start/restart test. It does not prove
Guacamole login, Autopsy search, correct Wazuh views, three clients per team or capacity.
Those checks are task N2 in [NEXT.md](handoff/NEXT.md). Native capture and VM artifacts
remain published in Git LFS. Offline bundle publication and AWS remain later gates.
