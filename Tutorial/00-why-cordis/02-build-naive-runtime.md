# 构建第一个 Runtime

上一节由我们亲自调用 Provider 和 Consumer。现在写一个 Runtime 来完成这件事。

## Step 2：实现 `NaiveRuntime`

先准备两个容器：

```python
class NaiveRuntime:
    def __init__(self) -> None:
        self.services: dict[str, object] = {}
        self.cleanups: list[Callable[[], object]] = []
```

- `services` 保存所有 Service；
- `cleanups` 保存所有 Cleanup 函数。

接着实现 `mount()`。Mount 表示“挂载”，也就是把一个 Plugin 安装到 Runtime：

```python
def mount(self, plugin: Plugin) -> None:
    result = plugin(self.services)
    if callable(result):
        self.cleanups.append(result)
```

这段代码做了两件事：

1. 立即执行 Plugin；
2. 如果 Plugin 返回函数，就把它当成 Cleanup 保存起来。

运行测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k provider_before_consumer
```

### Checkpoint B

此时的结构如下：

```text
NaiveRuntime
├── services   所有 Plugin 共用的 Service 字典
├── cleanups   所有 Plugin 共用的 Cleanup 列表
└── mount()    立即执行传入的 Plugin
```

这个 Runtime 很短，也能工作。但 `mount()` 有一个重要特点：它不会等待，Plugin 一挂载就立即执行。

## Step 3：先挂载 Consumer

如果配置文件把 Consumer 写在 Provider 前面，会发生什么？

```python
runtime.mount(consumer)
runtime.mount(provider)
```

运行测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k consumer_before_provider
```

第一个 `mount()` 会抛出 `KeyError`，因为 Consumer 需要的 `message` Service 还不存在。

测试本身仍会通过，因为测试正在确认这个缺陷确实存在。随后即使挂载 Provider，刚才失败的 Consumer 也不会自动再试一次：

```text
挂载 Consumer
  └── 找不到 message → KeyError → 本次执行结束

挂载 Provider
  └── message 出现了
      └── Runtime 不知道应该重新运行哪个 Consumer
```

第一个问题出现了：

> Plugin 的书写顺序决定了系统能不能启动。

在 Cordis 中，这个问题由 **Inject** 和 **Fiber 的 PENDING 状态**解决。我们现在只记住术语，暂时不实现它们。

## Step 4：让 Provider 返回 Cleanup

Provider 创建 Service，也应该负责删除它：

```python
def provider(scope):
    scope["message"] = "hello"
    return lambda: scope.pop("message", None)
```

实现 `close()`：

```python
def close(self) -> None:
    while self.cleanups:
        self.cleanups.pop()()
```

`pop()` 从列表末尾取出 Cleanup，因此清理顺序与创建顺序相反。后创建的资源先清理，这是生命周期系统中常见的做法。

运行测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k returned_cleanup
```

关闭 Runtime 后，`message` 被删除。我们解决了“整个程序关闭时怎样清理”的简单情况，但还没有解决单个 Plugin 的生命周期。
