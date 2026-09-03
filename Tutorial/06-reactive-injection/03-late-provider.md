# Consumer 可以先于 Provider 挂载

## Step 6：运行完整场景

先挂载 Consumer：

```python
consumer_fiber = root.plugin(consumer)
await consumer_fiber
assert consumer_fiber.state is FiberState.PENDING
```

再挂载 Provider：

```python
provider_fiber = root.plugin(provider)
await provider_fiber
await consumer_fiber
assert consumer_fiber.state is FiberState.ACTIVE
```

完整流程如下：

```text
1. Registry 创建 Consumer Fiber
2. Consumer 检查 database：缺失
3. Consumer 保持 PENDING，callback 不执行
4. Registry 创建 Provider Fiber
5. Provider LOADING，注册 database Impl
6. Provider ACTIVE，再次发布 database 变化
7. Consumer 重新检查 database：可用
8. Consumer LOADING，执行 callback
9. Consumer ACTIVE
```

运行：

```bash
uv run pytest Tutorial/06-reactive-injection/src/test_chapter06.py -k late_provider
```

这就是 Cordis 与普通“按顺序调用 Plugin”最明显的区别：配置中的先后顺序不再决定依赖的激活顺序。

## Step 7：等待多个 Inject

如果 Consumer 同时依赖 `database` 和 `cache`，第一个 Provider 到达后仍然保持 PENDING。只有两个 Service 都通过 strict lookup，callback 才执行一次。

运行：

```bash
uv run pytest Tutorial/06-reactive-injection/src/test_chapter06.py -k all_dependencies
```

## Step 8：`ctx.inject()` 临时 Consumer

有时不值得单独定义一个带 metadata 的 Plugin。Cordis 提供：

```python
fiber = ctx.inject(["database"], callback)
```

它只是创建一个带 `.inject` metadata 的内部 Plugin，再走正常的 `ctx.plugin()` 路径。它不能绕过 Registry 或创建第二套调度器。

运行：

```bash
uv run pytest Tutorial/06-reactive-injection/src/test_chapter06.py -k context_inject
```

### Checkpoint C

本章完成了第一个响应式依赖闭环：

```text
Plugin.inject
    ↓
PluginRuntime.inject
    ↓
Fiber PENDING
    ↓
Reflect Service notification
    ↓
Registry 找到 dependent Fiber
    ↓
Fiber 检查所有依赖
    ↓
LOADING → ACTIVE
```
