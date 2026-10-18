# MASTER HANDOFF — Operation Silent Ridge Audio Briefs

**To:** the next AI (drafter/producer of the audio briefs)
**From:** reviewer/synthesizer pass over two prior AI submissions + the user's podcast beat-map, all cross-checked against the live repo
**Status:** Authoritative planning input. This document supersedes and consolidates the earlier `HANDOFF.md`, `INJECTION-PLAN.md`, and the two prior AI outputs. Read this first; the other files in this folder are prior art to reconcile, not the plan of record.

Your job: **write the 7 audio briefs** specified below, spoiler-checked against the answer key, in the repo's existing voice, plus the paired `ridge.cli announce` text echoes and a day-of injection runbook. You are producing **scripts + production notes**, not final mixed audio (voice/TTS is a separate pipeline step).

---

## 0. Source of truth (read these in the repo before writing)

Repo: `https://github.com/Judge-M/Oct26` (a temp clone may exist at `/home/ismaelrodriguez/.hermes/cache/scratch/oct26`; re-clone if pruned).

| Path | What it locks |
|---|---|
| `facilitator/ground-truth.md` | Canonical timeline, inject content, intentional gaps, the 120s WS-17 clock rule. **Facilitator-only — never leak.** |
| `ridge/scenario_narrative_v1.json` | Premise, the 4 phases, stakes, handoffs — the canonical narrative voice. |
| `docs/learning-objectives.md` | LO1–LO8 definitions + ticket→LO crosswalk. Map every brief to an LO. |
| `docs/facilitator-evidence-release.md` | **The release mechanism** (automatic, ticket-gated) + the real `announce` command form. |
| `docs/rehearsal/evidence/rehearsal-20261018/completed-rerun.md` | Empirically **observed** release chain + the full 80-answer key + team→ticket map. |
| `docs/rehearsal/team-03-live-run.md` | Full human walkthrough, all 80 answers with evidence paths. |
| `docs/schedule-model.md` | Segment budget (25/195/10/15/30 = 275). Planning arithmetic, **not** a measurement. |
| `participants/handover.md` | The incoming-shift tasking voice + the `{{initial_report}}` / joint-assessment mechanics. |
| `participants/cells.md` | Team/cell workflow; "completion closes the ticket and makes eligible follow-up work available." |
| `docs/event-day-deck/pages/*.page` | Story wording, the fiction disclaimer, "Good hunting", EXCON/ENDEX framing. |
| `README.md` + `docs/presenter-landing.html` | The participant-facing `announce --operator EXCON` signature + the presenter hub to link audio from. |

---

## 1. Locked canon — DO NOT contradict

### Premise
Cooperative **defensive** SOC/incident-response exercise (not offensive, not flags-only). Up to 10 teams ("cells") of 3. Suspected disclosure of movement details for **fictional patrol LANTERN**, already in the field. Incoming shift takes the watch at **exercise time 09:30Z**. No confirmed harm. All names/hosts/addresses/artifacts are fictional.

### Canonical timeline (UTC, normalized — WS-17 device time is 120s FAST; subtract 2 min, once, only from WS-17 `device_time`)
`08:40` MFA + S-41 issued on WS-17 → `08:45` WS-31 suspicious inventory / WS-22 benign look-alike → `08:50` WS-31 telemetry stops → `08:57` viewer downloaded → `08:58` viewer runs → `08:59` session-store access → `09:03` external S-41 refresh (no fresh MFA) → `09:04` plan-v3 downloaded (req-71) → `09:04:30` roster request denied (403, 0 bytes, req-75) → `09:05` external password login fails → `09:06` plan-v3 body egress (req-72 → 198.51.100.77 / relay.archive.example) → `09:07` remote endpoint acknowledges (≠ human read) → `09:08` BriefSync persistence registered → `09:10` v4 supersedes v3 (sector AMBER→BLUE, window 10:00–11:00Z→10:30–11:30Z, **CEDAR retained**) → `09:12` authorized planner r.chen reads v4 → `09:14–09:18` DOCS collector gap → `09:20` password reset (**S-41 survives**) → `09:26` external refresh still succeeds → `09:30` incoming shift.

### The four phases (`scenario_narrative_v1.json`)
- **Phase 1 — Establish the disclosure path** (T01–T05)
- **Phase 2 — Test identity and access explanations** (T06–T10)
- **Phase 3 — Define scope and collection limits** (T11–T15)
- **Phase 4 — Correlate and state the defensible conclusion** (T16–T20)

