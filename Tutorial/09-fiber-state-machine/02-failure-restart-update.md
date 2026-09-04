# 失败、Restart 与 Update

## Step 3：启动失败进入 FAILED

Plugin callback 或 config validator 抛出异常时，Fiber 必须：

1. 回滚这次 LOADING 已创建的资源；
2. 保存异常到 `fiber.error`；
3. 记录失败对应的 Dependency Epoch；
4. 进入 `FAILED`；
5. 让 `wait()` 重新抛出异常。

FAILED 是稳定状态，而不是 Fiber 已死亡。它告诉 Runtime：“这个 epoch 已经试过，而且失败了。”

## Step 4：相同 epoch 不自动重试

如果失败后每次 Service notify 都重新执行 Plugin，一个永久错误就会形成无限重试。

因此 Fiber 记录 `failed_epoch`：

```text
当前 epoch == failed_epoch → 保持 FAILED
当前 epoch 改变            → 可以重新尝试
显式 restart               → 强制重新尝试
```

本章教学版只有 ready/not-ready 两种 epoch；正式实现记录所有 Inject 对应的 Impl identity。

运行：

```bash
uv run pytest Tutorial/09-fiber-state-machine/src/test_chapter09.py -k failed_epoch
```

## Step 5：`restart()` 使用当前 raw config

`restart()` 表示“即使依赖和配置没有变化，也重新开始一个 activation”：

```text
ACTIVE → UNLOADING → LOADING → ACTIVE
FAILED ────────────→ LOADING → ACTIVE / FAILED
```

它会先清理旧资源，再调用同一个 Plugin。它不会创建新 Fiber，也不会改变 Registry identity。

如果依赖仍然缺失，restart 只能回到 `PENDING`，因为 Fiber 不能绕过 Inject 条件。

## Step 6：`update(config)` 先验证再替换 ACTIVE epoch

ACTIVE Fiber 收到新 config 时：

```text
validate
   ├── 失败：抛出错误，当前 ACTIVE epoch 不动
   └── 成功：经过 internal/update → restart
```

这里先验证很关键。错误配置不能让一个原本工作的 Plugin 先停掉。

本章先实现最小 update 行为；正式 Cordis 的 `internal/update` waterfall 可以保存配置、修改配置，或返回结果阻止默认 restart。Events 会在第 12 章完整实现。

### Checkpoint B

- `restart()` 表示重新执行当前配置；
- `update()` 表示验证并应用新配置；
- 两者最后都回到同一条 refresh/activate 路径，而不是复制 Plugin 启动代码。
