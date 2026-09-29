# Participant narrative: updating, resetting and validating it for a run

The CTFd question page and the IRIS queue are one Jinja template,
`ridge/web.py` `PAGE`, rendered twice with a `lane` variable. Everything a
participant reads about the scenario comes from a versioned narrative fixture
through an assembler. Neither `ridge/web.py` nor the two integrations contains
scenario prose, and that is the point: three surfaces each carrying their own
copy is how they drifted apart.

There are currently two such fixtures, and the split is pending an organizer
decision. `ridge/narrative.py` reads `ridge/scenario_narrative_v1.json` and its
`story` markup is the organizer-approved rendering. `ridge/web_narrative.py`
reads `assets/scenario-narrative-v1.json` and contributes the blocks the
approved markup has no equivalent for. Both contexts reach the template; only
the approved markup renders the overlapping sections, so no participant reads
the same briefing twice. This note describes the contract surface, and the
section table below says which parts of the page that is.

Five surfaces render from that one file — the two lanes, the event-day deck, the
T01 network map and the evidence breadcrumbs. The first half of this note is how
to reset and update them; the second half, **Five surfaces, one story**, is
`ridge/narrative_consistency.py`, the check that proves they still agree, and it
is part of `python -m ridge.cli preflight`.

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

   The receipt gains a `narrative` block naming the contract and revision, and a
   `consistency` block naming the surfaces proved and the ones this host could
   not prove:

   ```json
   {"ready": true, "teams": 10, "tickets": 20,
    "narrative": {"contract": "silent-ridge-narrative", "revision": "1",
                  "surfaces": ["ctfd", "iris"]},
    "consistency": {"contract": "silent-ridge-narrative", "revision": 1,
                    "surfaces": ["contract", "ctfd", "iris", "web-template"],
                    "surfaces_not_proved": ["breadcrumbs", "deck", "handout", "map"],
                    "leak_guard": "fixture-only"}}
   ```

   That example is the integration container, which ships the contract and
   deliberately no `expanded/` and no deck, map or breadcrumbs. It proves the two
   lanes, names what it could not, and reports `leak_guard: fixture-only` because
   no answer key is present for the leak guard to run against. None of that is a
   pass and none of it is a failure; it is the container saying what it checked.
   The full receipt's `not_proved` list goes further and names the consequences —
   the four deck-only sections, the four tools the deck explains, and the map's
   one recorded exception. Run
   `python -m ridge.narrative_consistency --receipt` on the controller host for
   the full proof, where `surfaces_not_proved` is empty and `not_proved` is empty.

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

## Five surfaces, one story: the consistency check

`assets/scenario-narrative-v1.json` is authoritative, and five participant-facing
surfaces render from it. Five renderers are five chances to drift, so
`ridge/narrative_consistency.py` is the check that closes the loop. It is
read-only and offline: no network, no Docker, no browser, no database and no
clock.

| Surface | Source | Renders |
| --- | --- | --- |
| CTFd question page | `ridge/web_narrative.py` on `ridge/web.py` `PAGE` | phases, hints policy, accepted answers, ticket closure, ending, boundaries, T01 map link |
| IRIS incident queue | the same template, `lane='iris'` | the same, minus the question cards and minus the map link |
| Event-day deck | `docs/event-day-deck/`, generated by `ridge/deck_narrative.py` | the whole exercise narrative plus the projection set; 15 of 22 slides are contract-derived |
| T01 network map | `assets/t01-network-map-v1.json` via `ridge/network_map.py` | a post-completion analytical view of the evidence T01 already exposes |
| Evidence breadcrumbs | `assets/breadcrumbs-v1.json` via `ridge/breadcrumbs.py` | seven optional notes in `/evidence/notes/` |

The two lanes also render `ridge/narrative.py`'s approved `story` markup -
briefing, roles, tool map, per-ticket phase and handoff, "Why this question
matters" and shared progress - from `ridge/scenario_narrative_v1.json`. Two
narrative implementations now coexist on this one page pending an organizer
decision, so this table records what the contract above contributes, not
everything a participant reads. See the docstring in `ridge/web.py`.

Run it on its own, with the receipt:

```text
python -m ridge.narrative_consistency
python -m ridge.narrative_consistency --receipt
```

It is also part of preflight, so the receipt from
`python -m ridge.cli preflight` gains a `consistency` block naming the contract,
the revision, the surfaces proved and the ones this host could not prove. There
is no second organizer command to remember.

### What it checks, and what each failure means

