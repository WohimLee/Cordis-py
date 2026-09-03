# 11. DeepSeek Harness 映射与源码依据

## DSH 中的能力图

DeepSeek Harness 将能力拆为 Cordis 插件和服务：

```text
LLM provider
      │ provides ctx.llm
      ▼
Agent loop ─── requires ctx.tools
      │
      ├── requires ctx.sessions
      ├── emits agent/* events
      └── calls ctx.llm.stream()

Tool plugins ───── register into ctx.tools
Persistence ────── observes session events
Web UI ─────────── drives ctx.agents
```

替换 LLM provider 时，旧服务撤销使依赖者卸载；新服务注册后依赖者重新激活。Agent loop 不需要知道 provider 是 DeepSeek、OpenAI 还是本地模型。

## Python 复现层级

```text
Cordis-py Core
  Context / Registry / Reflect / Fiber / Effect / Events
                │
                ▼
Configuration Runtime
  Loader / Include / Group / HMR
                │
                ▼
Harness Capability Plugins
  llm / tools / sessions / agent-loop / shell / fs / web ...
                │
                ▼
Application Profiles
  headless / CLI / API / ACP / Web
```

第一阶段只复现 Core。Loader 完成不等于 Harness 已复现；Harness 还需要逐项实现其服务定义、provider 和 consumer。

## 源码阅读顺序

原始实现位于 DeepSeek Harness 的 `vendor/cordis/src`。建议顺序：

1. `context.ts`：根 Context、Proxy、extend、isolate 和 intercept；
2. `registry.ts`：插件形态、Inject 和 `ctx.plugin()`；
3. `fiber.ts`：`_refresh()`、epoch、reload、unload 和 effect；
4. `reflect.ts`：服务解析、provide 和 notify；
5. `events.ts`：五种分发模式和 listener ownership；
6. `service.ts`：Service 对 provide、check 和 intercept 的封装；
7. `logger.ts`：Logger 层级、消息和 Exporter；
8. Loader 源码：配置 Entry 如何变成插件树。

## 对照原则

Python 实现应按行为场景对照，而不是逐行翻译：

- Context 动态访问是否解析到同一作用域实现；
- 同一加载顺序是否产生相同 Fiber 状态序列；
- provider 替换是否导致相同 unload/reload；
- Effect 是否在相同所有权边界被清理；
- dispatch 是否产生相同监听顺序和结果；
- update、failure 和 disposal 是否达到相同最终状态。

JavaScript Proxy、Symbol、prototype 和 thenable 等机制不要求按实现方式复制；它们承载的公开 API 和可观察能力仍属于 Core 对等目标，无法直接表达的部分必须登记 Python 等价形式并通过行为对照。

## 架构事实来源

| 架构主题 | 原始源码 |
| --- | --- |
| Context 派生与隔离 | `context.ts` |
| PluginSpec 与 Runtime | `registry.ts` |
| Fiber 状态、epoch、Effect | `fiber.ts` |
| Service implementation 与 notify | `reflect.ts` |
| 分发模式与 Hook | `events.ts` |
| Service 便利封装 | `service.ts` |
| 日志模型 | `logger.ts` |

实现期间如果文档与当前 vendored 源码冲突，以 vendored 源码的可观察行为为准，并同步修正文档及跨语言测试。
