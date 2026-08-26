# 10. 公共 API

## 使用草案

```python
from cordis import Context, Service, Fiber, FiberState, inject

ctx = Context()
fiber = ctx.plugin(my_plugin, config)
await fiber.wait()

dispose_listener = ctx.on("app/ready", listener)
dispose_service = ctx.provide("cache", cache)

ctx.emit("event", value)
result = ctx.bail("decision", request)
result = await ctx.serial("decision", request)
await ctx.parallel("notification", payload)
result = await ctx.waterfall("pipeline", request, next_=default_handler)

await fiber.update(new_config)
await fiber.restart()
await fiber.dispose()
await ctx.aclose()
```

## 服务示例

```python
class Counter(Service):
    provide = "counter"

    def __init__(self, ctx):
        self.value = 0
        super().__init__(ctx)

    def next(self):
        self.value += 1
        return self.value
```

## 插件依赖示例

```python
@inject("counter")
def greeter(ctx, config):
    ctx.on("ready", lambda: print(ctx.counter.next()))
```

插件返回 disposer 或在 Context 上注册 Effect。用户无需手工把 listener/service 加入清理列表。

共享 Service 的注册方法通过 `self.caller_context` 创建调用方拥有的 Effect，确保 provider Fiber 卸载时自动撤销注册。

## API 分层

稳定公共层：

- `Context`、`Service`、`Fiber`、`FiberState`；
- `inject`、`plugin` 装饰器；
- `CordisError`、`ValidationError`；
- Effect、Disposable、Plugin 和 ConfigValidator Protocol。

高级扩展层：ReflectService、RegistryService、EventsService 和 LoggerService。内部 epoch、runner、store 索引以下划线命名，不承诺兼容。

## 类型策略

- 发布 `py.typed`；
- Service 和配置使用泛型；
- Plugin 定义为 Protocol，不限制函数、类和对象入口；
- Context 的动态服务无法完全由静态类型推导，建议应用定义带注解的 Context Protocol；
- 装饰器保留被包装对象类型；
- 公共 API 不暴露 `Any`，除非动态插件边界无法安全收窄。

## 兼容边界

Python API 保证概念和行为兼容，不保证 JavaScript 语法兼容：

- 不复制 Proxy 和 Symbol；
- 不实现 TypeScript declaration merging；
- Fiber 默认使用显式 await；
- callable Service 由普通 `__call__` 表达；
- Context 的动态属性同时提供显式 `get()` 入口；
- loader 的模块标识采用 Python `module:attribute`。
