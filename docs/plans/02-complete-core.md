# Plan 02: Complete Core

Status: Not started

## Goal

Complete the reflection, configuration, lifecycle diagnostics and logging behavior required to describe the full vendored Cordis core.

## Dependencies

- Plan 01 complete and verified.

## In scope

- Reflect set, accessor, mixin and bind;
- Service base class, callable services and availability checks;
- intercept config ancestry and custom merge;
- configuration validator protocol and adapters;
- Fiber wait, restart and update waterfall;
- internal plugin/status/config/service/get/set/listener/dispatch events;
- effect tree diagnostics and traceback context;
- Logger, LoggerService and Exporter;
- cleanup error aggregation and lifecycle race hardening.

## Out of scope

- configuration files and dynamic module resolution;
- file watching and HMR;
- Harness-specific services.

## Work packages

- [ ] Complete Reflect property model and ownership validation.
- [ ] Implement Service convenience layer over Reflect.
- [ ] Implement intercept resolution and validator adapters.
- [ ] Implement update/restart with waterfall veto.
- [ ] Implement internal events and their exception policies.
- [ ] Implement Logger and lifecycle-owned exporters.
- [ ] Expose side-effect-free runtime diagnostics.
- [ ] Complete async setup/dispose/reload race matrix.
- [ ] Expand cross-language behavior fixtures.

## Acceptance criteria

- Reflect writes enforce provider ownership.
- Config failures leave no partial service/listener state.
- Update validates before replacing an active configuration.
- Restart cannot overlap another epoch lifecycle.
- Internal observation events cannot break mandatory cleanup.
- Effect diagnostics accurately represent live ownership.
- Every lifecycle race settles in a documented stable state.

## Verification

- Complete core unit and race suites.
- Cross-language scenarios for update, failure and disposal.
- Full lint, type-check, test and package build.
