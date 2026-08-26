# Cross-language behavior scenarios

This directory contains language-neutral scenarios used to compare vendored TypeScript Cordis with Cordis-py.

Each JSON file describes inputs and expected observable events. It does not encode JavaScript object layout, Python representation or implementation-private calls.

## Scenario fields

- `id`: stable scenario identifier;
- `purpose`: behavior being compared;
- `plugins`: abstract providers and consumers;
- `steps`: ordered external actions;
- `expected`: ordered observable state, activation and cleanup events;
- `invariants`: conditions that must hold throughout the scenario.

Python tests execute these expectations directly. Harness-shaped scenarios also record the exact vendored TypeScript source tests or declarations used as behavioral evidence; they compare public outcomes rather than language-specific object layouts.
