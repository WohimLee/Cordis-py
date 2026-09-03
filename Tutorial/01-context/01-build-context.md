# 01 — 构建最小 Context

第 00 章把同一个 Service 字典传给所有 Plugin。这样虽然简单，却无法说明 Plugin 在什么运行环境中执行。

Cordis 使用 **Context** 表示 Plugin 的运行作用域。所有 Context 属于同一个 Runtime，但可以携带不同的 metadata。它类似校园通行证：通行证属于同一所学校，却可以标明不同班级和权限。

## 本章目标

本章逐步实现 root Context、Context identity、metadata、`extend(meta)`，最后让 Plugin 接收调用它的 Context。Fiber、Effect owner、Inject 和 Service 自动解析仍留给后续章节。

## Step 0：分开作用域和共享状态

第 00 章只有一个 `NaiveRuntime`。现在把整套程序共享的数据放进内部 `_Runtime`：

```python
class _Runtime:
    def __init__(self) -> None:
        self.services = {}
        self.cleanups = []
```

Context 表示一个作用域：

```python
class Context:
    def __init__(self) -> None:
        self._runtime = _Runtime()
        self._root = self
        self._meta = {}
```

直接调用 `Context()` 创建的是 **root Context**，所以 `ctx.root is ctx`。

运行：

```bash
uv run pytest Tutorial/01-context/src/test_chapter01.py -k root_context
```

## Step 1：识别 Context

DSH Cordis 提供 `Context.is(value)`。`is` 是 Python 关键字，因此 Python 使用：

```python
@staticmethod
def is_context(value: object) -> bool:
    return isinstance(value, Context)
```

这是语言造成的名字差异，能力没有变化。

## Step 2：读取 metadata

Metadata 是 Context 携带的描述信息，例如 `baseUrl` 或自定义标签。我们希望 Plugin 可以写 `ctx.baseUrl`，因此用 `__getattr__` 在普通属性不存在时查询 `_meta`：

```python
def __getattr__(self, name: str) -> object:
    try:
        return self._meta[name]
    except KeyError:
        raise AttributeError(name) from None
```

### Checkpoint A

```text
root Context
├── _root ──────→ 自己
├── _runtime ───→ 共享 Runtime 状态
└── _meta ──────→ 当前作用域的 metadata
```

下一节用 `extend(meta)` 创建 child Context，并验证 metadata 如何继承。
