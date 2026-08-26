# 12. 测试与实施路线

## 单元测试矩阵

- Context 派生不修改父 Context；
- 隔离标签解析；
- 服务重复注册和所有权检查；
- Inject 列表、映射和继承合并；
- 五种事件模式、prepend、once、global 和过滤；
- Effect 同步、异步、generator、失败回滚和幂等；
- Fiber 全部状态转换；
- 配置验证和 intercept 合并；
- Logger 层级和 Exporter 清理。

## 生命周期竞态测试

- async setup 未完成时 owner dispose；
- LOADING 时依赖消失；
- UNLOADING 时依赖恢复；
- disposer 内注册或删除其他资源；
- provider 和 consumer 同时关闭；
- listener 在 dispatch 中删除自身或新增 listener；
- 子插件创建时父插件同步销毁；
- 多个 disposer 同时失败。

测试使用可控 Future/Event 驱动时序，不使用脆弱的 `sleep()`。

## 跨语言行为测试

从 vendored Cordis 提取语言无关场景，为 TypeScript 和 Python 使用相同期望：

- 插件激活顺序；
- 依赖消失与恢复；
- Effect 清理顺序；
- waterfall 嵌套结果；
- 隔离服务可见性；
- update/restart 行为；
- 失败后的最终状态。

不比较对象布局，只比较公开结果、状态和事件序列。

## 实施阶段

### 阶段 A：语义核心

实现 Context、Service、Registry、Fiber、Inject、Effect 和事件。完成依赖消失/恢复、同步/异步清理及隔离测试。

### 阶段 B：完整核心

补齐 Reflect accessor/mixin、配置验证、update/restart、Logger、内部事件、Effect 诊断和错误聚合。

### 阶段 C：配置运行时

实现 YAML/TOML Loader、include、overlay、插件解析、插件组和配置热更新。

### 阶段 D：Harness 兼容层

选择 DeepSeek Harness 的真实插件组合，以 Python 重写对应服务接口，并建立跨语言行为测试和示例应用。

## 架构验收标准

1. 插件加载顺序不影响声明依赖后的最终结果；
2. provider 消失时 consumer 自动卸载，恢复时重新激活；
3. 所有注册项都有明确 owner 和幂等 disposer；
4. 同步与异步清理都能完整等待；
5. 隔离作用域中同名服务互不干扰；
6. waterfall 必须调用 `next()` 才继续；
7. 竞态下不会重复激活、泄漏 Effect 或从 DISPOSED 复活；
8. 配置验证失败不留下部分服务和监听器；
9. Loader 不替代核心依赖调度；
10. 关键行为具有与 TypeScript Cordis 对照的场景测试。

达到阶段 A 是“小而可用的 Python Cordis”；达到阶段 B 才是完整核心；阶段 C 和 D 属于 DeepSeek Harness 级完整运行时。
