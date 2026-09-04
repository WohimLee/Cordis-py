# 09 — 把 Fiber 补成完整状态机

第 07 章的 Fiber 已经能根据 Dependency Epoch 激活、卸载和重新激活，但它把启动失败重新当成了 `PENDING`。这会丢失一个重要事实：

```text
PENDING：现在缺少依赖，还没有尝试启动
FAILED：依赖已经齐全，但启动尝试失败了
```

完整 Fiber 必须让这两种情况可观察，也必须阻止无意义的重复尝试。

## 本章目标

这一章建立六个正式状态，并实现 `wait()`、`restart()`、`update()`、`dispose()` 和状态通知：

```text
PENDING → LOADING → ACTIVE
             │
             └────→ FAILED

ACTIVE / FAILED → UNLOADING → PENDING
任意 live state → UNLOADING → DISPOSED
```

Dependency Epoch 的生成方式已经在第 07 章讲过。本章教学实现用一个可控制的 `dependencies_ready` 函数代表“当前依赖是否齐全”，让注意力集中在状态机本身。

## Step 0：区分稳定态和过渡态

六个状态并不处在同一层：

| 状态 | 类型 | 含义 |
| --- | --- | --- |
| `PENDING` | 稳定态 | Fiber 存在，但依赖不完整 |
| `LOADING` | 过渡态 | 正在验证 config 并执行 Plugin |
| `ACTIVE` | 稳定态 | 当前 activation epoch 已生效 |
| `FAILED` | 稳定态 | 当前 epoch 的启动尝试失败 |
| `UNLOADING` | 过渡态 | 正在清理当前 epoch |
| `DISPOSED` | 最终态 | Fiber 已永久删除 |

“稳定”不是永远不变，而是当前没有 lifecycle transition 正在执行。`await fiber` 或 `fiber.wait()` 等待的正是这种状态。

## Step 1：所有状态变化走同一个入口

不要在各处直接写 `self.state = ...`。统一经过 `_set_state()`：

```python
def _set_state(self, state):
    old_state = self.state
    if old_state is state:
        return
    self.state = state
    for listener in self._status_listeners:
        listener(self, old_state)
```

Listener 收到 Fiber 和 old state；读取 `fiber.state` 就能得到 new state。这与 Cordis 的 `internal/status` 事件参数一致。

统一入口有两个作用：

- 相同状态不会产生假通知；
- Logger、Loader 或测试看到的是同一条状态时间线。

运行：

```bash
uv run pytest Tutorial/09-fiber-state-machine/src/test_chapter09.py -k status
```

## Step 2：用 refresh runner 驱动转换

外部变化只调用 `request_refresh()`，由唯一 runner 判断下一步：

```text
依赖缺失 + ACTIVE/FAILED → unload → PENDING
依赖齐全 + PENDING       → activate
依赖齐全 + ACTIVE        → 保持不变
```

这样 Service 通知、restart 和 update 不需要各写一套激活逻辑。

### Checkpoint A

Fiber state 不是展示用标签。它规定了现在允许执行什么，以及 `wait()` 何时可以向调用者报告稳定结果。
