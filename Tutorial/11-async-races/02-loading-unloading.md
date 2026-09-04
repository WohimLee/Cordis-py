# Loading 与 Unloading 中的依赖变化

## Step 2：LOADING 时依赖丢失

Plugin callback 可能已经开始，但还没返回 cleanup：

```text
epoch A 可用 → LOADING(A)
                  │ await
epoch A 消失 ─────┘
```

不能强行中断 callback，否则它稍后产生的资源没人清理。正确流程是：

1. 记录 refresh request；
2. 等 callback 返回；
3. 收集它产生的 cleanup；
4. 重新计算 epoch，发现 A 已过期；
5. 立即进入 UNLOADING 并执行 cleanup；
6. 最终停在 PENDING。

运行：

```bash
uv run pytest Tutorial/11-async-races/src/test_chapter11.py -k loss_while_loading
```

## Step 3：UNLOADING 时依赖恢复

旧 cleanup 可能需要异步完成。在它等待期间，新 Provider 已经出现：

```text
ACTIVE(A) → UNLOADING(A)
                │ await cleanup
              epoch B 出现
                ↓
cleanup A 完成 → LOADING(B) → ACTIVE(B)
```

新 activation 不能越过旧 cleanup。否则两个 epoch 会同时拥有 listener、task 或 Service。

Runner 在 cleanup 完成后读取 refresh flag，再用最新 epoch 激活一次。

运行：

```bash
uv run pytest Tutorial/11-async-races/src/test_chapter11.py -k restoration
```

## Step 4：为什么不直接 cancel Plugin callback

Python cancellation 只能在 await 点注入 `CancelledError`，用户代码还可能捕获或延迟它。更重要的是，Cordis 的依赖变化语义是安全卸载，不是任意取消用户 callback。

因此正常 dependency change 等待当前 setup 收敛，再清理返回结果。最终 Runtime shutdown 是否取消特定 background task，则由该 task 自己的 Effect cleanup 定义。

### Checkpoint B

任何时刻最多有一个 activation epoch 生效。新 epoch 可以等待，但不能和旧 epoch 的 cleanup 重叠。
