# Current State

Updated: 2026-09-03

## Project phase

Phases 0 through 5 are complete.

## Active plan

[Plan 05: Cordis Core Equivalence](../docs/plans/05-cordis-core-equivalence.md) (complete)

## Completed

- [x] Implemented the lifecycle-correct Context, Registry, Reflect, Fiber, Effect, Events, Service and Logger core.
- [x] Implemented the Loader transaction runtime and representative keyless Harness profile.
- [x] Classified every vendored Cordis Core 4.0.2 public contract and documented each Python language difference.
- [x] Aligned canonical portable concepts, names, signatures, errors and lifecycle behavior.
- [x] Added Context-bound Events, Reflect, Registry and Logger service facades without duplicating backing services.
- [x] Made Fiber directly awaitable and matched validation, Effect metadata, service availability and Registry deletion contracts.
- [x] Removed redundant compatibility aliases and kept function-plugin dependency metadata in canonical `.inject` form.
- [x] Moved project-specific call-chain observation into the separate 27-line `cordis_observer` package.
- [x] Matched all 21 paired Cordis 4.0.2/Python scenarios (`004` through `024`) exactly after normalization.
- [x] Reviewed final Core size: 2,686 Python lines versus the 1,794-line baseline and 2,693-line TypeScript reference.

## Verification

- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed (81 files).
- `uv run pyright`: passed with zero errors and warnings.
- `uv run pytest`: passed, 76 tests.
- `uv build`: passed for sdist and wheel.
- `git diff --check`: passed.
- Twenty-one paired TypeScript/Python Core scenarios: exact normalized matches.

## Blockers

None.

## Next action

No planned implementation remains. The working tree is ready for review and a user-controlled commit/release.

## Resolved decisions

- Python 3.11+ with Python 3.12 for local development;
- async-first, dynamically injected lifecycle semantics;
- vendored Cordis Core 4.0.2 behavior as the compatibility reference;
- `await fiber`/`fiber.wait()`, `Context.is_context()` and `global_` as keyword-safe Python spellings;
- one scheduler, service store, event bus and Effect implementation per capability;
- Python-only Loader, typing helpers and observer remain explicitly outside the equivalence claim.

## Working tree scope

Phases 0 through 5 are complete; the current uncommitted changes comprise the documented Cordis Core equivalence implementation and verification artifacts.