| Guard | Failure looks like | Where to look |
| --- | --- | --- |
| `canon` | `canon: host WS-17 no longer appears in scripts/generate.py` | the fiction was renamed and the entity registry was not |
| `entities` | `map: assets/t01-network-map-v1.json:35: 'WS-42' is not a declared host` | a name reached a participant surface that no canon file declares |
| `entities` | `handout: participants/cells.md:14: WS-17 is spelled differently here` | a variation, not a synonym; the issue calls that a failure |
| `sections` | `ctfd: does not render exercise.premise` or `deck: never projects 'aar.close'` | a required section was emptied or stopped being projected |
| `lineage` | `map: assets/t01-network-map-v1.json was written against narrative revision 0` | the contract moved and the fixture was not revisited |
| `provenance` | `deck: docs/event-day-deck/pages/02_brief.page:1 does not match the contract it is generated from` | a contract-derived slide was hand-edited |
| `provenance` | `ctfd: the render context states '...', which is not the contract wording` | a renderer introduced a sentence of its own |
| `restatement` | `handout: participants/handover.md:6: restates exercise.discovery without saying it the same way` | a surface acquired a second copy of a contract sentence |
| `tools` | `tools: Guacamole is never explained in participant-facing content` | a tool in the issue is named nowhere a participant can place it |
| `tools` | `deck: never names 'Cutter', which the contract tool map explains` | the deck and the contract describe different toolkits |
| `leakage` | `deck: docs/event-day-deck/pages/15_step3.page:30 carries a credential assignment` | a secret, a facilitator path or a deployment detail reached a participant |
| `leakage` | `map: assets/t01-network-map-v1.json:40 names the answer to T09-Q3, whose evidence is not published when the map unlocks` | the post-completion view reached past the evidence on the mount |
| `attribution` | `handout: ... names an adversary group that is not in canon` | T20-Q4 scores `no` for intent, so no name may appear |

Anything this host cannot read goes into the receipt's `not_proved` list rather
than failing, and the surfaces involved into `surfaces_not_proved`. The
integration container is the case that matters: it ships the contract and no deck,
no map and no breadcrumbs, so its receipt proves the two lanes and names the rest
as unproved, along with the consequences - the four sections only the deck owes,
the four tools only the deck explains, and the map's one recorded exception. Read
that field before event day; a receipt with a long `not_proved` list is not a
proof of the whole event.

### The fictional canon is pinned, not remembered

`CANON` in `ridge/narrative_consistency.py` is the one declared set of
fictional organisations, people, hosts, patrol names, document names, sectors,
check-in words, programs and resolver names. It is not a list somebody maintains
by hand:

- every declared name must still appear in the file that declares it, so
  `scripts/generate.py` (the collection handout glossary at lines 74-90, and the
  plan content above it), `facilitator/ground-truth.md` and `expanded/author.py`
  are the canon and the registry follows them;
- every name-shaped token a participant can read must be in that set, filed
  under the right category and spelled exactly as declared;
- a name used on one surface and spelled any other way on another is a failure.

Renaming a host, an account, a document or a sector means editing the canon file
**and** the registry entry that points at it, in the same commit.

### Changing the narrative for a new run

1. Edit `assets/scenario-narrative-v1.json` and increment `revision`. Do not add
   a second fixture and do not restate any of it in `ridge/web.py`; the template
   holds no scenario prose and the provenance guard fails if it starts to.
2. Regenerate the deck so the change lands as a mechanical diff:

   ```text
   python -m ridge.deck_narrative --write
   ```

3. Bump `narrative_contract.revision` in `assets/t01-network-map-v1.json` and
   `assets/breadcrumbs-v1.json` to the same revision, after re-reading both for
   the change. The lineage guard refuses a fixture left behind.
4. Run the gates, in this order:

   ```text
   python -m unittest discover -s tests
   python -m compileall -q ridge integrations expanded deployment/expanded
   python -m ridge.narrative_consistency --receipt
   python -m ridge.cli preflight
   ```

5. Review `public_terms` before widening it. Each entry must already be visible
   in a published participant surface, and `check_public_terms` verifies that, so
   the exemption list cannot be used to leak a new answer.
6. Never put facilitator material in a fixture. `facilitator/ground-truth.md`
   and `facilitator/solutions.md` stay unreachable from participant code; scored
   answers stay in `expanded/author.py` and are dropped by
   `ridge/web_narrative.question_narrative` before the template sees them.

### Resetting or reseeding the narrative

The narrative has no per-run state. It is a read-only fixture, so a reset is a
repository and image question, not a database question. The scored state lives
elsewhere: points, ownership, answers and findings stay in the controller's
`runtime-expanded/state.sqlite` and the CTFd `Awards` rows, exactly as
`docs/expanded-operations.md` describes. Resetting the narrative never touches any
of that, and resetting the exercise never erases it.

