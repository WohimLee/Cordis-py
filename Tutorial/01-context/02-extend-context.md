# 使用 `extend()` 派生 Context

一个 Runtime 中会有很多 Plugin。如果所有 Plugin 都直接使用 root Context，它们就无法带有不同的作用域信息。

Cordis 使用 `extend(meta)` 从现有 Context 创建 child Context。

## Step 3：创建 child Context

child Context 不能调用普通的 `Context()`，因为那会创建一个全新的 `_Runtime`。我们增加一个内部构造方法：

```python
@classmethod
def _derive(
    cls,
    parent: Context,
    meta: Mapping[str, object],
) -> Context:
    child = cls.__new__(cls)
    child._runtime = parent._runtime
    child._root = parent.root
    child._meta = parent._meta | dict(meta)
    return child
```

这几行代码分别保证：

1. child 与 parent 共用 `_runtime`；
2. child 的 `root` 仍指向同一个 root Context；
3. child 先继承 parent metadata，再应用自己的 metadata。

公开的 `extend()` 很简单：

```python
def extend(self, meta=None) -> Context:
    return Context._derive(self, {} if meta is None else meta)
```

运行：

```bash
uv run pytest Tutorial/01-context/src/test_chapter01.py -k extend
```

## Step 4：验证继承和覆盖

创建三层 Context：

```python
root = Context()
app = root.extend({"baseUrl": "file:///app/", "mode": "dev"})
plugin = app.extend({"mode": "test", "name": "demo"})
```

结果是：

```text
root
└── app
    ├── baseUrl = file:///app/
    ├── mode = dev
    └── plugin
        ├── baseUrl = file:///app/  （继承）
        ├── mode = test            （覆盖）
        └── name = demo            （新增）
```

`plugin.mode` 是 `test`，但 `app.mode` 仍然是 `dev`。child 的变化不会倒过来修改 parent。

### Checkpoint B

我们现在拥有一棵 Context 树：

```text
root Context
├── child A
│   └── grandchild
└── child B
```

它们有不同 metadata，但共享同一个 `_Runtime`。这就是“作用域不同，Runtime 相同”。

本章使用字典合并保存 metadata 快照。正式 Cordis 使用 JavaScript prototype 表达继承，正式 Python 实现则维护显式的父级信息和 Context-bound service view。这里只保留当前章节需要观察的行为。
