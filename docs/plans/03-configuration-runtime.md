# Plan 03: Configuration Runtime

Status: Not started

## Goal

Build a safe declarative plugin-tree runtime without moving dependency scheduling out of Cordis core.

## Dependencies

- Plan 02 complete;
- Loader entry identity and update behavior reviewed against vendored Loader.

## In scope

- format-neutral Loader Entry model;
- YAML and optional TOML frontend;
- Python `module:attribute` resolver;
- source locations and actionable validation errors;
- include, overlay and group composition;
- environment interpolation;
- enable/disable, update, replace and rollback;
- optional file/module HMR.

## Out of scope

- arbitrary Python expressions in configuration;
- process/container sandboxing;
- Harness capability implementation.

## Work packages

- [ ] Define immutable parsed config and mutable runtime Entry models.
- [ ] Implement safe module resolution and allow-list policy hooks.
- [ ] Implement source-aware parsing and validation.
- [ ] Implement include-cycle detection and overlays.
- [ ] Mount Entry trees using only `ctx.plugin()`.
- [ ] Implement diff-based update and rollback.
- [ ] Add HMR behind an optional dependency/feature boundary.
- [ ] Add security and failure-path tests.

## Acceptance criteria

- Loader does not manually topologically sort service dependencies.
- Relative paths resolve against their source file.
- Invalid updates retain the previous valid runtime.
- Include cycles and missing plugin references report source positions.
- YAML/TOML cannot execute arbitrary Python.
- HMR follows normal Fiber disposal and ownership paths.

## Verification

- Parser and resolver unit tests;
- temporary-directory integration tests;
- update/rollback/HMR lifecycle scenarios;
- full project checks and packaged-resource smoke test.
