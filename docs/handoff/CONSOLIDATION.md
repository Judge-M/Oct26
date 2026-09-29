# Replacement for PRs 14–20

This integration starts from main `370ff50`. It consolidates useful source and
corrects reviewed defects; it does not certify an event deployment.

| Previous PR | Disposition |
|---|---|
| 14 | Container design retained as an experimental option; VM remains available. |
| 15 | Profile, journal, workload, paths and learning-document corrections retained. OS-held local locking replaces an unrenewed 120-second lease. Resource receipts no longer claim an application is paused. |
| 16 | Central provisioning, Compose, evidence delivery, question matrix and tests retained and integrated. Bootstrap model/CLI errors corrected; the harness now checks remote effects. Unusable Hyper-V command generator omitted; C01 remains open. |
| 17 | Unsafe lifecycle/recovery/AWS/fencing stubs are not imported. The package conflict, false paused state, backup bypass and SQLite-only “full restore” therefore cannot enter the runtime. Original H01 recipes remain published on main; H01 and later-wave task cards remain open. |
| 18 | Container source retained; real builds required. Fix checksums, Java/tool prerequisites, case seeding, secret encoding and project scoping. |
| 19 | README replaced by a concise current-state description; unbuilt features are not listed as implemented deployments. |
| 20 | Dated observations retained as historical evidence. They are not proof of acceptance on this branch. |

The old PRs remain historical GitHub references; no useful event artifact is lost.
Their task labels and green unit tests must not be interpreted as acceptance.
Closing the old PRs does not complete their unaccepted tasks.

## Still required

Follow NEXT.md. The complete local lifecycle, Wazuh stack acceptance, native
database/workspace recovery, AWS deployment/expiry/verified teardown, independent
fencing, site switching, ten-team capacity and offline release acceptance remain
explicit tasks. Implement them after the two-team workflow, using the shared
package and actual component operations. No synthetic provider can satisfy them.
