# 08 — 用 Isolation 划分同名 Service

前几章解析 Service 时只看名称。于是整个 Runtime 里只能有一个 `database`：

```text
ctx.get("database") → 名为 database 的 Service
```

可一个大型程序可能同时运行多个相互独立的应用，每个应用都想提供自己的 `database`。名称没有错，缺少的是“它属于哪个作用域”。Cordis 用 **isolation label** 解决这个问题。

## 本章目标

这一章补上 Service resolution 的两个维度，并继续处理 Inject mapping 中暂未使用的配置：

```text
Service implementation = name + isolation label
Service config         = base + intercepts + inject head
```

Isolation 决定“找到哪个 Service”，Intercept 决定“怎样得到它的配置”。两者名字容易同时出现，但职责不同。

## Step 0：把 label 加入查询条件

Reflect 保存的实现不再只有名称：

```python
@dataclass(eq=False, slots=True)
class Impl:
    name: str
    value: object
    label: object
```

查询时，name 和 label 都必须相同。两个 Context 即使都查询 `database`，只要 label 不同，就不会拿到对方的实现。

label 比较的是对象身份，而不是显示出来的文字。这使一个普通 `object()` 就可以成为不会意外重名的 scope token。

## Step 1：`Context.isolate()` 创建派生作用域

```python
private = root.isolate("database")
```

`isolate()` 不修改 root，而是返回一个 derived Context，并给指定 Service name 设置新 label：

```text
root    database label = DEFAULT_LABEL
private database label = fresh object
```

因此两边可以同时提供 `database`，各自读取自己的值。

运行：

```bash
uv run pytest Tutorial/08-isolation-intercept/src/test_chapter08.py -k fresh_label
```

## Step 2：派生 Context 继承 label

在 isolated Context 上继续调用 `extend()`，子 Context 必须留在同一个 scope：

```text
root
└── private = root.isolate("database")
    └── child = private.extend()

private 与 child 使用同一个 database label
```

如果 `extend()` 每次都创建 label，Plugin 创建的子 Context 反而无法看到父作用域的 Service。所以 `derive()` 复制 label mapping，但其中 token 的对象身份保持不变。

## Step 3：显式共享 label

`isolate(name, label)` 也允许传入已有 label：

```python
scope = object()
app_a = root.isolate("database", scope)
app_b = root.isolate("database", scope)
```

这两个 Context 不在同一条父子链上，却会加入同一个 `database` scope。共享由 label 身份决定，不由 Context 树的位置决定。

### Checkpoint A

现在 Service resolution 的最小键已经是：

```text
(service name, isolation label)
```

Dependency Epoch 记录的是解析到的 `Impl` identity，因此隔离作用域中的实现变化只会影响同 label 的 Consumer。
