# Clean-baseline receipt — fresh-host reproduction and one real defect fixed

Date: 2026-09-29. Branch: `main` (uncommitted working change, see §6).
Baseline: `main` `4203239` ("Merge pull request #181 from Judge-M/docs/f03-credentials-contract").
Test count: **395 passing** (394 + 1 new regression test), 22 skipped.

**Status:** source implemented, images built, build verified. No event was
started, no participant ever saw this stack, and nothing here certifies event
readiness. `doctor` reports `recovery_ready: false` and `event_ready: false`,
which is the correct state on a fresh baseline — see `NEXT.md` for the open
10-team and dress-rehearsal gates.

## 1. Why this receipt exists

The question asked was narrow: starting from a clean checkout on a machine whose
previous Oct26 work had been removed, do the problems seen before still occur?
Mostly no. One real defect was found, fixed, and given a regression test. One
failure that looked like a repository bug turned out to be host contamination
from the previous setup, and is worth recording because it will recur.

## 2. Environment (measured, not assumed)

| Item | Value |
|---|---|
| OS | Windows 10/11 workstation |
| CPU / RAM / disk | 20 logical cores / 31.7 GiB / 238 GB free |
| Docker | Docker Desktop, engine 29.8.0, Linux containers |
| Docker memory cap | **15.5 GiB** (`MemTotal=16603844608`) against 31.7 GiB host RAM |
| Python / Git / Git LFS | 3.12.10 / 2.54.0.windows.1 / 3.7.1 |

The Docker memory cap is a real constraint for event sizing, not a defect: the
README sizes the stack at 32 GB host RAM, and a 2-team pilot fits inside 15.5 GiB
while the 10-team rehearsal does not. Recorded, not changed — raising it is a
host reconfiguration decision.

## 3. What was verified

| Step | Command | Result |
|---|---|---|
| 1 | `git clone` + `git lfs fsck` | PASS — 10/10 LFS objects hash-verified, 5.68 GiB |
| 2 | `python -m unittest discover -s tests` | **1 error** — `test_bounded_http`, see §4 |
| 3 | `python -m ridge.deploy doctor` | PASS — `ready_for_up: true` |
| 4 | `python -m ridge.case_template --destination work/case-template` | PASS — archive OID matches its LFS pointer |
| 5 | `python -m ridge.deploy build --component iris/ctfd/integration` | PASS |
| 6 | `python -m ridge.deploy build --component desktop` | **FAIL** — host contamination, see §5 |
| 7 | `python -m ridge.deploy build --component all` (after fix) | PASS |
| 8 | `python -m ridge.deploy verify-build` | PASS — 4/4 receipts, exit 0 |
| 9 | `python -m unittest discover -s tests` (after fix) | PASS — 395 tests, OK |

Final image receipts, all on source fingerprint `05d59b6c40a10e9db`:

| Component | Image | Image ID (first 12) |
|---|---|---|
| iris | `silent-ridge-iris:dev` | `76d5aad1dc40` |
| ctfd | `silent-ridge-ctfd:dev` | `350248fd9311` |
| integration | `silent-ridge-integration:dev` | `f82b8b20febe` |
| desktop | `silent-ridge-desktop:dev` | `91f281eb5bf4` |

Not done, deliberately: no `up`, no `start`, no event, no Guacamole session, no
Autopsy keyword-search acceptance, no ten-team claim. Those are the F03/F06
gates in `NEXT.md` and this receipt does not touch them.

## 4. The one real defect: rejected connections reset instead of returning 503

**Symptom.** `tests/test_bounded_http.py::test_slow_body_times_out_and_handler_cap_rejects_excess`
failed intermittently, roughly 1 run in 5, only on Windows. The client received
`ConnectionAbortedError [WinError 10053]` where the test asserted a
`503 Service Unavailable`.

**Root cause, established before any edit.** `BoundedThreadingHTTPServer._reject_busy`
(`bounded_http.py`) drains the peer's already-queued request bytes before writing
the 503, because closing a Windows socket with unread data makes Windows send an
RST that discards the response. The drain sampled the socket with a **single
non-blocking `recv`**, which races the client's `sendall`: when the request was
still in flight the read returned nothing, the socket was closed with data
unread, and the peer got a reset instead of the 503.