A reset is therefore:

```text
git checkout <the revision you intend to run>
python expanded/author.py                                  # regenerate tickets.json
python expanded/prepare.py work/evidence                   # rebuild the release
python -m ridge.deck_narrative --write                     # regenerate the slides
python -m ridge.narrative_consistency --receipt            # prove the five agree
python -m ridge.cli preflight                              # prove the deployment
```

The first two steps rebuild the evidence; the breadcrumbs are rendered by
`expanded/prepare.py` from `assets/breadcrumbs-v1.json` into the same release, so
a reseed reproduces them byte for byte. The consistency receipt carries a SHA-256
for every committed narrative source, so two runs on the same tree produce the
same digests and a reset that changed a byte changes the receipt.

### Verifying on a clean deployment before event day

The narrative is read per request, so there is no cache or migration step. What
has to be true is that the images carry the fixture the host validated, and that
the five surfaces still agree.

1. On a clean checkout of the revision you intend to run:

   ```text
   python -m ridge.narrative_consistency --receipt
   ```

   Record the `revision`, `surfaces`, `not_proved` and the `sha256` block. An
   empty `not_proved` is the result you want on a full checkout with PyYAML
   installed; anything in it is a surface this host did not prove.

2. Rebuild the three images and the integration image, then compare the
   contract digest inside each with the host's. `ridge.bundle.LAYOUTS`
   hash-verifies the contract in all three participant images, and
   `ridge.deck_narrative --report` prints the deck's own coverage receipt.

3. Run `python -m ridge.cli preflight` and read both the `narrative` and the
   `consistency` blocks. The container's `consistency.surfaces` will be the two
   lanes only; that is expected and is why step 1 runs on the host.

4. Open the two pages and the deck and use the table above. A page that loads
   without the briefing means the deployment is running an image built before
   the contract existed, and the fix is a rebuild, not an edit to the template.

## Known limits

These are limits of the check and of the content, stated so nobody mistakes them
for coverage.

- **The deck PDF is a build artifact.** `docs/event-day-deck/event-day-deck.pdf`
  is produced by an external `.pptd` toolchain (`kimi-slides`) that is not
  vendored here and is not published to any package registry, so it cannot be
  rebuilt or verified from a clean checkout. The `.page` sources are the deck of
  record, the committed PDF is currently the pre-issue-#58 one, and
  `python -m ridge.deck_narrative --pdf` reports whether it has fallen behind.
  Nothing in the consistency check reads the PDF. See
  `docs/event-day-deck/README.md`.
- **Restatement is a similarity test, not a proof.** A sentence that shares a run
  of six content words with a contract section is caught; a free paraphrase that
  shares no such run is not. The exact provenance checks - a committed slide must
  equal the regenerated slide, and a rendered value must be a contract value or a
  join of them - are what cover a surface that invents rather than copies.
- **Entity detection is shape-based.** A token is treated as a name in this
  fiction because it matches one of `ENTITY_PATTERNS` (a host, a service, a
  session, a document, an account, a program, a task, a patrol, a sector, a
  check-in word, a path, a resolver name). A wholly invented label with none of
  those shapes is not seen. That is why the registry is pinned to canon and why
  adding a new kind of name means adding a pattern and a negative test.
- **`exposure`, `escalation`, `outcome` and the after-action review are the
  deck's obligation, not the question page's.** They are carried on the page
  context but only rendered by the projection set. A participant who never sees
  slide 2 does not read them; the acceptance criterion is met by the briefing,
  the role cards, the phase list and the tool map, which the page does carry.
- **Guacamole is explained on exactly one slide.** `pages/15_step3.page` is the
  only participant-facing passage that says what Guacamole is for. The check
  proves it is there and names the file and line; it cannot prove a participant
  reads slide 15.
- **`participants/README.md` carries a maintainers' note.** It is copied into
  the published handout tree by `scripts/generate.py` and names
  `scripts/generate.py`. The note is explicitly labelled for maintainers and the
  leak guard does not treat a build path as a credential, so it is recorded here
  rather than failed. Delete the block from the published copy if you run an
  unassessed session.
- **One value on the network map is both a record value and a locked answer.**
  The map projects a corrected endpoint event's `time_utc` on a graph edge, and
  that value is also T19-Q3's answer while T19 is still locked. It is a field
  drawn from `endpoint/events.csv`, which is on the mount from run start, so it is
  listed in `KNOWN_RECORD_VALUES` with its reason and proved still necessary on
  every run rather than waved through. A second value on the same reasoning fails.
- **The consistency check does not open a browser.** It proves what the surfaces
  render from their committed sources. That a participant can read the result is
  the table above, and only that.

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
