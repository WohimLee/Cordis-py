# 11 — 让异步竞态收敛到正确状态

第 09 章有完整状态，第 10 章有完整资源 ownership。但异步程序会在一个 transition 尚未完成时收到新的意图：

```text
Plugin 还在 LOADING，Service 已经消失
Fiber 还在 UNLOADING，Service 又恢复了
Effect setup 还没返回 cleanup，owner 已经 dispose
```

这些情况不能靠“通常执行得很快”解决。

## 本章目标

本章建立一个通用规则：

> 当前 transition 完整做完，再根据最新事实决定下一步。

它需要三个部件：

- 一个 lifecycle lock：同一 Fiber 不并发执行两个 transition；
- 一个 refresh requested flag：合并重复通知，但不丢掉最新意图；
- 每次关键 await 后重新检查 Dependency Epoch 或 dispose intent。

## Step 0：事件是意图，不是命令

Service 消失时，Reflect 只要求 Fiber refresh。它不直接命令 Fiber “立刻进入 PENDING”，因为 Fiber 可能还在 Plugin callback 内部。

```text
Service change → request_refresh()
                     ↓
             唯一 runner 读取最新状态
```

多个通知可以合并成一次检查，因为 Fiber 关心的是最终 Dependency Epoch，不是通知次数。

## Step 1：不要用 sleep 编写竞态测试

测试使用两个 `asyncio.Event`：

```text
started：证明协程已经走到指定位置
release：由测试决定它何时继续
```

这样测试验证的是确定的发生顺序，而不是机器恰好在若干毫秒内完成了什么。

### Checkpoint A

Lock 保护 transition 的唯一性，flag 保存 transition 期间到达的新意图。只用其中一个都不够。
