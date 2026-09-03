# 00 — 为什么需要 Cordis

这一章先不实现 Cordis。

我们从最简单的 Plugin 系统开始，然后亲手把它弄出问题。这样等到 Context、Fiber 和 Effect 出现时，你会知道它们分别解决了什么，而不是只记住几个类名。

## 先认识几个术语

这些名称会一直用到教程结束，因此保留 Cordis 中的正式叫法：

- **Plugin**：可以安装到 Runtime 里的程序模块。在 Python 中，它一开始只是一个函数。
- **Runtime**：负责安装和运行 Plugin 的程序。
- **Service**：Plugin 之间共享的能力或对象，例如数据库连接、Logger 或 LLM。
- **Provider**：提供 Service 的 Plugin。
- **Consumer**：使用 Service 的 Plugin。
- **Cleanup / Disposer**：资源不用时执行的清理函数。
- **Lifecycle**：一个 Plugin 从安装、运行到卸载的完整过程，也就是生命周期。

例如，一个 Provider 提供数据库连接，另一个 Consumer 使用它查询数据。

## 本章要发现什么

我们会做出一个很小的 `NaiveRuntime`。Naive 表示“朴素的”：它符合第一直觉，但没有认真处理复杂情况。

本章最终会发现三个问题：

1. Consumer 必须排在 Provider 后面；
2. Runtime 不知道每个资源属于哪个 Plugin；
3. Service 改变后，Consumer 不会自动停止和重新运行。

本章只使用函数、字典和列表。Context、Registry、Fiber、Reflect 和 Effect 会在后面的章节中逐个出现。

## Step 0：从一个函数类型开始

本章的代码都放在 `src/` 中：

```text
00-why-cordis/
├── 01-start-from-functions.md
├── 02-build-naive-runtime.md
├── 03-discover-lifecycle-problems.md
├── 04-connect-to-cordis.md
└── src/
    ├── chapter00.py
    └── test_chapter00.py
```

先定义 Plugin：

```python
from collections.abc import Callable

Plugin = Callable[[dict[str, object]], object]
```

这行类型定义表示：

```text
Plugin 接收一个字典，执行后返回一个对象。
```

这个字典暂时用来保存所有 Service。返回值以后可以是 Cleanup。

## Step 1：直接运行两个 Plugin

Provider 写入 Service，Consumer 读取 Service：

```python
services: dict[str, object] = {}


def provider(scope):
    scope["message"] = "hello"


def consumer(scope):
    assert scope["message"] == "hello"


provider(services)
consumer(services)
```

运行对应测试：

```bash
uv run pytest Tutorial/00-why-cordis/src/test_chapter00.py -k direct_calls
```

测试通过了。现在的执行过程是：

```text
Provider 把 "hello" 放进字典
                    ↓
Consumer 从字典中读出 "hello"
```

但这还不能说明我们的 Plugin 系统设计正确。它只说明：当我们提前知道正确顺序时，直接调用两个函数可以工作。

### Checkpoint A

目前只有：

- 两个函数形式的 Plugin；
- 一个共享 Service 字典；
- 人工安排的执行顺序。

还没有真正的 Runtime。下一节会把 Plugin 的运行工作交给 `NaiveRuntime`。
