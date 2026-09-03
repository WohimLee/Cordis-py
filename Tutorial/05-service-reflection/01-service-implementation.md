# 05 — Service 不只是一个值

第 00 章把 Service 放进普通字典：

```python
services["message"] = "hello"
```

这种写法只能保存名称和值。Cordis 还需要知道：

- Service 由哪个 Fiber 提供；
- 它属于哪个 isolation scope；
- Provider 是否已经 ACTIVE；
- Service 当前是否可以使用；
- Provider 卸载时应该删除哪一条记录。

Cordis 把一条具体的 Service 实现记录称为 **Impl**，也就是 implementation。

## 本章目标

本章单独构建 Reflect 的核心能力：

- 使用 Impl 保存 Service；
- `provide()` 返回可逆 disposer；
- `get()` 根据 Context 解析 Impl；
- strict 与 loose lookup；
- 同名 Provider 的覆盖和恢复；
- isolation label；
- Service 变化通知；
- Fiber dispose 自动删除它提供的 Service。

为了避免重复上一章完整的 Registry，本章只带一个最小 Fiber owner。第 06 章会把 Reflect 与 Plugin/Inject Lifecycle 连接起来。

## 正式术语

- **Reflect**：记录和解析 Context 属性、Service implementation 的 Runtime 组件。
- **Impl**：一条 Service implementation 记录，不只是 Service value。
- **provide**：向当前 scope 注册一个 Service Impl。
- **strict lookup**：只有 Provider ACTIVE 且 Service available 时才返回值。
- **loose lookup**：调试或内部流程可以看到尚在 LOADING 的 Impl。
- **isolation label**：区分同名 Service 所属作用域的 identity。

## Step 0：定义 Impl

```python
@dataclass
class Impl:
    name: str
    fiber: Fiber
    value: object
    label: object
    check: AvailabilityCheck
```

同一个 `name` 可以有多条 Impl。Reflect 解析 Service 时，必须同时考虑 name 和 label。

## Step 1：注册和读取 Service

`provide()` 创建 Impl，并按名称保存：

```python
impl = Impl(name, context.fiber, value, label, check)
self._impls.setdefault(name, []).append(impl)
```

`get()` 找到与调用方 Context label 相同的最新 Impl：

```python
for impl in reversed(self._impls.get(name, [])):
    if impl.label is expected_label:
        return impl.value
```

运行：

```bash
uv run pytest Tutorial/05-service-reflection/src/test_chapter05.py -k provide_and_get
```

### Checkpoint A

```text
Context.provide("message", "hello")
    ↓
Reflect 保存 Impl(name, fiber, value, label, check)
    ↓
Context.get("message")
    ↓
Reflect 按 name + label 返回 value
```

下一节处理 Impl 的可见状态和 isolation。
