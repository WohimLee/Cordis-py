# 02. 核心对象模型

## Context

Context 是插件看到的唯一运行时入口：

```python
class Context:
    root: Context
    fiber: Fiber
    reflect: ReflectService
    registry: RegistryService
    events: EventsService
    logger: LoggerService

    def extend(self, **metadata) -> Context: ...
    def isolate(self, name: str, label: object | None = None) -> Context: ...
    def intercept(self, name: str, config: object) -> Context: ...
    def plugin(self, plugin: Plugin, config: object = None) -> Fiber: ...
    def effect(self, setup: EffectSetup, label: str = "anonymous") -> Disposable: ...
```

Context 不复制服务。服务由 Root Context 保存，子 Context 通过服务名和隔离标签解析实现。

在 TypeScript Cordis 中，Context 是 Proxy。读取 `ctx.llm` 会依次判断原生属性、查询服务定义、选择当前隔离域、验证依赖权限，并返回本次 Fiber 激活时绑定的实现。Python 使用 `__getattr__` 和显式 `get()` 表达同一语义，不能把动态服务降级为普通字段。

- `extend()` 只增加元数据；
- `isolate()` 改变指定服务的解析标签；
- `intercept()` 为某服务累计插件级配置；
- 所有派生操作都不得修改父 Context。

## Service

Service 是占用稳定 Context 名称的能力对象：

```python
class Database(Service):
    provide = "database"

    def __init__(self, ctx, config):
        super().__init__(ctx)
```

构造时调用 `ctx.provide(name, self)`。注册属于当前 Fiber，Fiber 卸载时自动撤销。一个隔离作用域内同名服务最多有一个活动实现。

Service 可声明默认服务名、额外可用性检查、配置验证器和专用配置合并器。

## Plugin

支持三种插件形态：

```python
def plugin(ctx, config): ...

class PluginClass:
    def __init__(self, ctx, config): ...

class PluginObject:
    def apply(self, ctx, config): ...
```

Registry 将其统一为：

```python
@dataclass(frozen=True)
class PluginSpec:
    callback: Callable
    name: str
    inject: Mapping[str, object | None]
    provide: tuple[str, ...]
    validator: ConfigValidator | None
    intercept: frozenset[str]
```

插件通过函数属性、类属性或装饰器声明元数据。Registry 只在边界处规范化一次，Fiber 不重复判断插件形态。

必须始终区分：Plugin 是定义，Fiber 是该定义某次运行的实例，Context 是该实例看到的运行环境。

## PluginRuntime

同一 callback 对应一个 Runtime，但可以挂载多次：

```python
@dataclass
class PluginRuntime:
    spec: PluginSpec
    fibers: set[Fiber]
```

`registry.delete(plugin)` 卸载该 Runtime 的全部 Fiber。Runtime 不保存单次挂载配置。

## Fiber

Fiber 代表一次 `ctx.plugin()` 调用，持有：

- 唯一 uid；
- 父 Context 和插件 Context；
- PluginRuntime；
- 原始配置和验证后配置；
- Inject 声明；
- 当前依赖实现快照；
- 当前 epoch；
- Effect 树和清理任务；
- 启动错误和生命周期状态。

同一插件多次挂载产生多个 Fiber，它们拥有独立配置、作用域和 Effect。

## 所有权关系

- Root Fiber 拥有顶层 Plugin Fiber；
- Plugin Fiber 通过 Effect 拥有子插件；
- Fiber 拥有激活期间创建的 Service、Hook 和用户资源；
- Runtime 仅建立索引，不替代父 Fiber 的所有权；
- Context 是能力视图，不独立拥有资源。

示例所有权树：

```text
Parent Fiber
├── Effect: provide("foo")
├── Effect: on("message")
└── Effect: Child Fiber
    ├── Effect: provide("bar")
    └── Effect: timer
```

销毁 Parent 会递归撤销整棵子树，插件不需要在全局维护资源 id。
