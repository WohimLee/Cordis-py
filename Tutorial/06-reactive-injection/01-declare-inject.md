# 06 — 用 Inject 声明依赖

第 04 章的 Registry 知道有哪些 Plugin，第 05 章的 Reflect 知道有哪些 Service Impl。但它们还没有连接起来。

假设 Consumer 需要 `database`：

```python
def consumer(ctx, config):
    database = ctx.get("database")
```

只看函数内容，Runtime 不应该猜测它依赖什么。Cordis 要求 Plugin 明确声明 **Inject**。

## 本章目标

这一章只完成依赖的第一次激活：

```text
缺少依赖 → Fiber 保持 PENDING
依赖到达 → Fiber 自动 LOADING → ACTIVE
```

Service 丢失后的卸载和恢复需要 Dependency Epoch，将在第 07 章实现。

## Step 0：函数 Plugin 的 `.inject`

函数 Plugin 使用静态 metadata：

```python
def consumer(ctx, config): ...


consumer.inject = ["database"]
```

这里的 `.inject` 不是执行依赖注入的函数。它只是一份声明，告诉 Registry：创建 Fiber 时要记录 `database` 依赖。

## Step 1：两种 Inject 数据形式

Cordis 接受列表和 mapping：

```python
inject = ["database", "cache"]
```

或者：

```python
inject = {
    "database": {"timeout": 3},
    "cache": None,
}
```

列表只声明名称。Mapping 的 value 会在后续 Intercept 章节作为 Service 配置使用。

Registry 先统一成：

```python
{
    "database": None,
    "cache": None,
}
```

这个过程称为 **normalize**，也就是把几种外部写法转换成一种内部结构。

## Step 2：class Plugin 的 `@Inject`

Class 使用正式 `Inject` decorator：

```python
@Inject("database")
class Consumer: ...
```

Decorator 只向 class 写入 metadata，不负责执行 Plugin。子类会继承 parent class 的 Inject，再添加自己的依赖。

运行：

```bash
uv run pytest Tutorial/06-reactive-injection/src/test_chapter06.py -k inject_metadata
```

### Checkpoint A

```text
Plugin
└── inject metadata
    ├── database
    └── cache

Registry.resolve()
└── PluginRuntime.inject = 统一后的 mapping
```

Runtime 已经知道“Consumer 需要什么”，下一步判断这些 Service 是否存在。
