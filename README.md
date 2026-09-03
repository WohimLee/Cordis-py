# Cordis-py

Cordis-py is a behavioral Python reproduction of the Cordis plugin runtime vendored by DeepSeek Harness.

The runtime core, declarative Loader and representative DeepSeek Harness composition are implemented: scoped Contexts, dependency-driven Fibers, lifecycle-owned Effects, safe YAML/TOML composition, transactional updates and a keyless LLM/tools/sessions/agent-loop profile. See the [architecture index](docs/architecture/README.md), [compatibility matrix](docs/compatibility.md), and [current state](.agents/STATE.md).

## Core model

```text
Context receives a Plugin
    ↓
Registry normalizes it and creates a Fiber for this mount
    ↓
Reflect resolves the Fiber's injected Services in the current Context scope
    ↓
Fiber runs the Plugin when every dependency is available
    ↓
Effects own its Services, listeners, child Fibers and user resources
```

Plugin is reusable behavior, PluginRuntime is its shared Registry record, Fiber is one concrete mount, Context is that mount's scoped capability view, and Effect gives every long-lived resource a reversible owner. Fiber ownership forms a lifecycle tree; Context derivation forms a related scope structure; service dependencies and event subscriptions form graphs across those structures. See the [core object model](docs/architecture/02-core-model.md), [lifecycle design](docs/architecture/04-lifecycle.md), and [PluginRuntime tutorial](Tutorial/04-plugin-registry/02-plugin-runtime.md).

## Development

Python 3.11 or newer is supported. The checked-in `.python-version` selects Python 3.12 for local development.

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build
```

Implementation work follows the numbered files in [docs/plans](docs/plans/README.md).

## Semantic-core example

```python
from cordis import Context, Service, inject


class Counter(Service):
    provide = "counter"

    def __init__(self, ctx, config=None):
        self.value = 0
        super().__init__(ctx)


@inject("counter")
def greeter(ctx, config):
    ctx.on("ready", lambda: print(ctx.counter.value))


async def main():
    ctx = Context()
    counter = ctx.plugin(Counter)
    greeter_fiber = ctx.plugin(greeter)
    await counter.wait()
    await greeter_fiber.wait()
    ctx.emit("ready")
    await ctx.aclose()
```
