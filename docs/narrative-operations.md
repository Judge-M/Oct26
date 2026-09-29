# Participant narrative: updating and resetting it for a run

The CTFd question page and the IRIS queue are one Jinja template,
`ridge/web.py` `PAGE`, rendered twice with a `lane` variable. Everything a
participant reads about the scenario comes from
`assets/scenario-narrative-v1.json` through `ridge/web_narrative.py`. Neither
`ridge/web.py` nor the two integrations contains scenario prose, and that is the
point: three surfaces each carrying their own copy is how they drifted apart.

## Reset for a new exercise run

The narrative has no per-run state. It is a read-only fixture, so a reset is a
repository and image question, not a database question. The scored state lives
elsewhere: points, ownership, answers and findings stay in the controller's
`runtime-expanded/state.sqlite` and the CTFd `Awards` rows, exactly as
`docs/expanded-operations.md` describes. Resetting the narrative never touches
any of that, and resetting the exercise never erases it.

To put a deployment back on the current approved narrative:

1. Confirm the working tree is the revision you intend to run.
   `git log -1 --format=%H` and `git status --short` must both be clean.
2. Prove the narrative is intact before anything is rebuilt. From the
   repository root:

   ```text
   python -m ridge.cli preflight
   ```

   The receipt gains a `narrative` block naming the contract and revision:

   ```json
   {"ready": true, "teams": 10, "tickets": 20,
    "narrative": {"contract": "silent-ridge-narrative", "revision": "1",
                  "surfaces": ["ctfd", "iris"]}}
   ```

   A missing or empty section fails loudly with the section named
   (`narrative: the event briefing is missing premise`), and a contract that
   would pre-answer a scored question fails as a
   `ridge.scenario_contract.ContractError`. Neither can be read as a pass.

   `ridge.deploy` runs the same command inside the integration container, which
   ships the contract but deliberately no `expanded/` and therefore no answer
   key. There the receipt's `leak_guard` reads `fixture-only` instead of
   `authored`, and the container says so rather than implying the answer-leak
   guard ran. `ridge.bundle.LAYOUTS` hash-verifies the contract inside all three
   images, so a cold bundle is still tied to the fixture this host validated.
3. Rebuild the two participant images and the integration image. The contract
   fixture is copied into each by `deployment/expanded/Dockerfile.ctfd`,
   `Dockerfile.iris` and `Dockerfile.integration`; an image built before this
   existed raises `narrative contract not found` on the first page render or on
   the first preflight.

   ```text
   docker build -f deployment/expanded/Dockerfile.ctfd -t silent-ridge-ctfd .
   docker build -f deployment/expanded/Dockerfile.iris -t silent-ridge-iris .
   docker build -f deployment/expanded/Dockerfile.integration -t silent-ridge-integration .
   ```

4. Restart only CTFd and IRIS, then reload the participant page. The narrative
   is read per request, so no cache or migration step is involved.

## Update the narrative for a new run

1. Edit `assets/scenario-narrative-v1.json` and increment `revision`. Do not
   add a second fixture and do not restate any of it in `ridge/web.py`; the
   template holds no scenario prose and a test enforces that.
2. Run the gates. `python -m unittest discover -s tests` covers the leak guard,
   the phase partition, the render context and the template; `python -m
   compileall -q ridge integrations expanded deployment/expanded` is the CI
   compile step.
3. Run `python -m ridge.cli preflight` again. It renders the contract for both
   lanes and additionally renders a fully closed exercise, so a missing ending
   or accepted-answer line is found at preflight rather than at the end of the
   day.
4. Review `public_terms` before widening it. Each entry must already be visible
   in a published participant surface, and `check_public_terms` verifies that,
   so the exemption list cannot be used to leak a new answer.
5. Never put facilitator material in the contract. `facilitator/ground-truth.md`
   and `facilitator/solutions.md` stay unreachable from participant code; scored
   answers stay in `expanded/author.py` and are dropped by
   `ridge/web_narrative.question_narrative` before the template sees them.

## How a facilitator verifies it is present

From the repository root, with no service running:

```text
python -m ridge.cli preflight     # includes the narrative receipt
python -m ridge.web_narrative     # prints the narrative receipt only
python -m unittest tests.test_web_narrative
```

Then open the two surfaces and look for the specific text, not just for a page
that loads:

| Surface | What to look for |
| --- | --- |
| `<ctfd>/silent-ridge` | Classification line, "Situation", the three role cards, the phase list, and a per-question phase, headline, brief and "Why this question matters" |
| `<iris>/silent-ridge` | The same briefing block, plus each ticket's phase, headline, brief, stakes, why-now and next step |
| Any question card | A help policy line and three `<details>` levels that open with the contract's nudge, method and walkthrough lead-ins |
| A solved question | The accepted-answer line above the recorded finding |
| A closed ticket | The ticket-closure and handoff lines |
| The last ticket closed | The closing block: brief, handoff, residual and scoring note |
| Any page | The collapsed "Ground rules for this exercise" block |

Before the event, `python -m ridge.cli preflight` is the proof; after it, the
table is the proof. A page that loads without the briefing means the deployment
is running an image built before the contract existed, and the fix is step 3
above, not an edit to the template.

## Known finding: the participant scoreboard

An issue comment reported the participant-facing scoreboard returning an HTTP
500 page. Investigated against the pinned `ctfd/ctfd:3.7.7` image with this
plugin and a disposable database: **not reproduced from committed source.**

- `tests/ctfd_container_smoke.py:109-111` already asserts that an authenticated
  participant receives HTTP 200 and their team name from `/scoreboard` in the
  real image, and CI runs that smoke on every push.
- A wider probe against the same image returned 200 for `/scoreboard`,
  `/api/v1/scoreboard` and `/api/v1/scoreboard/top/10` (the only two API paths
  `protect_stock_routes` allows and the only two the theme's own JavaScript
  calls), both before and after a point is delivered through the plugin.

The one reproducible 500 is a misconfiguration, not a defect in this repository:
`CTFd/utils/config/__init__.py:51` calls `int(freeze)`, so any `freeze` setting
that is not a bare Unix timestamp raises `ValueError` and the **`/scoreboard`
page** returns 500 while `/api/v1/scoreboard` still returns 200. Nothing in this
repository sets `freeze`, and the CTFd admin UI writes an integer, so this only
happens if an operator hand-edits the config. Do not work around it by clearing
the value: freezing a scoreboard is a real event-day control.

To settle it, capture from the failing deployment: the CTFd container log for
the request, the value of the `freeze` row in `config`, and the HTTP status of
`/api/v1/scoreboard` for the same session. If the page 500s while the API
returns 200, the cause is `freeze`; anything else needs the traceback, because
the committed stack does not produce it.