### Release chain — AUTOMATIC, ticket-gated (empirically confirmed, `completed-rerun.md:88-92`)
Evidence is **not** released on a clock and **not** manually copied. The controller integration releases a dependent ticket automatically when its prerequisite closes; the facilitator only **observes** (`ridge.cli status` / `diagnostics` / `pending`→0 / new IRIS task) and then plays audio + announce.

| Dependent | Unlocks when | File released | Phase |
|---|---|---|---|
| T07 | T06 closes | `identity/late-auth.csv` | 2 |
| T09 | T08 closes | `server/version-comparison.csv` | 2 |
| T11 | T10 closes | `hunting/late-inventory.csv` | 3 |
| T19 | **T01 AND T05** close | `network/dlp-body.txt`, `network/dlp-metadata.json` | 4 |
| T20 | T07+T09+T11+T19 close | (synthesis, no file) | 4 |

Cross-team coupling is real (each team owns 2 tickets; T19 needs Team 1's T01 + Team 5's T05; T20 needs four teams). Inject beats land at these convergence unlocks — that's when blocked teams get unblocked and the "shared investigation" theme is loudest.

### Intentional gaps — these MUST remain gaps at ENDEX (never resolve them in audio)
Original delivery path of the viewer · token/session contents · **human attribution** (who, if anyone, received/read the payload) · activity inside the DOCS audit gap · WS-31 runtime activity (stays **unresolved**) · uncollected systems · **actual use** of the disclosed information. Transmission ≠ receipt ≠ intent is non-negotiable.

### Learning objectives (map each brief to these — `docs/learning-objectives.md`)
LO1 interpret source time / preserve provenance · LO2 reconstruct chain, separate observation from inference · LO3 preserve/handle evidence defensibly · LO4 assess identity/session activity, **judge control efficacy** · LO5 bound disclosure scope, avoid absence-of-evidence fallacies · LO6 test scope hypotheses against coverage, keep unresolved systems unresolved · LO7 produce precise evidence-bounded findings, share durably · LO8 reconcile findings across teams + run the AAR.

---

## 2. THE PLAN — 7 audio moments, all event-gated

This is the reconciled placement: the user's podcast beat-map (dramaturgy) × the verified release chain (mechanics) × the rehearsal data (confirmed order + coupling).

| # | File | Beat | Trigger (observed, not clock) | Target len | LO | Framing |
|---|---|---|---|---|---|---|
| 1 | `brief-01-opening-task.md` | Cold-open tasking | Orientation seam, just before `ridge.deploy start` | ~70–80s | LO2, LO7, LO8 | Dramatic, spoiler-free. "You have the watch." |
| 2 | `brief-02-inject-a-reset.md` | "The reset didn't contain it" | **T07 unlocks ← T06** (`late-auth.csv`) | ~15–25s | **LO4** | Revisit your access assessment: what a credential action did/did not revoke. |
| 3 | `brief-03-inject-b-superseded.md` | "Some of it is outdated — some isn't" | **T09 unlocks ← T08** (`version-comparison.csv`) | ~15–25s | LO5, LO2 | Re-examine what is superseded and what is still live. Bound the scope claim. |
| 4 | `brief-04-inject-c-unresolved.md` | "A name match is not a compromise" | **T11 unlocks ← T10** (`late-inventory.csv`) | ~15–25s | LO6, LO5 | Test the lead; keep unobservable hosts unresolved; absence of telemetry ≠ proof. |
| 5 | `brief-05-inject-d-payload.md` | "Now you can test the payload" | **T19 unlocks ← T01+T05** (DLP body/metadata) | ~15–25s | LO2, LO5 | The most satisfying reveal: re-test the transmission lead against the actual body. Connection/ack ≠ human receipt. |
| 6 | `brief-06-command-decision.md` | "Final decision point" | **T20 unlocks ← T07+T09+T11+T19** | ~25–35s | LO5, LO7, LO8 | Pose the command questions; task a proportionate containment recommendation. Do **not** issue operational direction to the patrol. |
| 7 | `brief-07-endex-standdown.md` | ENDEX | End of investigation block, before AAR | ~15–20s | LO8 | Formal stand-down; hand the room to reflection. |

**Fallback (if the facilitator prefers one beat):** the schedule model budgets a single 10-min facilitated "Inject briefing: late evidence release" segment. If used, play beats 2–5 consolidated there and keep 6–7 at their triggers. Event-gated (above) is the **primary** design because releases fire automatically throughout the 195-min block, not at one scheduled minute.

**Do NOT add audio at the clock-discovery beat** (T01/T03/T04/T13 timestamp normalization). That's a discovery moment; narrating it would spoil the 120s offset (LO1). Let teams find it.

---

## 3. Per-brief spec

