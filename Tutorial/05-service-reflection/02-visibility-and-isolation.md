# Service 可见性与 Isolation

## Step 2：strict 和 loose lookup

Provider 的 Fiber 在 LOADING 时，Service 可能已经调用 `provide()`，但 Plugin setup 还没有完成。

普通 Consumer 不应该过早拿到这个 Service：

```text
Provider LOADING
├── strict get → None
└── loose get  → value

Provider ACTIVE
├── strict get → value
└── loose get  → value
```

运行：

```bash
uv run pytest Tutorial/05-service-reflection/src/test_chapter05.py -k strict_lookup
```

Loose lookup 不是让业务代码绕过 Lifecycle，而是给 Runtime 内部检查和诊断使用。

## Step 3：Availability check

有些 Service 即使 Provider ACTIVE，也可能暂时不可用。例如连接池尚未连上远端。

`provide()` 可以接收 check：

```python
ctx.provide("database", database, check=lambda ctx: database.ready)
```

Strict lookup 同时要求：

```text
Provider Fiber ACTIVE
并且
check(Context) 返回 True
```

Loose lookup 仍可以看到 Impl，方便 Runtime 判断 implementation identity 是否存在。

## Step 4：同名 Provider 的覆盖和恢复

如果同一 scope 后来注册第二个同名 Service，最新 Impl 优先：

```text
Impl A: message = "A"
Impl B: message = "B"  ← 当前返回
```

Dispose B 后，不是把 `message` 永久删除，而是恢复 A：

```text
Impl A: message = "A"  ← 再次返回
```

运行：

```bash
uv run pytest Tutorial/05-service-reflection/src/test_chapter05.py -k shadowed_provider
```

普通字典无法自然表达这件事，因为 `services[name] = value` 会覆盖并丢失旧值。Reflect 保存的是 Impl 列表。

## Step 5：Isolation label

两个 Plugin 可能都需要名为 `database` 的 Service，但属于不同租户或测试环境。Cordis 使用 isolation label 区分它们。

```python
scope_a = root.isolate("database", label_a)
scope_b = root.isolate("database", label_b)
```

即使 Service name 相同：

```text
scope A → database Impl(label A)
scope B → database Impl(label B)
root    → database Impl(default label)
```

label 比字符串名称更像对象 identity：只有同一个 label 对象才属于同一 isolation scope。

运行：

```bash
uv run pytest Tutorial/05-service-reflection/src/test_chapter05.py -k isolation
```

### Checkpoint B

Reflect 的解析条件现在是：

```text
name 相同
    + isolation label 相同
    + strict 时 Provider ACTIVE
    + strict 时 availability check 通过
```

下一节让 Impl 与 Fiber Lifecycle 和变化通知连接起来。
