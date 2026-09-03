# 让 Effect 可调用、可等待

## Step 3：dispose 只能真正开始一次

Effect 保存一个 `_dispose_task`：

```python
def __call__(self):
    if self._dispose_task is None:
        self._dispose_task = asyncio.create_task(self._dispose())
    return self._dispose_task
```

第一次调用 Effect 时创建 Task，之后一直返回同一个 Task：

```python
first = effect()
second = effect()
assert first is second
```

这就是幂等 dispose。多个调用者可以等待同一次清理，不会重复执行 Cleanup。

运行：

```bash
uv run pytest Tutorial/02-effect/src/test_chapter02.py -k shared_dispose
```

## Step 4：Effect 为什么既 callable 又 awaitable

在 DSH Cordis 中，`ctx.effect()` 返回一个 disposer。同步 Effect 可以直接调用，异步 Effect 返回的 disposer 还可以像 Promise 一样等待。

Python 用两个协议表达这两件事：

- `effect()`：调用 Effect，开始 dispose；
- `await effect`：等待 setup 完成，并得到 Effect 自己；
- `await effect()`：开始 dispose，并等待 Cleanup 完成。

示例：

```python
effect = Effect(setup)
disposer = await effect
assert disposer is effect
await disposer()
```

`await effect` 不会清理资源。它只等待 setup 稳定。真正触发清理的是后面的 `effect()`。

## Step 5：等待异步 setup

异步 setup 可能需要一段时间：

```python
async def setup():
    trace.append("setup-start")
    await ready.wait()
    trace.append("setup-end")
    return lambda: trace.append("cleanup")
```

Effect 创建后，setup Task 立即启动。如果这时调用 dispose，Effect 不能直接结束，否则 setup 稍后可能创建出一个无人清理的资源。

正确顺序是：

```text
setup-start
    ↓
收到 dispose 请求
    ↓
等待 setup 完成
    ↓
setup-end
    ↓
cleanup
```

运行：

```bash
uv run pytest Tutorial/02-effect/src/test_chapter02.py -k dispose_waits
```

### Checkpoint B

Effect 现在有两个独立的等待点：

```text
await effect     等待 setup
await effect()   等待 dispose
```

把两者分开后，Runtime 才能在异步 setup 尚未结束时安全接收卸载请求。
