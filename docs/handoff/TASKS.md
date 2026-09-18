# Bounded task queue

Original planning baseline: tasks started as **not started**. Current progress and
execution order are in [NEXT.md](NEXT.md) and [CONSOLIDATION.md](CONSOLIDATION.md). Dependencies mean accepted evidence, not merely a merged stub.

| ID | Task | Requires | Review |
|---|---|---|---|
| [A01](tasks/A01.md) | Reconcile readiness documentation and prepare PR #6 updates | — | standard |
| [A02](tasks/A02.md) | Inventory the ten-team workload and dependency schedule | — | standard |
| [A03](tasks/A03.md) | Define and validate one private deployment profile | — | standard |
| [A04](tasks/A04.md) | Specify deployment receipts, locking and provider interfaces | A03 | focused architecture review |
| [A05](tasks/A05.md) | Fix the Autopsy evidence-path and preflight contract | A03 | standard |
| [B01](tasks/B01.md) | Automate and test IRIS bootstrap | A03, A04 | focused adapter review |
| [B02](tasks/B02.md) | Automate CTFd settings, teams and participants | A03, A04 | standard |
| [B03](tasks/B03.md) | Vendor and bootstrap the complete Wazuh historical stack | A03 | standard |
| [B04](tasks/B04.md) | Make central Compose, networks and secrets run-scoped | A03, A04 | standard |
| [B05](tasks/B05.md) | Prove a real two-team vertical slice while paused | A05, B01, B02, B03, B04 | focused integration review |
| [C01](tasks/C01.md) | Prepare and verify a local Hyper-V desktop provider | A03, A04 | standard |
| [C02](tasks/C02.md) | Provision Guacamole and prove team session isolation | B04, C01 | standard |
| [C03](tasks/C03.md) | Deliver released evidence to desktops reliably | A05, B05, C02 | focused release-consistency review |
| [C04](tasks/C04.md) | Walk all questions through the installed tools | A05, C02, C03 | standard |
| [D01](tasks/D01.md) | Test live transactional failures and pause races | B05, C03 | mandatory transaction review |
| [D02](tasks/D02.md) | Build coherent full-event backup | B05, C02, C03, A04 | mandatory backup review |
| [D03](tasks/D03.md) | Restore onto a clean local destination | D02, C01 | mandatory restore review |
| [D04](tasks/D04.md) | Bound storage growth and implement safe retention | D02, D03, A04 | mandatory deletion review |
| [E01](tasks/E01.md) | Implement the shared deployment CLI | A04, B05, C03, D03, D04 | standard |
| [E02](tasks/E02.md) | Provide the Windows one-command local launcher | E01, C01, C02 | standard |
| [E03](tasks/E03.md) | Prepare and validate the AWS desktop AMI | A03, A04, C01 | focused cloud image review |
| [E04](tasks/E04.md) | Implement minimal AWS infrastructure and provisioning | E01, E03, B04 | focused infrastructure review |
| [E05](tasks/E05.md) | Implement AWS expiry and verified teardown | E04, D03, D04 | mandatory cost/deletion review |
| [F01](tasks/F01.md) | Implement active-site fencing and recovery ownership | A04, D03, E04 | mandatory distributed-state review |
| [F02](tasks/F02.md) | Automate local↔AWS switching with rollback | F01, D03, E04, E05 | mandatory recovery review |
| [F03](tasks/F03.md) | Measure ten-team/30-participant capacity | E02, E04, C04, D01 | standard |
| [F04](tasks/F04.md) | Close the duration and beginner usability gap | A02, C04, F03 | standard |
| [F05](tasks/F05.md) | Publish the complete versioned offline release | E02, E04, D03, C04, F04 | focused release review |
| [F06](tasks/F06.md) | Execute the event dress rehearsal and recovery drill | D01, F02, F03, F04, F05 | mandatory final acceptance review |
| [G01](tasks/G01.md) | Finalize operator handoff and freeze the event release | A01, F06 | standard |
| [H01](tasks/H01.md) | Consolidate preserved recipes into a portable build pipeline | — | focused block-device/deletion review |
