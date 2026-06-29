# Code Review — 2026-06-29

**Effort:** xhigh · **Scope:** full current-branch diff (`git diff @{upstream}...HEAD`)
**Changed files (9):** `src/cryptoswap_wallet/cli.py`, `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.github/workflows/linkcheck.yml`, `lychee.toml`, `Makefile`, `README.md`, `.gitignore`

## Summary

This review covers a diff adding shell tab-completion (argcomplete), a global
pytest warnings-as-errors policy, and a lychee link-checker (pre-push hook plus
a nightly/main CI workflow that auto-files GitHub issues). The most consequential
findings are correctness/robustness issues in the link-checker automation (a
brittle issue-dedup scheme keyed on a generic, human-applyable `report` label
with no stable marker, a first-run failure because the label is never created,
and a churn bug that opens a new issue every break/fix cycle) and the global
`filterwarnings = ["error"]` that turns any future upstream `DeprecationWarning`
into a hard CI and pre-push failure. The remainder are over-broad exclude
regexes, a stale README, and documentation/test/cleanup gaps around the new
argcomplete feature.

**Stats:** 10 finders · 34 candidates · 26 verifier agents · 4 refuted · 15 reported.

---

## Findings (most severe first)

### 1. Link-checker issue dedup keyed on a generic `report` label — CONFIRMED
**`.github/workflows/linkcheck.yml:62`** (same root cause at `:46`, `:62`)

Both the dedup/close loop (lines 47-51) and the heal-close loop (lines 62-64)
select issues solely by `--label report` with no title match or hidden marker.
Any open issue a human (or another workflow) labels `report` for an unrelated
purpose is treated as a link-checker report and gets auto-closed or overwritten
via `gh issue edit --body-file`. The label is generic and not reserved to this
workflow.

> **Failure scenario:** A maintainer opens a tracking issue and tags it `report`.
> The next green link-check run closes it with "All links are now healthy.", or a
> red run overwrites its body with the lychee output, silently destroying the
> human-authored content.

### 2. `gh issue create --label "report"` fails when the label does not exist — CONFIRMED
**`.github/workflows/linkcheck.yml:58`** (same root cause at `:55`)

`gh issue create ... --label "report"` requires the `report` label to already
exist in the repository; gh does not auto-create labels.

> **Failure scenario:** On the very first run that finds a broken link (no prior
> report issue exists, so the `else` branch runs), `gh issue create --label
> "report"` fails because the label has never been created, the step errors, and
> the inaugural link-checker issue is never filed.

### 3. Every break/fix cycle spawns a brand-new issue instead of reopening — CONFIRMED
**`.github/workflows/linkcheck.yml:52`**

The create-or-update step queries `gh issue list --label report --state open`
(line 47), so it can never see a previously auto-closed canonical issue. The
"all links healthy" step (line 62) closes the report issue when links recover.
On the next breakage CANON is empty (the old issue is closed, hence invisible),
so the `else` branch runs `gh issue create` and opens a brand-new issue instead
of reopening the prior one. There is no `gh issue reopen` anywhere in the
workflow.

> **Failure scenario:** Links break (issue #5 opened) → links fixed (#5
> auto-closed with "healthy") → links break again. The workflow creates a fresh
> issue #6 rather than reopening #5. Every break/fix cycle spawns a new issue,
> leaving a trail of stale closed report issues and losing the comment history of
> the original.

### 4. Global `filterwarnings = ["error"]` turns upstream deprecations into hard failures — CONFIRMED
**`pyproject.toml:69`** (same root cause also at `:66`)

Global `filterwarnings = ["error"]` promotes every third-party deprecation to a
hard test failure for a wallet built on libraries known to emit them.

> **Failure scenario:** bitcoinlib, eth-account/eth-abi, and tronpy routinely emit
> DeprecationWarnings on newer Python/dependency releases. With warnings-as-errors
> and no upstream-scoped ignore entries, a routine transitive dependency bump
> turns the entire (otherwise green) test suite red with an unrelated upstream
> deprecation, blocking CI and unrelated PRs until someone adds an ignore line,
> even though the wallet code is correct.

