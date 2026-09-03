# 02 — 构建 Effect

第 01 章的 Runtime 把所有 Cleanup 放在一个全局列表中。我们先不处理 owner，而是解决更基础的问题：怎样把“创建资源”和“清理资源”合成一个可靠的可逆操作？

Cordis 把它称为 **Effect**。Effect 包含一次 **setup**，以及 setup 产生的一个或多个 **Cleanup / Disposer**。执行 Cleanup 叫作 **dispose**。

## Step 0：普通 Cleanup 的问题

```python
def setup():
    trace.append("open")
    return lambda: trace.append("close")


cleanup = setup()
cleanup()
cleanup()
```

结果是 `close` 出现两次。普通函数不知道自己是否执行过，也不知道 setup 是否仍在进行。

运行：

```bash
uv run pytest Tutorial/02-effect/src/test_chapter02.py -k plain_cleanup
```

## Step 1：收集有效 Cleanup

Effect 创建时立即运行 setup：

```python
class Effect:
    def __init__(self, setup):
        self._cleanups = []
        result = setup()
        self._collect_sync(result)
```

Setup 可以返回 `None`、一个 callable，或者 callable 组成的 iterable。其他结果立即抛出 `TypeError("Invalid effect")`，避免到卸载时才发现资源无法清理。

## Step 2：逆序清理

后创建的资源通常依赖先创建的资源，因此清理顺序要反过来：

```text
创建：外层 → 内层
清理：内层 → 外层
```

Effect 从列表末尾取 Cleanup：

```python
while self._cleanups:
    cleanup = self._cleanups.pop()
    await run_cleanup(cleanup)
```

运行：

```bash
uv run pytest Tutorial/02-effect/src/test_chapter02.py -k reverse_order
```

预期 trace 是 `["second", "first"]`。

### Checkpoint A

Effect 现在把 setup 和 Cleanup 放在同一个对象中，能够检查返回值并按正确顺序撤销资源。下一节继续解决重复 dispose 和异步 setup。
