# Current State

Updated: 2026-08-26

## Project phase

All planned phases are complete.

## Active plan

[Plan 04: Harness Compatibility](../docs/plans/04-harness-compatibility.md) (complete)

## Current task

No active implementation task. Select a post-roadmap enhancement before expanding scope.

## Completed

- [x] Reviewed the vendored Cordis core at an architectural level.
- [x] Wrote and logically ordered the architecture documentation.
- [x] Incorporated the explanatory material from `docs/draft.md`.
- [x] Defined roadmap, implementation plans, ADR convention and agent workflow.
- [x] Resolve Plan 00 decisions.
- [x] Scaffold the Python package and verification toolchain.
- [x] Define the first cross-language provider-replacement scenario.
- [x] Begin semantic core implementation.
- [x] Implement Phase 1 Context, Registry, Reflect, Fiber, Effect and Events.
- [x] Execute the Provider replacement scenario from JSON expectations.
- [x] Complete Reflect accessors, mixins, ownership checks and callback binding.
- [x] Complete Service intercepts and dynamic availability refresh.
- [x] Complete validation, restart and update waterfall behavior.
- [x] Complete internal lifecycle events, logging and runtime diagnostics.
- [x] Harden dependency and shutdown lifecycle races.
- [x] Define immutable parsed Loader entries and mutable runtime Entry state.
- [x] Implement source-aware TOML parsing and restricted environment interpolation.
- [x] Implement allow-listed package/path `module:attribute` resolution.
- [x] Implement relative include expansion and canonical-path cycle detection.
- [x] Implement recursive config/inject overlays addressed by globally stable entry id.
- [x] Preserve included entry source ownership for errors and relative module resolution.
- [x] Mount root and nested entries exclusively through `Context.plugin()`.
- [x] Merge declarative inject metadata without adding a second dependency scheduler.
- [x] Roll back plugin effects and child Fibers when tree mounting fails.
- [x] Reuse existing Fibers for config-only Loader updates.
- [x] Roll back earlier entry updates when a later config update fails.
- [x] Reject structural changes without disturbing the active runtime.
- [x] Preflight structural replacements without importing modules twice.
- [x] Replace changed trees through normal Fiber disposal and mounting.
- [x] Restore the previous valid tree when replacement activation fails.
- [x] Add a thin safe-YAML frontend over the format-neutral parser.
- [x] Support mixed YAML/TOML include graphs.
- [x] Verify Python-specific YAML tags cannot execute code.
- [x] Add host-driven configuration reload through Loader transactions.
- [x] Inventory the current DSH LLM, tools, sessions, agents and agent-loop seams.
- [x] Build a keyless Harness-shaped service profile and YAML configuration.
- [x] Verify provider reload preserves the stable LLM service and Agent Loop Fiber.
- [x] Verify profile shutdown leaves no registry, service or root Effect state.
- [x] Execute language-neutral adapter reload and LLM service-loss scenarios.
- [x] Publish the compatibility matrix and provider-plugin tutorial.

## Verification

- Documentation formatting: `git diff --check` passed.
- Relative Markdown links: repository link check passed.
- `uv sync --dev`: passed; lock file generated.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run pyright`: passed with zero errors.
- `uv run pytest`: passed, 57 tests.
- `uv build`: passed for sdist and wheel.
- Cross-language scenario JSON syntax: passed.
- Phase 2 runtime, diagnostics and lifecycle race tests: passed.

## Blockers

None.

## Next action

Choose whether to add a real Qwen provider smoke test as an optional example, not a core requirement.

## Resolved decisions

- Python 3.11+ with Python 3.12 as the local development version;
- uv, hatchling, pytest, pytest-asyncio, Ruff and Pyright strict;
- async-first lifecycle;
- dynamic and explicit Context service access;
- no initial `Fiber.__await__`.

## Working tree scope

Phases 0 through 4 are complete. Cordis core, Loader, keyless Harness profile, compatibility scenarios and guidance are implemented.
