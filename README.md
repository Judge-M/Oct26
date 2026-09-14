# Operation Silent Ridge — expanded implementation

General-purpose teams investigate suspected disclosure of fictional patrol LANTERN's movement information. IRIS is the task queue; CTFd presents coached questions and equal-value points. Autopsy, Wireshark, Cutter and Wazuh provide the analysis interfaces. Linux desktops are accessed through Apache Guacamole.

**This implementation is not event-ready.** The transactional core and generated fixtures have been exercised locally. Application adapters, Linux desktops, native Windows/memory evidence and ready-to-open Autopsy cases still require integration/preparation work and Linux validation. Read the [acceptance record](docs/expanded-validation.md).

## Workflow

Teams claim one available IRIS ticket at a time. Each ticket has at most one owner. Only that owner's unanswered questions are answerable. A correct answer earns one point, queues its authored finding for IRIS, and persists globally. The last answer closes the ticket for everyone and unlocks authored follow-ups. There is no report, manual closure, facilitator approval, grading, first-blood bonus or hint penalty.

Relinquishing retains answers and findings. The replacement owner completes the remaining questions. Points remain with the original solving team. Ownership history and answer-to-finding/point/closure links are retained. Durable delivery uses atomic application-side receipts to avoid duplicate awards, tasks and comments. Synchronization pending is visible.

## Source validation and fixture generation

Python 3.12 or later is sufficient for the core and fixture tests:

```text
python -m unittest discover -s tests -v
python expanded/author.py
python expanded/prepare.py work/artifacts/new-release
python -m ridge.cli init --config expanded/config.json --content expanded/tickets.json
python -m ridge.cli status
```

Replace sample application IDs and VM addresses with provisioned identities. Initialization starts paused and does not create application accounts. Core tests use a simulated remote sink, not live IRIS or CTFd.

The 20 ticket outlines contain 80 questions with navigation, free hints, explicit walkthroughs and question-specific findings. Their 1,300 team-minute workload is **an unmeasured estimate** (260 minutes for five teams). Content targeting missing Autopsy cases is not yet runnable. Verify dates and navigation against installed packages and representative beginners.

## Deployment and operation

- [Central services, Linux template and Guacamole](docs/expanded-deployment.md)
- [Evidence preparation and Autopsy acceptance](docs/expanded-evidence.md)
- [Controller operations, export and reset](docs/expanded-operations.md)
- [Executed checks and outstanding acceptance](docs/expanded-validation.md)

Transfer all application images, dependencies, symbols/data, templates, evidence and guides before offline use. Secrets, state, exports and large artifacts stay outside Git. Final hardware and artifact-store provider remain configurable. The artifact verifier fails complete-bundle checks until every required category and verified compatibility are present.

## Retired baseline

The specialist-cell portal, Jira board, reporting worksheets and approval workflow under app/, admin/, jira/ and the original controller scripts remain only as baseline reference/test fixtures. They are **not the expanded workflow**. Default Compose no longer launches the old portal. The expanded generator preserves established incident facts while replacing old participant prompts and source IDs. The retained SQL helper and legacy image packer received regression fixes. The [old README](https://github.com/Judge-M/Oct26/blob/b4def5d4b65395aa0f441e785f225e053eec10d9/README.md) is historical.

All identities, addresses and activity are fictional. Public solutions make this coached material; a private assessment variant is not required.