An instrumented subclass recorded the drain result on 20 consecutive runs:

- 9/20 runs aborted with `WinError 10053`; every abort had `drain_bytes=0`.
- Every run that drained 48 bytes succeeded, and no run with `drain_bytes=48`
  ever aborted.

The correlation was exact, so the mechanism is confirmed rather than inferred.

**Fix.** Drain with a short bounded blocking budget (`min(request_timeout,
0.25)`) and retry on timeout, so a request that is merely in flight is still
consumed before the response is written. The peer can no longer decide by its own
timing whether it receives a response or a reset.

**Regression test.** `test_rejection_survives_a_request_still_in_flight` repeats
the reject-under-load sequence 25 times per run and fails explicitly on
`ConnectionAbortedError`. Proven to actually guard the fix: against the unpatched
`bounded_http.py` it failed 12–19 times per run across 8 runs (100% detection);
against the patch it passes reliably.

**Files changed:** `bounded_http.py`, `tests/test_bounded_http.py`.

## 5. The failure that was not a repository bug

`build --component desktop` failed at `Dockerfile:106`:

```
useradd: user 'participant' already exists
... exit code: 9
```

That line deletes a pre-existing `ubuntu` user and then creates `participant`, so
it assumes a pristine `ubuntu:24.04`. The failure was correct behaviour against a
corrupted base: on this host, `ubuntu:24.04` and `silent-ridge-desktop:dev` were
**the same image** (`6ae4ae95788c`, tagged 2 days earlier), because a previous
build had tagged its finished desktop image over the stock base tag. The "base"
image already contained `participant`, Autopsy, Cutter, Firefox and
`/opt/silent-ridge`.

Removing the clobbered tag and re-pulling produced a pristine base
(`008173c23f95`: no `participant`, empty `/opt`), after which the desktop image
built with **no source change at all**.

**No Dockerfile change is warranted.** The build failed loudly and correctly;
loosening `useradd` to tolerate an existing user would have let a polluted base
silently produce a wrong image. `verify-build` independently refused the stale
receipts rather than letting a mismatched image run, which is the intended
behaviour of that gate.

**Carry-forward risk.** `--pull=false` prefers a cached base, so any host that has
had `ubuntu:24.04` (or another base tag) overwritten will fail the same way
confusingly. A first-time-setup check that verifies base images match the
upstream digests they are supposed to resolve to, before building, would turn
this from a late, confusing `useradd` error into an early, accurate one. Not
implemented here — no task card covers it.

## 6. Host cleanup performed (disposable, previous event)

The previous setup had never been torn down and was occupying the host. On the
organizer's explicit instruction, the following were removed: 25 `ridge-oct26-*`
containers, 40 named `ridge-oct26-*` volumes, 3 orphaned anonymous volumes
(created `2026-09-26T23:09:07Z`, referenced by no container), the `ridge-oct26-*`
networks, the clobbered `ubuntu:24.04` tag, and the two stale `silent-ridge-*`
images built from old source.

This was a **destructive full wipe**: the prior event's IRIS and CTFd databases,
findings, scores and per-team case/workspace/scratch data are gone, together with
the 10-team deployment. No recovery set was taken first, because teardown was
requested as a clean slate. `docker volume ls` afterwards returned zero volumes.

## 7. Honest limits

- Single Windows workstation, single build, no Linux or macOS reproduction. The
  §4 defect is Windows-specific; the fix is written to be harmless elsewhere but
  has not been exercised on another platform.
- Docker memory cap (15.5 GiB) was never raised, so no claim is made about
  10-team capacity on this host.
- Build receipts prove images were built and verified. They do not prove any
  service started, any participant connected, or any question was answered.
- The §5 base-image check is a recommendation only. Nothing in the repository
  detects a clobbered base tag today.
- The working change in §4 is uncommitted and unpushed.
