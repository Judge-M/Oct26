# Review risk register

Findings from a full-repository review, with disposition. Items marked **Fixed**
changed behaviour in this branch; **Documented** items are accepted or require a
decision outside the code (host policy, event planning or infrastructure).

## Fixed in this branch

### R1. Duplicated pause-aware clock logic
`app/exercise_clock.py` and `scripts/control.py` each implemented the elapsed-time
mapping independently, so a change to one could silently diverge from the other.
The canonical projection now lives in `app/exercise_clock.py` (`project`), and
`scripts/control.py:position` delegates to it. `test_clock_projection_is_shared`
locks the two entry points together.

### R2. No rate limit on participant `/api/login`
The facilitator panel throttled sign-in attempts but the participant service did
not, allowing unbounded password guessing against cell accounts. `/api/login` now
allows 20 attempts per minute, mirroring the panel, and returns HTTP 429.
Covered by `test_login_attempts_are_throttled`. The limit is global to the process
(not per source address), matching the existing panel behaviour.

### R3. Stale `control.lock` had no diagnostics
A crashed controller command left `control.lock` with no indication of its owner,
and the error only said another command was active. The lock file now records
`pid`, `host` and UTC at acquisition, and the conflict error prints them so the
operator can judge whether the holder is dead before clearing the lock. The lock
is still never removed automatically, per `docs/controller-ledger.md`.
Covered by `test_lock_error_reports_holder`.

### R4. Monkey-patched test methods
`tests/test_analysis.py` attached two test functions to the class after its
definition instead of declaring methods in the class body, which is fragile for
discovery and refactoring. Both are now ordinary methods.

## Documented (accepted or out of code scope)

### R5. Facilitator answers are public
`solutions.md`, `ground-truth.md`, `controller-guide.md`, `assessment-aar.md` and
`cell-coaching.md` ship in a public repository. This is a deliberate, documented
property of the coached version. A blind or assessed run requires a private
variation; changing names alone does not protect the conclusions. No code change.

### R6. Release crash window
`exercise.py:_release` renames the staging directory into `public` before writing
the ledger and release log, so a crash in that window fails `verify` and requires
manual recovery from a known-consistent backup. `docs/architecture.md` and
`docs/controller-ledger.md` describe the failure and forbid "repairing" a manifest.
Closing the window fully would need a transactional journal across the vault,
public tree and ledger; deferred as a design change.

### R7. Windows ACL isolation
`init()` calls `chmod`, which does not establish Windows ACLs, so runtime and
export secrecy depends on host ACLs that the code does not set. Documented in
`docs/architecture.md`; deployment must restrict `runtime/` and `exports/` on the
Windows host. No portable code fix.

### R8. Container/offline validation is CI-only
`docs/validation.md` lists site-specific checks that CI cannot cover: actual Jira
import and permissions, participant seats, lab firewall/TLS, a clean physical
offline host, accessibility, and a timed human rehearsal. CI is not evidence those
passed. Process item for the event owner.