For each brief produce: (a) full script in military radio-dispatch voice, (b) 1–2 sentence purpose + exact trigger, (c) facilitator notes (when to play, the paired announce text, whether to pause the clock), (d) the `ridge.cli announce` text echo, (e) LO mapping, (f) voice/processing notes.

### Brief 01 — Opening Tasking
- **Carry:** 09:30Z handover; suspected LANTERN disclosure (**suspected, not confirmed**); no confirmed harm; do not assume the incident is over; five export families staged (endpoint, network, identity, document-service, SIEM); tasking = *what moved / how access was gained / which systems remain affected*; label every claim **confirmed / assessed / unknown**; cite evidence; report even at low confidence; first command update due at the `{{initial_report}}` elapsed mark; read-only; do not contact/track/direct real personnel; no attack required; fiction disclaimer; "Good hunting."
- **Never say:** WS-17, brief-viewer.exe, S-41, plan-v3/v4, m.ellis, r.chen, AMBER/BLUE/CEDAR, 198.51.100.77, req-71/72/75, any attack-chain timestamp, the 120s offset, "session stolen", "exfiltrated to…".
- **Ordering:** stay **order-neutral** on reset-vs-viewer (see §6 discrepancy). AI-2's existing `brief-01-opening-task.md` already passes this — use it as the spine, tighten to spec.

### Brief 02 — Inject A: reset didn't contain it (T07 ← T06)
- **Carry:** new identity/access records released; re-examine whether a credential action actually contained the incident; what a reset does and does **not** revoke; revisit your prior access assessment and update the shared finding.
- **Never say:** 09:20, 09:26, S-41, "session revocation", "refresh succeeds", m.ellis, "previous_claim". Name the family ("later authentication records"), not the answer.

### Brief 03 — Inject B: superseded, not all (T09 ← T08)
- **Carry:** a superseding movement record released; re-examine what has been superseded and what has **not**; not all exposed detail is equally current; bound the scope claim accordingly.
- **Never say:** plan-v3/v4, AMBER/BLUE, CEDAR, 10:30–11:30Z, 09:10, "sector changed but the word was retained".

### Brief 04 — Inject C: name match ≠ compromise (T11 ← T10)
- **Carry:** an unresolved-host inventory lead released alongside a comparator; test whether a name match is a compromise indicator; keep unobservable hosts **unresolved**; absence of telemetry is not proof of absence.
- **Never say:** WS-31, WS-22, BriefSync, r.chen, "Exercise IT", 08:45/08:50, "benign", "approved path".

### Brief 05 — Inject D: test the payload (T19 ← T01+T05)
- **Carry:** the actual transmitted payload body + its metadata are now staged; re-test your earlier transmission lead (the size match) against the real body; a connection or acknowledgement supports **transmission, not human receipt or intent**; revisit and update the prior conclusion.
- **Never say:** req-72, 09:06, "version 3", "matches plan-v3", 198.51.100.77, "the hash matches", relay.archive.example.

### Brief 06 — Command Decision (T20 ← T07+T09+T11+T19)
- **Carry:** all evidence lines have converged; task a **proportionate containment recommendation** for command (e.g. explicit session revocation, endpoint preservation/containment, continued targeted collection where evidence is missing); pose the command questions the team must answer *without* answering them — "Is roster disclosure established? Is the patrol's exposure complete? Do you know the adversary? Did the credential action contain it?"; distinguish disclosed vs denied vs unresolved; **your role is a reliable technical assessment to decision-makers — not operational direction to the patrol**; no invented harm or intent.
- **Never say:** the T20 answers as flat facts (`3`, `no`, `no`, `no`), "roster was denied", "WS-31 is unresolved", "intent is not established" — pose them as the questions command needs defended, not the answers.

### Brief 07 — ENDEX Stand-down
- **Carry:** ENDEX; stand down; cease all investigation; your assessment is recorded; debrief/AAR follows; well done; fiction disclaimer. AI-2's existing `brief-03-endex-standdown.md` is good as-is — renumber to 07.

---

## 4. Voice & style contract

