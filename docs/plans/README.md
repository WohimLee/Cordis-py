# Implementation Plans

Plans translate the architecture into bounded implementation phases. Execute them in numeric order unless an accepted ADR changes the dependency.

| Plan | Purpose | Status |
| --- | --- | --- |
| [00 Foundation](00-foundation.md) | Resolve toolchain and public-contract decisions | Not started |
| [01 Semantic core](01-semantic-core.md) | Build the smallest lifecycle-correct runtime | Not started |
| [02 Complete core](02-complete-core.md) | Complete reflection, config, logger and races | Not started |
| [03 Configuration runtime](03-configuration-runtime.md) | Build Loader, Include, Group and HMR | Not started |
| [04 Harness compatibility](04-harness-compatibility.md) | Validate representative DSH composition | Not started |

## Plan format

Every plan contains goal, dependencies, scope, exclusions, ordered work packages, acceptance criteria, verification and open decisions. Checkboxes represent verified outcomes, not code-writing activity.

When work begins, update the plan status and `.agents/STATE.md`. When a plan completes, record verification evidence and update `docs/roadmap.md`.
