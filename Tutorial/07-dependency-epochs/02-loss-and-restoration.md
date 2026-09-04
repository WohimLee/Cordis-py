# Service 丢失与恢复

## Step 2：ACTIVE Fiber 发现 Epoch 改变

Consumer ACTIVE 时，Reflect 通知依赖变化。Fiber 重新解析 Epoch：

```text
最新 Epoch == 当前 Epoch → 不做任何事
最新 Epoch != 当前 Epoch → 卸载旧 activation
```

Service 消失时，最新 Epoch 是 `None`：

```text
ACTIVE
  ↓ Service 丢失
UNLOADING
  ↓ 逆序 Cleanup
PENDING
```

运行：

```bash
uv run pytest Tutorial/07-dependency-epochs/src/test_chapter07.py -k service_loss
```

测试同时检查 Cleanup 已执行一次，Consumer 最后处于 PENDING。

## Step 3：Service 恢复后创建新 Epoch

新的 Provider 注册同名 Service 后，Reflect 得到新的 Impl identity：

```text
PENDING
  ↓ Epoch B 完整
LOADING
  ↓ callback 使用 Impl B
ACTIVE
```

同一个 Consumer Fiber 没有被替换。它经历了两次 activation：

```text
Fiber
├── Epoch A：activate → cleanup
└── Epoch B：activate → ...
```

运行：

```bash
uv run pytest Tutorial/07-dependency-epochs/src/test_chapter07.py -k restoration
```

预期 trace：

```python
["activate:A", "cleanup:A", "activate:B"]
```

## Step 4：串行 runner

Service 变化可能连续到来。每次通知都直接创建独立 activation Task，会让两个 Epoch 同时运行。

Fiber 因此只有一个 lifecycle runner：

```python
def refresh(self):
    if self._runner is None or self._runner.done():
        self._runner = asyncio.create_task(self._run())
```

Runner 在循环中反复解析最新 Epoch：

```text
检查 Epoch
    ↓
需要时卸载旧 Epoch
    ↓
Cleanup 完整结束
    ↓
重新检查最新 Epoch
    ↓
需要时激活新 Epoch
```

它不为每次通知排一个固定动作，而是在每个安全边界重新查看最新事实。

### Checkpoint B

Consumer 已经能够在同一个 Fiber 内经历多个 Epoch，而且任意时刻最多只有一个 lifecycle runner 修改它的状态。
