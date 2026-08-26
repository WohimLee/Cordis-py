# Plan 00: Foundation Decisions

Status: Not started

## Goal

Resolve implementation-shaping decisions and establish reproducible repository commands before writing runtime code.

## Dependencies

- Architecture chapters 01–12 reviewed;
- vendored Cordis source remains available as the behavioral reference.

## In scope

- minimum Python version;
- packaging and dependency-management tool;
- test, type-check, lint and formatting commands;
- async-first lifecycle decision;
- Context service-access API decision;
- initial package/module layout;
- scenario format for TypeScript/Python behavior comparison.

## Out of scope

- runtime implementation;
- Loader implementation;
- Harness service plugins.

## Work packages

- [ ] Inventory available Python/tooling constraints.
- [ ] Decide minimum Python version and document consequences.
- [ ] Decide lifecycle async contract and synchronous convenience boundary.
- [ ] Decide dynamic `ctx.service` versus explicit `ctx.get()` contract.
- [ ] Select build, environment, test, lint and type-check tools.
- [ ] Accept or replace proposed ADRs.
- [ ] Write canonical commands into `AGENTS.md` and README.
- [ ] Define the first cross-language behavior fixture.

## Acceptance criteria

- A clean checkout can install dependencies and run an empty test suite with documented commands.
- Public lifecycle signatures are no longer blocked by open decisions.
- Phase 1 can begin without choosing infrastructure ad hoc.
- All accepted choices have an ADR or an explicit note that they are reversible implementation details.

## Verification

- Execute install, lint, type-check and test commands from a clean environment.
- Confirm build metadata produces an importable wheel.
- Review all relative documentation links.

## Open decisions

- Python 3.11 versus 3.12 minimum;
- uv/hatch/pdm/standard pip workflow;
- pyright versus mypy;
- Ruff formatting policy;
- whether `Fiber.__await__` belongs in the first public API.
