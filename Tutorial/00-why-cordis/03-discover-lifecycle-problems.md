# 找出 Lifecycle 的问题

现在的 `NaiveRuntime` 可以保存 Cleanup。但“保存了 Cleanup”和“正确管理 Lifecycle”并不是一回事。

## Step 5：这些资源属于谁

假设 Provider 和 Consumer 都创建了资源：

```text
cleanups
├── Provider 创建的 Cleanup
└── Consumer 创建的 Cleanup
```

Runtime 只有一个全局列表。它没有记录 Cleanup 属于哪个 Plugin。

如果现在只想卸载 Provider，我们会遇到一连串问题：

- 哪个 Cleanup 属于 Provider？
- Provider 注册过哪些事件监听器？
- Provider 启动过哪些后台 Task？
- Provider 创建了子 Plugin 时，应该先清理谁？
- 某个 Cleanup 报错后，其他 Cleanup 还要不要继续？

运行测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k cannot_unmount
```

测试确认 `NaiveRuntime` 根本没有卸载单个 Plugin 的 API。

第二个问题出现了：

> Runtime 知道有哪些资源，却不知道资源属于谁。

Cordis 使用 **Fiber** 表示一次 Plugin 挂载，并让这次挂载产生的所有 **Effect** 归这个 Fiber 所有。Fiber 和 Effect 的正式名称需要保留，因为它们正是 Cordis 的核心概念。

## Step 6：替换 Service

现在把 `message` 从 `v1` 改成 `v2`：

```python
runtime.services["message"] = "v2"
```

运行测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k service_replacement
```

Consumer 之前已经读取了 `v1`。覆盖字典中的值不会通知它，因此 trace 仍然只有：

```python
["activate:v1"]
```

如果 Consumer 保存了旧 Service，或者用旧 Service 启动了后台任务，它们都会继续存在。

我们真正想要的是：

```python
["activate:v1", "cleanup:v1", "activate:v2"]
```

这个过程分三步：

1. 发现 Consumer 依赖的 Service 已改变；
2. 完整清理 Consumer 上一次运行产生的资源；
3. 使用新的 Service 再运行一次 Consumer。

第三个问题出现了：

> Service 不能只是字典里的值，它还要参与 Plugin 的 Lifecycle。

Cordis 使用 **Reflect** 保存 Service implementation。Implementation 不只包含值，还记录提供它的 Fiber 和作用域信息。当 implementation 改变时，依赖它的 Fiber 会开始新的 **Epoch**。

Epoch 可以先简单理解为“某一组依赖保持有效期间，Plugin 的一次运行”。

### Checkpoint C

`NaiveRuntime` 现在可以：

- 挂载并立即执行 Plugin；
- 用字典共享 Service；
- 保存同步 Cleanup；
- 关闭 Runtime 时逆序清理。

它不能：

- 无序挂载 Provider 和 Consumer；
- 等待暂时缺失的依赖；
- 单独卸载一个 Plugin；
- 记录资源属于哪个 Plugin；
- 响应 Service 的删除或替换；
- 管理异步 setup、Cleanup 和并发变化。

这些限制不是多加几个 `if` 就能解决的。我们需要把作用域、Plugin identity、生命周期状态、资源所有权和 Service 解析分开建模。