### 5. Over-broad `example` exclude regex matches real domains — CONFIRMED
**`lychee.toml:7`** (same root cause also at `:6`)

The example-domain exclude regex `([a-z0-9-]+\.)*example(\.[a-z]+)?(/|$)` is
unanchored and matches any URL whose host/path contains `example.<tld>` as a
component, including real domains like `example.org` or `myexample.org`.

> **Failure scenario:** A future README/docs link to a genuinely reachable host
> such as `https://myexample.org/page` or `https://example.org/realpage` is
> silently treated as excluded, so if it later 404s the link checker reports it
> green and the dead link ships undetected.

### 6. lychee pre-push hook makes `git push` depend on external link reachability — CONFIRMED
**`.pre-commit-config.yaml:38`**

lychee added as a pre-push hook; previously the pre-push gate was pytest-only, so
`git push` no longer depends solely on local code/test state but on external link
reachability.

> **Failure scenario:** When an external host the repo links to is temporarily
> unreachable or rate-limited beyond the accept list (thorchain.org or the
> liquify.com thornode endpoint in README.md, or the kislyuk/argcomplete anchor),
> `git push` is blocked with a link-check failure even though the committed code
> is correct, forcing the developer to bypass the hook with `--no-verify`.

### 7. Stale 14-day cache can keep a broken link reported-healthy — CONFIRMED
**`.github/workflows/linkcheck.yml:32`**

The lychee step caches results with `--max-cache-age 14d` and the cache key
restores from `cache-lychee-` prefix, so a link that broke can stay
reported-healthy for up to 14 days from a stale cache entry.

> **Failure scenario:** A URL that returned 200 and got cached then goes
> permanently dead; for up to 14 days the nightly cron keeps reading the cached
> 200 and never opens an issue, so the broken link is invisible during the window
> the checker is supposed to catch it.

### 8. PR and nightly-cron runs detect dead links but have no reporting outlet — CONFIRMED
**`.github/workflows/linkcheck.yml:42`**

Issue create/close gated on `github.ref == refs/heads/main`, but PR and
nightly-cron runs still execute the full link check with no reporting outlet.

> **Failure scenario:** On `pull_request` and on the nightly schedule the link
> check runs and can detect dead links, but the reporting steps are skipped (ref
> is not main), so a broken link introduced in a PR or one that rots overnight
> produces no issue and, with `fail:false`, no failed check either. The detection
> work runs but its result is silently discarded on exactly the events meant to
> catch regressions early.

### 9. argcomplete imported unconditionally on every CLI startup — CONFIRMED
**`src/cryptoswap_wallet/cli.py:1112`**

argcomplete is imported unconditionally on every CLI startup though
`autocomplete()` is a no-op unless `_ARGCOMPLETE` is set.

> **Failure scenario:** Every normal `cryptoswap-wallet` invocation (balance,
> list, status, `--help`, and every fast argument-parsing path the module's
> lazy-import design works hard to keep light) eats the cost of `import
> argcomplete` (~11 ms first import) before `parse_args`. The actual
> `argcomplete.autocomplete(parser)` call returns in ~17 µs because it bails
> immediately when `_ARGCOMPLETE` is not in `os.environ` — so the import is paid
> on 100% of real runs to benefit only shell-completion invocations.
>
> **Cheaper alternative:** gate the import on the same env var the library checks:
> `if "_ARGCOMPLETE" in os.environ: import argcomplete; argcomplete.autocomplete(parser)`
> (`os` is already imported at module level) — argcomplete's own recommended
> fast-startup pattern, removing the import from every non-completion run.

### 10. README hook description is stale after this diff — CONFIRMED
**`README.md:144`**

The Development section states "`pre-commit` runs ruff on commit and the unit
tests on push." This diff adds two more hooks not reflected here: a commit-msg
Conventional Commits hook (`.pre-commit-config.yaml:23`) and a pre-push lychee
link-check (`.pre-commit-config.yaml:41`). The README was edited in this same
diff (for argcomplete) but this hook description was left stale, against the
project's own "check whether docs need updating" convention.

> **Failure scenario:** A contributor reads the README, expects only
> ruff-on-commit and tests-on-push, then has a commit rejected for a
> non-Conventional message or a push blocked by an external link being
> unreachable, with no documentation explaining why.

