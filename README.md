# Cordis-py

Cordis-py is a behavioral Python reproduction of the Cordis plugin runtime vendored by DeepSeek Harness.

The runtime core, declarative Loader and representative DeepSeek Harness composition are implemented: scoped Contexts, dependency-driven Fibers, lifecycle-owned Effects, safe YAML/TOML composition, transactional updates and a keyless LLM/tools/sessions/agent-loop profile. See the [architecture index](docs/architecture/README.md), [compatibility matrix](docs/compatibility.md), and [current state](.agents/STATE.md).

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
