# 04 — Plugin 不只是一种函数

第 03 章把 Plugin 写成接收 Context 的函数。实际项目还会遇到 class 和带 `apply()` 方法的对象。

Cordis 允许三种主要 Plugin 形态：

```python
def function_plugin(ctx, config): ...


class ClassPlugin:
    def __init__(self, ctx, config): ...


class ObjectPlugin:
    def apply(self, ctx, config): ...
```

如果 Fiber 分别处理三种形态，它的 Lifecycle 代码会出现三套分支。Registry 的第一个任务就是把它们转换成统一的 **callback**。

## 本章目标

本章解决三个问题：

- 不同 Plugin 形态如何用同一条 Fiber 激活路径运行；
- 同一个 Plugin 多次挂载时，哪些数据应该共享；
- 怎样按 Plugin identity 查询和删除 Fiber。

Inject、Service 和依赖激活尚未加入。

## Step 0：先写三种 Plugin

测试分别挂载 function、class 和 object Plugin：

```bash
uv run pytest Tutorial/04-plugin-registry/src/test_chapter04.py -k plugin_shapes
```

三者都应收到 Context 和 config，并产生相同形式的激活记录。

## Step 1：规范化为 callback

Registry 的 `resolve()` 为每个 Plugin 生成统一 callback：

```python
Callback = Callable[[Context, object], object]
```

规范化规则是：

```text
function Plugin ──→ 调用 function(ctx, config)
class Plugin    ──→ 构造 ClassPlugin(ctx, config)
object Plugin   ──→ 调用 object.apply(ctx, config)
```

Fiber 从此只接收 callback，不需要知道原始 Plugin 属于哪种形态。

如果对象既不是 callable，也没有 callable `apply`，Registry 立即抛出 `TypeError`。错误越靠近挂载入口，越容易定位。

## Step 2：保持 Plugin identity

`resolve()` 不能每次都创建一个全新的 callback。否则同一个 Plugin 挂载两次时，Registry 会误以为它们是两个不同 Plugin。

因此 Registry 按对象 identity 缓存规范化结果：

```python
first = registry.resolve(plugin)
second = registry.resolve(plugin)
assert first is second
```

Identity 表示“是不是同一个对象”，不是“代码看起来是否相同”。两个内容一样的 lambda 仍是两个 Plugin。

### Checkpoint A

Registry 现在把多种外部形态收敛成一种内部 callback，同时保留原始 Plugin identity。下一节保存同一 Plugin 的共享运行记录。
