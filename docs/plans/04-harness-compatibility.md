# Plan 04: DeepSeek Harness Compatibility

Status: Not started

## Goal

Prove the runtime through representative DeepSeek Harness capability composition and document intentional compatibility limits.

## Dependencies

- Plan 03 complete;
- representative Harness services selected from current source.

## In scope

- minimal service-definition/provider/consumer pattern;
- representative llm, tools, sessions and agent-loop seams;
- configuration profile assembled through Loader;
- provider replacement and dependent reload scenarios;
- TypeScript/Python event or transcript comparison;
- compatibility matrix and plugin-author tutorial.

## Out of scope

- immediate port of every Harness package;
- byte-for-byte logs or JavaScript object representation;
- matching implementation-private TypeScript APIs.

## Work packages

- [ ] Inventory runtime APIs used by selected Harness packages.
- [ ] Define Python service protocols for representative seams.
- [ ] Implement test providers and consumers.
- [ ] Assemble a runnable profile without manual boot order.
- [ ] Record provider replacement and shutdown sequences.
- [ ] Compare observable behavior with TypeScript fixtures.
- [ ] Publish compatibility matrix and intentional differences.

## Acceptance criteria

- Representative application starts from configuration.
- Provider replacement unloads and reloads the expected dependency subtree.
- Session/tool/agent interactions use services and events rather than concrete imports.
- Shutdown leaves no tracked Effect, task, service or listener.
- A contributor can implement and configure a new plugin from project docs alone.

## Verification

- runnable example profile;
- keyless integration transcript;
- leak-free shutdown assertion;
- compatibility scenario suite;
- full project checks.