- **Register:** calm, clipped, unhurried radio-dispatch (watch-officer / TOC). Urgency from brevity, not volume. Slight downward pitch at line ends ("out").
- **Open/close:** "All stations, this is EXCON. Exercise, exercise, exercise." … "Good hunting. EXCON, out."
- **Canon terminology (use exactly):** EXCON · ENDEX · Patrol LANTERN · "Good hunting" · confirmed / assessed / unknown · "exercise only" · cells/teams · controller · hunting reporter · joint assessment · "do not contact real personnel".
- **Fiction disclaimer (end every brief, exact deck wording):** *"All names, hosts, addresses and artifacts are fictional exercise material. Nothing here is a real system or person."* + footer line *"OPERATION SILENT RIDGE — EXERCISE ONLY."*
- **Processing notes (carry from AI-2, consistent across all 7):** high-pass ~200 Hz, presence boost 1–4 kHz, soft static bed ~-30 dB, squelch "kerchunk" at open, two-tone chime at close.
- **Pacing:** ~140 wpm. Expand any acronym on first use. Write clean for TTS *or* live voice.

---

## 5. Spoiler discipline — the hard rule

**The audio never answers a ticket.** It names the *situation* and the *kind* of evidence, never the workstation, filename, session, version, sector, check-in word, address, request ID, hash result, or timestamp that teams must establish themselves.

