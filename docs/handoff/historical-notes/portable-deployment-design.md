# Silent Ridge: local and temporary AWS deployment

## Decision

Target 10 teams and approximately 30 participants, including one shared desktop
per team. Use a single active deployment and portable, tested recovery packages.
Local hosting and AWS run the same application versions and configuration schema.
AWS resources exist only for the rehearsal or event, unless the operator explicitly
chooses to keep a standby environment.

This is a proposed deployment contract, not an implemented launcher. Repository
baseline: merged PR #10, commit `fa4ed1c`. No cloud resources or packages were
published during this assessment.

## What to distribute

1. GitHub Packages / GHCR: versioned custom integration, IRIS and CTFd images,
   linked to the repository with OCI source labels. Build and test before
   publishing. Deploy by digest, not a mutable `latest` tag. Never bake credentials,
   participant records, solution evidence or private incident exports into images.
2. GitHub Release: launcher, Compose configuration, AWS infrastructure templates,
   release lockfile, checksums and operator instructions. The lockfile ties every
   application image, configuration schema and desktop build to one release.
3. Private exercise bundle: generated evidence, solutions, prepared Autopsy cases,
   desktop artifacts and offline dependencies, with a verified manifest. Large
   private assets need a separate artifact store or local distribution disk.
4. Desktop builds: use one provisioning recipe to produce a tested local VM
   artifact and an AWS AMI. An AMI is region-specific; a local VM disk is not
   automatically a bootable EC2 image. Bake tools and initial evidence ahead of
   time so event launch does not install Autopsy or download large datasets.

The images should appear under the repository's Packages section. Initial GHCR
packages default to private; choose visibility deliberately after the first push.

## Topology

| Component | Local | AWS |
|---|---|---|
| Control services | Linux host running Docker Compose | On-Demand Linux EC2 host running the same Compose release |
| IRIS, CTFd and databases | Private service networks and durable local volumes | Private service networks and encrypted EBS storage |
| Wazuh indexer/dashboard | Dedicated allocation; isolate if measured contention requires it | Separate EC2 host if measurements justify it |
| Team desktops | 10 VMs from the validated template | 10 EC2 instances from the validated AMI |
| Browser access | TLS gateway to IRIS, CTFd and Guacamole | Same gateway and application routes |
| Recovery bundle | Encrypted copy on another device/site | Encrypted copy downloaded locally, optionally retained in private S3 |

Do not choose final instance sizes before measuring a representative Autopsy case
and 30-user rehearsal. Record peak memory, CPU, evidence/case disk growth, indexer
heap, concurrent display responsiveness and restore duration. Account for all ten
desktops in the cost estimate. Prefer On-Demand compute for the live event; avoid
interruptible capacity until interruption recovery is an accepted exercise feature.

AWS desktops must be reachable only from the Guacamole gateway on the required
display port. Databases and the integration API are never public. Prefer private
desktop subnets. If using outbound NAT, explicitly include its hourly and transfer
costs; do not silently add NAT gateways, load balancers or managed databases as
defaults. A baked offline desktop reduces its need for Internet access.

## Operator experience to implement

The following commands specify the intended interface; they do not exist yet:

```text
ridge deploy local --event exercise.yaml
ridge deploy aws --event exercise.yaml --region REGION
ridge doctor
ridge start --operator EXCON-A
ridge move aws --backup /private/event-backup
ridge move local --backup /private/event-backup
ridge destroy aws --verified-backup /private/event-backup
```

First-use configuration collects team names, domains/TLS, desktop provider,
artifact location and capacity. Deployment generates distinct secrets and creates
IRIS users/case/status mappings, CTFd teams and Guacamole connections idempotently.
New deployments start paused. A failed health or identity check prevents event
start. Participant URLs remain stable through a configured gateway/DNS switch.

`deploy aws` should present a resource inventory and estimated recurring costs
before creation, track every created resource in one event stack, report bootstrap
failure clearly, and support cleanup after partial creation. AWS credentials stay
outside the release bundle and use the operator's configured credential provider.

## Moving between hosts

This is a coordinated maintenance operation with downtime. It is not live
replication or automatic failover. Planned movement can preserve all committed
progress; disaster recovery is limited to the most recent complete backup.

1. Block new participant traffic, pause the source event and drain delivery.
2. Acquire the existing export fence and create the application audit export.
3. Quiesce application and desktop writes. Take compatible native database backups
   or clean stopped-volume backups; include the SQLite ledger and any WAL state
   consistently. Capture Wazuh through a supported snapshot/restore procedure.
4. Capture uploads, released evidence, private vault, configuration, required
   secrets, Guacamole database, and each team's Cases/Workspace/Scratch. Close
   Autopsy before copying its case databases. The three-system JSON export alone
   is insufficient for restoring the complete event.
5. Encrypt the recovery bundle, hash its complete inventory and transfer it off
   the source host. Preserve the exact release/image identities.
6. Restore the destination in isolation and paused. Verify identities, receipt
   watermarks, evidence hashes, native database health and all team desktops.
7. Fence the old deployment from participant writes before switching the gateway
   or DNS and explicitly starting the destination. Never run both writable.
8. Keep the old source stopped until destination acceptance. Once the destination
   accepts new writes, returning to the old snapshot would lose that progress;
   moving back requires a new coordinated backup.

For an unexpected source outage, first establish that the source cannot resume
serving writes. Only then activate a restored backup. Automatic DNS failover alone
cannot supply this guarantee.

## AWS shutdown and costs

Stopping EC2 removes compute usage charges but leaves chargeable EBS storage.
Other retained resources, including snapshots, public IPv4 addresses, NAT gateways
and S3 storage, can also continue to cost money. The normal end-of-event operation
should therefore be verified backup followed by stack deletion, not only stop.

The destroy operation must check a complete backup outside the resources being
deleted, show the exact stack/resource inventory, and avoid deleting the only
backup. Destruction should remove event compute, attached event volumes, gateway
resources and addresses. Shared images, AMI snapshots and optional S3 backups
remain explicit retained assets with a separate retention policy. Do not claim a
zero bill while retaining those assets.

Tag resources with event ID and expiry. An expiry reminder is safer than silently
terminating an event with unsaved work. Teardown must wait for completion and
report failed deletions and residual billable resources.

## Implementation sequence and release gates

1. Add tested GHCR publishing and a digest-locked release bundle.
2. Complete idempotent app bootstrap and local deployment, initially paused.
3. Build and validate both desktop artifacts and the complete Wazuh configuration.
4. Implement full backup/restore and prove a local-to-local restore first.
5. Add AWS infrastructure, the same launcher and resource-aware teardown.
6. Rehearse local to AWS and back with all 10 teams, then destroy the AWS stack and
   verify residual resources. Measure launch, backup and recovery times.

The existing repository still declares missing validated desktop artifacts,
native evidence/prepared cases and full deployment compatibility. Package
publication must not relabel those incomplete assets as an event-ready release.

## Sources

- [GitHub container registry and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Publishing Docker images with GitHub Actions](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [EC2 lifecycle and stopping](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
- [EC2 billing FAQ](https://aws.amazon.com/ec2/faqs/)
- [AWS disaster recovery options](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
