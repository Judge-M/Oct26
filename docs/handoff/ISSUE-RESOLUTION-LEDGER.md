# Issue Resolution Ledger (#184–#197)

Auditable mapping of the nine open issues to the commits and PRs that resolve
them. All nine are fixed by commits merged into `origin/main` (audit base
`2c0e169`, every cited commit verified reachable). Preparation history for
#193: its fix branch was integrated onto this branch as cherry-pick `c2b9fbe`
(from `fix/issue-193-stress-tracker@7f572ba`) while the branch was based on
`690df9b`; upstream PR #207 then merged `7f572ba` into `main`, so the
redundant cherry-pick was rebased away and #193 is cited by its merged
upstream commit here.

No GitHub issue comments were posted and no issues were closed or merged as
part of this ledger. Merging this branch is the maintainer's call; GitHub will
close all nine issues via the `Fixes` lines in the ledger commit when it is
merged.

## Ledger

| Issue | Symptom | Resolution | Status |
|---|---|---|---|
| #184 | `build --pull=false` fails late/confusingly when a cached base tag was overwritten | `8b5f81b` (fail build early), PR #205 (merge `c8fb31e`) | Merged to `origin/main` |
| #187 | Source builds cannot produce the content assets `up` requires | `de0132d` + `40ebfd0` (preflight fails closed; `asset()` path spelling), PR #200 (merge `b8bae18`) | Merged to `origin/main` |
| #188 | Full-content walkthrough has an undocumented generation prerequisite | `fa90efb` (document `expanded/author.py` prerequisite), PR #202 (merge `cfe98af`) | Merged to `origin/main` |
| #190 | Taught evidence paths for 3 of 80 questions never reach their answers | `d2ef1ef` + `d917e5f` (fix 3 + 3 more paths, live-play audit), PR #192 (merge `76b767f`) | Merged to `origin/main` |
| #191 | Windows flake: `tests/test_load.py` teardown left test HTTP servers open | `137dfb5` (close servers after joining serve thread), PR #201 (merge `c6305fe`) | Merged to `origin/main` |
| #193 | 5-team stress: two teams scored zero and blamed the product; undeclared CTFd login rate limit (HTTP 429) | `7f572ba` (declare the 429 sign-in budget in the participant guide + regression test), PR #207 (merge `2c0e169`) | Merged to `origin/main` |
| #194 | Gate-off queue page shows no controls/explanation, reads as broken | `234ce3c` (explain absence in every gate-off state), PR #206 (merge `690df9b`) | Merged to `origin/main` |
| #195 | Answer-format grading loses correct facts (6 of 8 wrong answers) | `814f5dd` (normalize answer surface forms before grading), PR #203 (merge `48d6cbe`) | Merged to `origin/main` |
| #197 | No single day-of entry point for deck/operator material | `8323682` (offline presenter landing page), PR #204 (merge `6976114`) | Merged to `origin/main` |

## Verification

Each merged fix commit is an ancestor of `origin/main` (run from any clone
after `git fetch origin`; all returned true at audit time, `origin/main` =
`2c0e169`):

```bash
for s in 8b5f81b de0132d 40ebfd0 fa90efb d2ef1ef d917e5f 137dfb5 7f572ba 234ce3c 814f5dd 8323682; do
  git merge-base --is-ancestor "$s" origin/main && echo "$s in origin/main"
done
```

Focused test run on this branch (Python 3.13, pytest 9.1.1,
`python -m pytest -q <files>`):

| Tests | Covers | Result |
|---|---|---|
| `tests/test_question_matrix.py` (incl. `test_guide_documents_the_ctfd_login_rate_limit`) | #193, #190 | pass |
| `tests/test_autopsy_paths.py` | #190 | pass |
| `tests/test_answer_format.py` | #195 | pass |
| `tests/test_queue_status.py` | #194 | pass |
| `tests/test_base_image_preflight.py` | #184 | pass |
| `tests/test_wazuh_config_preflight.py` | #187 | pass |
| `tests/test_presenter_landing.py` | #197 | pass |
| `tests/test_readiness_docs.py` | #188 | pass |
| `tests/test_load.py` | #191 | pass |

Aggregate: **101 passed, 1 skipped in 20.77s** (skip is a pre-existing
environment-gated test, not related to any ledger entry).

## Limitations

- #188 is a documentation fix; `test_readiness_docs.py` passing shows no
  regression, but the prerequisite text itself was verified by reading
  `fa90efb`, not by an automated assertion.
- #191's original symptom was a Windows-only flake; the verification run above
  is Linux, where `tests/test_load.py` passes as it did before the fix. The
  fix removes the teardown race that could hang on Windows; it was not
  reproduced on native Windows here.
- #193 is verified by the `test_guide_documents_the_ctfd_login_rate_limit`
  regression test shipped in `7f572ba`; the full 5-team stress scenario was
  not re-run.
- Issue states on GitHub remain `open`; closing happens only when this branch
  is merged (or via `gh issue close`, deliberately not used).
