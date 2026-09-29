# Event-day deck

The participant briefing deck, and the facilitator appendix that must not be
projected.

- `pages/` — the **participant projection set**. 22 slides. `event-day-deck.pptd`
  is the project that renders them, and it lists nothing else.
- `facilitator-pages/` — the **facilitator-only appendix**. 2 slides, behind its
  own project file `facilitator-appendix.pptd`, each carrying a full-width
  `FACILITATOR ONLY — DO NOT PROJECT` banner. Pause, inject, synchronisation and
  recovery procedure lives here and nowhere else.
- `event-day-deck.pdf` — the committed binary. **It is a build artifact and is
  currently stale; see below.**

## The sources are authoritative

`pages/*.page` and `facilitator-pages/*.page` are the deck. The `.pptd` files and
the PDF are both derived from them.

Scenario wording is not written in the slide files. It is rendered from
`assets/scenario-narrative-v1.json`, the same approved contract the CTFd
question page and the IRIS case use, and every contract-derived string carries a
`contractRef` naming the field it came from. The slide files are still committed
and readable, but retyping one is a defect: the validator requires the rendered
text to equal the contract value exactly.

To regenerate the contract-derived slides and both project files:

```bash
python -m ridge.deck_narrative --write
```

To validate without writing anything:

```bash
python -m ridge.deck_narrative            # exits non-zero on any problem
python -m ridge.deck_narrative --report   # JSON receipt: audience split, per-phase coverage
```

The deck is one of five participant-facing surfaces rendering from the same
narrative contract. `ridge/narrative_consistency.py` proves the five still agree -
that the committed slides are byte-for-byte what the contract generates, that
every name on every surface is canon, and that nothing on the deck is a spoiler:

```bash
python -m ridge.narrative_consistency --receipt
```

It also runs inside `python -m ridge.cli preflight`. See
[`docs/narrative-operations.md`](../narrative-operations.md) for what each failure
means and what the check cannot see.

The six hand-authored slides — the day loop, the four-tab setup, the tools table
and the troubleshooting table — are operational instructions, not scenario prose.
The contract has nothing to say about which button to press, so those stay
hand-authored and are held to the same geometry and legibility checks.

## Regenerating the PDF

`event-day-deck.pdf` is produced by an external `.pptd` toolchain (`kimi-slides`).
That toolchain is **not vendored in this repository and is not published to any
package registry**, so the PDF cannot be rebuilt or verified from a clean
checkout. Nothing in this repository fabricates or hand-edits it.

On the machine that has the toolchain, the operator runs:

```bash
kimi-slides build docs/event-day-deck/event-day-deck.pptd -o docs/event-day-deck/event-day-deck.pdf
kimi-slides build docs/event-day-deck/facilitator-appendix.pptd \
    -o docs/event-day-deck/facilitator-appendix.pdf
kimi-slides check docs/event-day-deck/event-day-deck.pptd
```

The `-o` path and the `check` subcommand match the invocation recorded in
`docs/handoff/NEXT.md` for the deck as it previously shipped; confirm them
against the installed toolchain before relying on them.

To check whether the committed PDF is behind its sources:

```bash
python -m ridge.deck_narrative --pdf
```

This reports `stale: true` when any `.page` source or project file is newer than
the PDF, together with the source file and the SHA-256 of the binary. It is a
warning, not a build: git does not preserve modification times, so a fresh
clone reports whatever order the checkout happened to write the files in.

### Current state

The PDF in this repository is the artifact that shipped before issue #58. It
still contains the old 13-slide deck. The narrative changes in that issue are in
the `.page` sources only, and the PDF must be rebuilt on a host that has
`kimi-slides` before the deck is projected at an event. Until then, the sources
are the deck of record.

This is the one thing about the narrative layer that cannot be verified from a
clean checkout, and `ridge/narrative_consistency.py` does not pretend otherwise:
it checks the `.page` sources and the generator, and never reads the PDF. It is
listed under known limits in
[`docs/narrative-operations.md`](../narrative-operations.md) with the operator
command.