Full 80-answer key is in `completed-rerun.md:60-81` and `team-03-live-run.md`. Forbidden-before-discovery terms include (non-exhaustive): `WS-17`, `WS-22`, `WS-31`, `brief-viewer.exe`, `BriefSync`, `S-41`, `m.ellis`, `r.chen`, `plan-v3`, `plan-v4`, `AMBER`, `BLUE`, `CEDAR`, `198.51.100.77`, `10.26.10.17`, `relay.archive.example`, `briefs.helpdesk.example`, `req-71`, `req-72`, `req-75`, `previous_claim`, `session revocation`, `6364`, `7644`, `C:/Temp/move-cache.txt`, `classify_version`, `cached v3`, and every chain timestamp (08:57, 08:58, 09:03, 09:04, 09:06, 09:08, 09:10, 09:20, 09:26). LANTERN itself is **not** a spoiler (it's the premise, given in `handover.md`).

Run a literal string-search of every finished script against this list before sign-off.

---

## 6. Delivery mechanics

- **No timed audio scheduler exists.** Everything is operator-driven. Audio fires when the facilitator **observes** an automatic release (or reaches a scheduled seam), then plays the clip and posts the text echo.
- **Observe releases on the controller host:**
  ```
  python -m ridge.cli --state RUNTIME/state/state.sqlite status
  python -m ridge.cli --state RUNTIME/state/state.sqlite diagnostics
  ```
  A release is real when the prerequisite is `complete`, the dependent is no longer `locked`, `pending` returns to 0, and the new IRIS task + named files are visible in the read-only participant tree.
- **Text echo — two valid forms:**
  - Participant-facing / README / presenter hub: `python -m ridge.cli announce --operator EXCON --text "..."`
  - Real-event runbook (controller host): `python -m ridge.cli --state RUNTIME/state/state.sqlite announce --operator EXCON-A --text "..."`
  - Use `EXCON` for the day-of announce echoes (matches README + `presenter-landing.html:220`); note `EXCON-A` is the controller-host operator id in the runbook. Replace `RUNTIME` with the actual state path.
- **Pair every audio clip with its text echo** so the spoken and written records can't drift. Keep the echoes verbatim from each brief's "Text echo" line.
- **Presenter integration:** link the audio files from `docs/presenter-landing.html` so the presenter gets one-click playback at each beat. Keep scripts + audio in a **facilitator-only** location — never `runtime/public`, never the participant evidence tree (`ground-truth.md:3` warns the public repo cannot hide answers).

---

## 7. Guardrails (non-negotiable)

- Stay 100% inside ground truth + intentional gaps. Invent no adversary, no real unit/coordinate/geography, no harm, no "human read the payload", no resolution of WS-31, no delivery vector.
- Reinforce, never contradict, LO1–LO8.
- Preserve the **cooperative** design: emphasize shared IRIS findings and the defensible joint assessment, not team ranking or speed. "Points are the byproduct, not the goal."
- Briefs are **not** scored content and must contain no answers or tool walkthroughs.
- Read-only investigation; do not contact real personnel; no attack required.

---

## 8. Known discrepancies & how to handle them

1. **Deck ordering bug (real, verified).** `docs/event-day-deck/pages/03_story.page` says "an account password was reset at 09:20, and a viewer tool was run minutes later." `ground-truth.md:35-36` places the viewer download/run at **08:57/08:58 — before** the 09:20 reset. The two canonical sources disagree. **Handle:** write Brief 01 order-neutral (AI-2 already did). **Flag to the event owner** to correct the deck line. Do not "fix" it in audio.
2. **The podcast is partly outdated on rehearsal status.** It assumed no human rehearsal had run. In fact two ran 2026-10-18: a first attempt that failed 0/80 (CTFd 500s, identity drift) and a **completed rerun: 20/20 stages, 80/80 answers, 0 pending**. *But* the rerun was **one operator serializing all 10 team identities through one browser** (`completed-rerun.md:33-34`), not 30 humans in parallel — so the podcast's core caveat still holds: **there is no empirical live-room pacing data.** This is exactly why briefs are keyed to release events, not elapsed minutes.
3. **The 65-min/ticket and 195-min makespan figures are unmeasured** (`schedule-model.md:22`, `learning-objectives.md:302`). Never express inject timing in absolute elapsed minutes in any deliverable; use phase progress / dependency unlocks.

---

## 9. Deliverable format & file layout

Write into this folder (`/home/ismaelrodriguez/silent-ridge-audio-briefs/`), then the owner places the approved set in the repo at **`docs/handoff/audio-briefs/`** (facilitator-only; matches the repo's `docs/handoff/` convention) with a short README pointing to this handoff + `schedule-model.md` + `ground-truth.md`.

Each `brief-NN-*.md` contains: role · trigger · target length · LO · voice/processing · spoiler-discipline note · **the script** · "key facts carried" accuracy checklist · the paired **text echo** command. Also refresh `INJECTION-PLAN.md` to the 7-beat table in §2 and update `README.md`'s index.

Final packaging deliverables:
1. 7 brief scripts (files above).
2. Updated `INJECTION-PLAN.md` (7 beats, event-gated, with the observed-release triggers + observe commands).
3. A day-of **runbook block**: the ordered `announce` commands + the `status`/`diagnostics` observation steps per beat.
4. Updated `README.md` index.
5. This `MASTER-HANDOFF.md` (carry forward).

---

## 10. Reviewer checklist (for the 3rd AI / final QA)

- [ ] Literal string-search of every script against the §5 forbidden-terms list — **zero** hits before discovery.
- [ ] No brief resolves an intentional gap (attribution, human receipt, WS-31, delivery path, DOCS-gap activity, actual use).
- [ ] Every brief reinforces (never contradicts) its mapped LO and the confirmed/assessed/unknown discipline.
- [ ] Triggers match the **observed** release chain (T07←T06, T09←T08, T11←T10, T19←T01+T05, T20←all four) — not clock times.
- [ ] Brief 01 is order-neutral on reset-vs-viewer (deck discrepancy).
- [ ] Every brief ends with the exact fiction disclaimer + "EXERCISE ONLY"; opening/closing use EXCON/"Good hunting"/"out".
- [ ] Text echoes use a valid `announce` signature; `--state` noted for the real event.
- [ ] The 120s WS-17 offset is never contradicted or revealed.
- [ ] Lengths within target; cooperative framing preserved; nothing scored; no tool walkthroughs.
- [ ] Assets staged facilitator-only, never `runtime/public` or the evidence tree.

---

## 11. Open decisions for the event owner (settle before production)

1. **4 inject beats vs 1 consolidated** 10-min segment? (Plan recommends 4, event-gated; consolidated is the fallback.)
2. **Who supplies the final voice + radio mix?** This package ships scripts + notes. A free Edge TTS endpoint returned 403 (provider-blocked, not a content issue) — assume a separate voice pipeline.
3. **Fix the `03_story.page` ordering line** so the deck stops contradicting ground truth.
4. **Repo placement:** confirm `docs/handoff/audio-briefs/` (facilitator-only) and whether to ship as a branch/PR.

---

## 12. Provenance / confidence

- **Verified against the live repo** (high confidence): timeline, release chain, 80-answer key, LO1–LO8, phases, schedule segments, announce signatures, fiction-disclaimer wording, "Good hunting", the deck ordering discrepancy, the rehearsal outcomes (failed first attempt + serialized successful rerun).
- **Inferred / editorial** (validate before relying): the podcast's simulated player reactions and pacing claims; the "~30–45 min in" style timing guesses; the dramatic-beat *ordering* is sound but its *absolute timing* is unmeasured (no 30-human live run exists).
- **Prior art to reconcile, not trust blindly:** AI-1's plan (good style guide + checklist; **discarded** its fabricated 60/130/200-min cadence and its single-clock-segment inject model). AI-2's scripts (good spine, correct event-gating, correct discrepancy flag; **expanded** its 3 injects → 4, added the T20 command-decision beat, corrected "facilitator drives" → "facilitator observes automatic release").

**Bottom line for the next AI:** the spine is AI-2's voice + spoiler discipline; the structure is the 7-beat event-gated table in §2; the dramaturgy is the podcast; the ground truth is the repo. Write the 7 briefs, string-check them against §5, pair each with its announce echo, and stage them facilitator-only.
