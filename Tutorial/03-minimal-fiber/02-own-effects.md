# 让 Fiber 拥有 Effect

第 02 章的 Effect 可以安全 dispose，但没有 owner。只要调用者忘记保存 Effect，它仍然会泄漏。

## Step 2：收集 Plugin 返回的 Cleanup

Fiber 不直接调用 callback，而是把 callback 当作 Effect setup。这里有一个不能颠倒的顺序：先把 Effect 放进 owner，再运行用户 callback。

```python
effect = Effect()
self._effects.append(effect)
effect.start(lambda: self.callback(self.ctx))
await effect
```

为什么不能直接写 `Effect(callback)` 后再 append？因为 callback 可能马上调用 `ctx.effect()` 或创建 Child Fiber。如果主 Effect 尚未进入 owner，新资源的登记顺序就会错误，清理顺序也会跟着颠倒。

如果 Plugin 返回 Cleanup，它会被这个 Effect 收集：

```python
def plugin(ctx):
    trace.append("activate")
    return lambda: trace.append("cleanup")
```

调用 `fiber.dispose()` 时，Fiber dispose 自己拥有的全部 Effect：

```python
while self._effects:
    await self._effects.pop().dispose()
```

运行：

```bash
uv run pytest Tutorial/03-minimal-fiber/src/test_chapter03.py -k returned_cleanup
```

## Step 3：实现 `Context.effect()`

Plugin 不一定只返回一个 Cleanup。它可能在运行过程中注册监听器、Service 或后台任务。

Context 把 Effect 交给当前 Fiber：

```python
def effect(self, setup: Setup) -> Effect:
    return self.fiber.install_effect(setup)
```

Plugin 可以写：

```python
def plugin(ctx):
    ctx.effect(lambda: create_resource("first"))
    ctx.effect(lambda: create_resource("second"))
```

两个 Effect 都属于同一个 Fiber。Fiber dispose 时按相反顺序清理它们。

运行：

```bash
uv run pytest Tutorial/03-minimal-fiber/src/test_chapter03.py -k context_effect
```

## Step 4：让 dispose 幂等

和 Effect 一样，Fiber 也保存一个共享 `_dispose_task`。多次调用 `fiber.dispose()` 会返回同一个 Task，不会重复清理资源。

```python
first = fiber.dispose()
second = fiber.dispose()
assert first is second
```

Fiber 的状态变化是：

```text
ACTIVE
  ↓ dispose()
UNLOADING
  ↓ 所有 Effect 清理完成
DISPOSED
```

### Checkpoint B

第 01 章的全局 Cleanup 列表现在可以删除了：

```text
Fiber A
├── Effect A1
└── Effect A2

Fiber B
└── Effect B1
```

Runtime 不再只知道“有哪些 Cleanup”，还知道每个 Effect 属于哪个 Fiber。