### 11. Shell tab-completion feature not recorded in CHANGELOG — CONFIRMED
**`CHANGELOG.md:9`**

User-facing shell tab-completion feature not recorded in CHANGELOG's
`[Unreleased] > Added` section.

> **Failure scenario:** Violates `~/.claude/CLAUDE.md` ("Check if a CHANGELOG needs
> updating"). The diff adds argcomplete-based shell tab-completion (cli.py
> `main()`, README usage block, `argcomplete>=3` dependency) — a user-facing
> feature on par with the other Added entries (e.g. `--version`, packaging) — yet
> the `[Unreleased]` Added list is left unchanged. On the next release the
> changelog under-reports what shipped.

### 12. New argcomplete code path ships with no test — CONFIRMED
**`src/cryptoswap_wallet/cli.py:1110`**

New argcomplete code path in `main()` ships with no accompanying test.

> **Failure scenario:** Violates `~/.claude/CLAUDE.md` ("Write tests first, then
> implement. Confirm tests are FAILING before adding the fix/feature."). The
> try/import-argcomplete/`autocomplete(parser)` block is a new feature path; grep
> over `tests/` finds no argcomplete or autocomplete reference, so the
> import-guard and the no-arg-completion behavior are unverified. A future
> refactor could silently break completion or crash `main()` in an
> argcomplete-less environment with no test to catch it.

### 13. PyPI exclude uses non-canonical short path — PLAUSIBLE
**`lychee.toml:9`**

The PyPI exclude uses the non-canonical short path
`pypi.org/p/cryptoswap-wallet`, which will not match a canonical
`pypi.org/project/cryptoswap-wallet/` link.

> **Failure scenario:** PyPI project pages live at `/project/<name>/`; the
> `/p/<name>` form is only a redirect shortcut. If a PyPI link is added in the
> canonical `/project/` form before the first release is published, this exclude
> does not match it, the 404 is reported, and the CI link-check fails (opening a
> spurious "Link Checker Report" issue) for a link that was meant to be ignored.

### 14. argcomplete is a hard dependency but guarded as optional — PLAUSIBLE
**`pyproject.toml:29`** (same root cause also at `src/cryptoswap_wallet/cli.py:1112`)

argcomplete added as a hard core dependency, yet cli.py guards the import with
`try/except ImportError` as if optional.

> **Failure scenario:** The two layers contradict each other on whether
> argcomplete is required. Because it is a hard dependency, the `except
> ImportError` branch in cli.py `main()` is dead code that can never fire, so a
> future maintainer reading the try/except will wrongly believe completion is
> optional and waste effort "fixing" an installation path that cannot occur;
> conversely, if completion is meant to be optional it is pulling a
> never-loaded-at-runtime library into every wallet install.

### 15. Pre-push hook and CI link-check have divergent args — PLAUSIBLE
**`.pre-commit-config.yaml:41`**

The pre-push lychee hook and the CI linkcheck workflow are two separate
link-check invocations with divergent args rather than one shared definition.

> **Failure scenario:** The hook passes `--max-cache-age 1d` while the workflow
> passes `--max-cache-age 14d` and `--max-retries 6`; a flaky/rate-limited link
> passes locally on push but fails in CI (or vice versa), so developers and CI
> disagree on link health and the discrepancy is maintained in two places that
> will drift further.

---

## Refuted candidates (not reported as findings)

- **`.github/workflows/linkcheck.yml:56`** — Claim that lychee-action v2 writes to
  `lychee/results.md` so `./lychee/out.md` never exists. **Refuted:** the action's
  `output` input defaults to `lychee/out.md`.
- **`lychee.toml:15`** — Claim that `accept = ["200", "206", "429"]` redundantly
  re-lists default-accepted codes. **Refuted** (only cosmetic, not a defect).
- **`.github/workflows/linkcheck.yml:53`** — Hard-coded `./lychee/out.md` path
  duplicated across two `gh issue` commands. **Refuted.**
- **`lychee.toml:11`** — `bc1q...` exclude is a literal-placeholder special-case
  not covering other address placeholders. **Refuted** (bare addresses aren't
  links anyway).
