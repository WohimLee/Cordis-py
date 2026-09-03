# PluginRuntime 与多个 Fiber

同一个 Plugin 可以挂载多次：

```python
first = root.plugin(plugin, "A")
second = root.plugin(plugin, "B")
```

这里有两次挂载，所以有两个 Fiber；但它们来自同一个 Plugin。

Cordis 使用 **PluginRuntime** 保存共享记录：

```python
@dataclass(eq=False)
class PluginRuntime:
    callback: Callback
    name: str
    fibers: set[Fiber]
```

三者职责不同：

| 对象 | 表示什么 |
| --- | --- |
| Plugin | 用户传入的函数、class 或 object |
| PluginRuntime | 同一 Plugin identity 的共享注册记录 |
| Fiber | Plugin 的某一次具体挂载和 Lifecycle |

## Step 3：获取或创建 PluginRuntime

`Registry.plugin()` 先规范化 Plugin，再查找共享 Runtime：

```python
callback = self.resolve(plugin)
runtime = self._runtimes.get(callback)
if runtime is None:
    runtime = PluginRuntime(callback, plugin_name(plugin), set())
    self._runtimes[callback] = runtime
```

然后为本次挂载创建新 Fiber：

```python
fiber = Fiber(context, runtime, config, parent)
runtime.fibers.add(fiber)
```

运行：

```bash
uv run pytest Tutorial/04-plugin-registry/src/test_chapter04.py -k shared_runtime
```

测试会看到一个 PluginRuntime 和两个 Fiber。两个 Fiber 的 config 和 state 各自独立。

## Step 4：把挂载入口交给 Registry

第 03 章由 `Context.plugin()` 直接创建 Fiber。现在它只转发请求：

```python
def plugin(self, plugin: Plugin, config=None) -> Fiber:
    return self.registry.plugin(self, plugin, config)
```

这样 Plugin identity 和 Fiber 创建只由 Registry 处理。Context 仍然是用户入口，但不重复 Registry 的职责。

### Checkpoint B

```text
原始 Plugin
    ↓ Registry.resolve()
统一 callback
    ↓ 查找或创建
PluginRuntime
    ├── Fiber(config=A)
    └── Fiber(config=B)
```

下一节加入 Registry 的查询、遍历和删除操作。

## 为什么需要多个 Fiber

多次挂载不是为了复制 Plugin 代码，而是为了用同一份实现承载不同配置、作用域或产品入口。设想一个通用委派 Plugin：每个实例把一个模型可见工具绑定到一个固定 Provider。

```python
delegation_routes = {}


def delegation_tool(ctx, config):
    tool_name = config["tool_name"]
    provider_name = config["provider"]

    def setup():
        delegation_routes[tool_name] = provider_name
        return lambda: delegation_routes.pop(tool_name, None)

    ctx.effect(setup, f"delegation route {tool_name}")
```

应用需要同时提供“新建子任务”和“继承当前历史的分叉任务”时，可以挂载两次：

```python
spawn = root.plugin(
    delegation_tool,
    {"tool_name": "subagent", "provider": "spawn"},
)
fork = root.plugin(
    delegation_tool,
    {"tool_name": "subagent_fork", "provider": "fork"},
)
```

Registry 复用一个 PluginRuntime，但为两次调用分别创建 Fiber：

```text
delegation_tool PluginRuntime
├── spawn Fiber
│   ├── config.tool_name = subagent
│   ├── config.provider = spawn
│   └── Effect: register("subagent")
└── fork Fiber
    ├── config.tool_name = subagent_fork
    ├── config.provider = fork
    └── Effect: register("subagent_fork")
```

两个 Fiber 共享 Plugin identity 和 callback，不共享单次挂载状态。它们各自拥有配置、主要 Plugin Context、dependency snapshot、activation epoch 和 Effect。卸载 `spawn` Fiber 只移除 `subagent`，不会移除 `subagent_fork`。

同一 Plugin 也可以在不同 Context 下挂载。此时每个 Fiber 的 Parent Context、isolation label 和 intercept 配置可以不同：

```python
internal = root.isolate("providers")
external = root.isolate("providers")

internal_fiber = internal.plugin(delegation_tool, internal_config)
external_fiber = external.plugin(delegation_tool, external_config)
```

这类多实例通常服务于三种需求：

- 同一实现暴露多个名称或路由，例如 `subagent` 与 `subagent_fork`；
- 同一 Provider 实现连接多个后端，例如 primary 与 secondary；
- 同一 Plugin 在多个隔离作用域或父插件下运行，随各自 owner 独立卸载。

必须区分新挂载和原 Fiber 的新 activation：

```text
再次 ctx.plugin(same_plugin)       ──▶ 新 Fiber
Fiber.restart()                    ──▶ 原 Fiber，新 activation
Fiber.update(config)               ──▶ 原 Fiber，配置更新并重新激活
Inject 丢失后恢复                  ──▶ 原 Fiber，新 dependency epoch
配置条目 disabled                  ──▶ 不创建活动 Fiber
```

多个活动 Fiber 能否共存还取决于它们注册的名称和 isolation scope。两个实例若在同一作用域提供同名 Service 或注册同名 Tool，会按对应 Registry 的重复规则失败；多实例配置必须给资源使用不同名称，或者把实例放入不同 isolation scope。
