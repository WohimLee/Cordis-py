# Architecture Decision Records

ADRs preserve durable implementation decisions and their consequences. Plans may reference proposed ADRs, but public contracts must not rely on them until their status is Accepted.

## Status values

- `Proposed`: under discussion and not authoritative;
- `Accepted`: current architecture rule;
- `Superseded`: replaced by a newer ADR;
- `Rejected`: considered but not selected.

## Naming

Use `NNNN-short-title.md`. Never rewrite the reasoning of an accepted ADR to make history look cleaner; supersede it with a new ADR.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-async-first-lifecycle.md) | Proposed | Use an async-first lifecycle |
| [0002](0002-context-service-access.md) | Proposed | Offer dynamic and explicit service access |
| [0003](0003-behavioral-compatibility.md) | Accepted | Target behavior rather than syntax compatibility |
