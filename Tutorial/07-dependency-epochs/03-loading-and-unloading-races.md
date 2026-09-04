# LOADING 与 UNLOADING 期间的变化

正常路径并不难。真正容易出错的是 Service 恰好在 setup 或 Cleanup 尚未完成时变化。

这里的 **race** 不是比赛，而是“两个异步操作的先后顺序不固定”。测试使用 `asyncio.Event` 精确控制顺序，不用 sleep 猜时间。

## Step 5：LOADING 时 Service 丢失

场景如下：

```text
Consumer 开始 Epoch A setup
    ↓
setup 等待 Event，Fiber 保持 LOADING
    ↓
Provider A 被 dispose
    ↓
setup 恢复并返回 Cleanup
```

错误实现可能直接把 Consumer 发布为 ACTIVE，因为 callback 没报错。

正确实现会在 setup 后重新解析 Epoch：A 已经不存在，因此刚得到的 Cleanup 立即执行，Fiber 回到 PENDING。

```text
LOADING(A) → UNLOADING(A) → PENDING
```

运行：

```bash
uv run pytest Tutorial/07-dependency-epochs/src/test_chapter07.py -k loss_during_loading
```

## Step 6：UNLOADING 时新 Provider 到达

另一个场景：

```text
Consumer 正在 Cleanup Epoch A
    ↓
Provider B 已经到达
```

错误实现可能立刻启动 Epoch B，导致 A 和 B 同时持有资源。

串行 runner 只记录“最新 Epoch 已变化”。它会等待 A 的 Cleanup 完整结束，再重新解析并启动 B：

```text
UNLOADING(A)
    ↓ 等待 Cleanup gate
PENDING
    ↓ 重新读取最新 Impl
LOADING(B)
    ↓
ACTIVE(B)
```

运行：

```bash
uv run pytest Tutorial/07-dependency-epochs/src/test_chapter07.py -k restoration_during_unloading
```

预期 trace 明确证明 `cleanup-end:A` 位于 `activate:B` 之前。

## Step 7：DISPOSED 永久终止

依赖暂时缺失和永久 dispose 不一样：

- PENDING 可以在依赖恢复后创建新 Epoch；
- DISPOSED 不再响应任何 Reflect 通知。

运行：

```bash
uv run pytest Tutorial/07-dependency-epochs/src/test_chapter07.py -k disposed_never_reactivates
```

### Checkpoint C

```text
每个 Fiber：最多一个 runner
每个 Fiber：最多一个正在运行的 Epoch
新 Epoch：必须等待旧 Epoch Cleanup
过期 setup：不能发布 ACTIVE
DISPOSED：永远不能复活
```
