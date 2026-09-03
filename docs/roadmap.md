# Cordis-py Roadmap

This roadmap defines project phases and exit criteria. Detailed execution steps live in [docs/plans](plans/README.md); current progress lives in [.agents/STATE.md](../.agents/STATE.md).

## Phase 0: Foundation decisions

Goal: make implementation-shaping choices explicit before scaffolding code.

Deliverables:

- supported Python version;
- package/build/test/type-check toolchain;
- async lifecycle contract;
- dynamic Context access contract;
- initial public API and compatibility policy;
- cross-language scenario-test format.

Exit criteria:

- foundational ADRs are accepted;
- Phase 1 plan has no blocking open questions;
- repository commands are documented in `AGENTS.md`.

## Phase 1: Semantic core

Goal: implement the smallest lifecycle-correct Cordis runtime.

Deliverables:

- errors and public protocols;
- Effect/Disposable machinery;
- Context and scoped derivation;
- PluginSpec, RegistryService and PluginRuntime;
- service provide/get and Inject;
- Fiber dependency epoch and state machine;
- five event dispatch modes;
- focused and integration tests.

Exit criteria:

- plugin load order does not affect dependency-driven activation;
- provider removal unloads consumers;
- provider restoration reloads consumers with a new epoch;
- resources clean up exactly once;
- parent disposal recursively disposes children;
- full Phase 1 verification passes.

## Phase 2: Complete core

Goal: cover the full vendored Cordis core behavior needed by Harness.

Deliverables:

- Reflect accessor, set, mixin and bind;
- Service availability checks and config merging;
- configuration validation;
- Fiber update, restart and diagnostics;
- internal lifecycle events;
- LoggerService and Exporter model;
- async setup/dispose race handling and aggregate errors.

Exit criteria:

- lifecycle race matrix passes deterministically;
- update and restart match documented waterfall behavior;
- diagnostics are read-only and side-effect free;
- cross-language core scenarios pass.

## Phase 3: Configuration runtime

Goal: turn declarative configuration into a managed plugin tree.

Deliverables:

- YAML/TOML-neutral Loader model;
- Python `module:attribute` resolver;
- include, overlay and group composition;
- environment interpolation without arbitrary code execution;
- configuration update and rollback;
- optional file/module HMR.

Exit criteria:

- Loader never performs manual service dependency ordering;
- invalid updates preserve the previous valid runtime;
- include cycles and invalid plugin references fail with source locations;
- HMR follows normal Fiber cleanup paths.

## Phase 4: DeepSeek Harness compatibility

Goal: validate Cordis-py through representative Harness capability seams.

Deliverables:

- service-definition/provider/consumer examples;
- representative LLM, tools, sessions and agent-loop plugin composition;
- Python configuration profile;
- TypeScript/Python transcript or event-sequence comparisons;
- compatibility matrix and documented intentional differences.

Exit criteria:

- replacing a provider causes the expected dependent plugin cascade;
- representative Harness composition runs without manual boot ordering;
- known deviations are explicit and tested;
- project documentation supports a new contributor implementing a plugin.

## Phase 5: Cordis Core equivalence

Goal: align Cordis-py with the concepts, public API and observable behavior of vendored `@deepseek-ai/cordis` 4.0.2, except for explicit Python language differences.

Deliverables:

- source-checked Cordis Core API and behavior matrix;
- paired TypeScript/Python behavior runner and scenarios;
- aligned Context, Registry, Fiber, Effect, Events, Reflect, Service and Logger contracts;
- documented Python spellings for APIs blocked by language syntax;
- removal of redundant pre-equivalence abstractions and aliases.

Exit criteria:

- every Cordis Core public API is classified and evidenced;
- exact and equivalent items pass their cross-language contract tests;
- no unexplained capability difference remains;
- no compatibility work introduces a second runtime mechanism;
- source growth and all retained compatibility scaffolding pass a redundancy review.

## Phase status

| Phase | Status | Plan |
| --- | --- | --- |
| 0. Foundation decisions | Complete | [00-foundation.md](plans/00-foundation.md) |
| 1. Semantic core | Complete | [01-semantic-core.md](plans/01-semantic-core.md) |
| 2. Complete core | Complete | [02-complete-core.md](plans/02-complete-core.md) |
| 3. Configuration runtime | Complete | [03-configuration-runtime.md](plans/03-configuration-runtime.md) |
| 4. Harness compatibility | Complete | [04-harness-compatibility.md](plans/04-harness-compatibility.md) |
| 5. Cordis Core equivalence | Complete | [05-cordis-core-equivalence.md](plans/05-cordis-core-equivalence.md) |
