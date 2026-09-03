# 03 — 为什么需要 Fiber

第 01 章用 Context 表示 Plugin 的运行作用域，第 02 章用 Effect 表示一个可逆操作。现在还缺少一个对象，把下面三件事连在一起：

- 哪个 Plugin 正在运行；
- 它目前处于什么 Lifecycle 状态；
- 它拥有哪一些 Effect。

Cordis 使用 **Fiber** 表示“一次 Plugin 挂载及其生命周期”。

## Context 和 Fiber 不是同一个概念

Context 回答：

> Plugin 在哪个作用域中使用 Runtime？

Fiber 回答：

> 这一次 Plugin 挂载现在是什么状态，它创建了哪些资源？

同一个 Plugin 可以挂载多次，因此也可以有多个 Fiber。一个 Fiber 在依赖变化后还可能经历多个 activation Epoch。现在先只实现一次 activation，Epoch 留到第 07 章。

## 本章需要的状态

正式 Cordis 有六个 `FiberState`。本章先使用完成最小 Lifecycle 所需的五个正式名称：

```python
class FiberState(StrEnum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    ACTIVE = "ACTIVE"
    UNLOADING = "UNLOADING"
    DISPOSED = "DISPOSED"
```

- **PENDING**：Fiber 已创建，等待开始；
- **LOADING**：正在执行 Plugin setup；
- **ACTIVE**：setup 已完成，Plugin 正在运行；
- **UNLOADING**：正在执行 Cleanup；
- **DISPOSED**：已经永久销毁，不能再次运行。

`FAILED` 会在完整状态机章节加入。现在不要一次引入全部失败恢复逻辑。

## Step 0：定义 Fiber 外形

Fiber 先保存 callback、parent、Plugin Context 和 Effect 列表：

```python
class Fiber:
    def __init__(self, parent_context, callback, parent):
        self.parent = parent
        self.callback = callback
        self.state = FiberState.PENDING
        self.ctx = parent_context._derive(self)
        self._effects = []
```

注意 `self.ctx` 是一个新的 child Context。Plugin 不直接使用调用方的 Context，而是在属于自己 Fiber 的 Context 中运行。

## Step 1：让 `Context.plugin()` 返回 Fiber

```python
def plugin(self, callback: Plugin) -> Fiber:
    fiber = Fiber(self, callback, self.fiber)
    fiber.start()
    return fiber
```

`plugin()` 不等待 Plugin 执行完成，而是立即返回 Fiber。调用者可以：

```python
fiber = context.plugin(plugin)
await fiber
```

`await fiber` 等待 setup 稳定，并返回 Fiber 自己。

运行：

```bash
uv run pytest Tutorial/03-minimal-fiber/src/test_chapter03.py -k activation
```

### Checkpoint A

```text
Context.plugin(callback)
    ↓
创建 Fiber：PENDING
    ↓
执行 callback：LOADING
    ↓
setup 完成：ACTIVE
```

现在 Fiber 能表示一次运行，但还没有真正拥有 Plugin 创建的资源。
