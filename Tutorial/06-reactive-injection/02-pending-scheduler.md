# 从 PENDING 到 ACTIVE

## Step 3：Fiber 检查全部依赖

Fiber 激活前逐个查询 Inject：

```python
def dependencies_ready(self) -> bool:
    return all(self.ctx.get(name) is not None for name in self.runtime.inject)
```

如果任何 Service 缺失，Fiber 不执行 Plugin callback，而是停在 PENDING：

```text
需要 database + cache

database 存在，cache 缺失
            ↓
          PENDING
```

PENDING 不是错误。它表示 Fiber 已经挂载，但当前条件不足。

运行：

```bash
uv run pytest Tutorial/06-reactive-injection/src/test_chapter06.py -k waits_for_provider
```

测试会先确认 Consumer callback 没有执行。

## Step 4：Registry 建立反向索引

Fiber 知道自己需要哪些 Service，但 Service 出现时，Reflect 还需要知道应该通知谁。

Registry 建立一份反向索引：

```text
database → {Consumer Fiber A, Consumer Fiber B}
cache    → {Consumer Fiber B}
```

创建 Fiber 时登记：

```python
for name in runtime.inject:
    self._dependents.setdefault(name, set()).add(fiber)
```

这不是手工拓扑排序。Registry 没有计算固定启动顺序，只记录“哪个 Fiber 关心哪个 Service”。

## Step 5：Reflect 通知 Registry

Provider 调用 `provide("database", value)` 时：

```text
Reflect 保存 database Impl
    ↓
Reflect.notify("database")
    ↓
Registry.refresh("database")
    ↓
所有 database Consumer 重新检查依赖
```

如果依赖已经齐全，Fiber 才进入 LOADING 并执行 callback。

### 一个容易忽略的时机

Provider 在自己的 LOADING 阶段调用 `provide()`。Strict lookup 此时仍看不到 Service，所以第一次 notify 后 Consumer 还是 PENDING。

Provider callback 完成并进入 ACTIVE 后，必须再次通知自己提供过的 Service：

```text
provide 时通知：Impl 已出现，但 Provider 仍 LOADING
ACTIVE 时通知：Impl 现在可以被 strict lookup 使用
```

少掉第二次通知，Consumer 会永远停在 PENDING。

### Checkpoint B

Registry 与 Reflect 现在形成了单向调度链：

```text
Service 变化 → 找到 Consumer → Consumer 自己检查全部 Inject
```

Reflect 只报告事实，不直接执行 Plugin；Fiber 仍然是 Lifecycle 的唯一执行者。
