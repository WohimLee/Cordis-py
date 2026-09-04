# Effect 的返回形式与所有权树

## Step 3：统一同步和异步结果

Effect setup 可以返回：

- `None`；
- 一个同步或异步 cleanup callable；
- cleanup 的 iterable；
- cleanup 的 async iterable；
- awaitable，完成后再返回上述任一种结果。

`_collect()` 递归处理这些形式，最终只把 callable 放入 cleanup stack。字符串虽然是 iterable，但不是合法 cleanup 集合，必须拒绝。

如果 setup 在已经产生部分 cleanup 后失败，Effect 会先回滚已有资源，再把原错误抛出。

## Step 4：cleanup 失败不能停止后续清理

假设三个资源都要关闭，第二个抛错：

```text
cleanup C：成功
cleanup B：失败
cleanup A：仍然必须执行
```

所有失败最后放进 Python 的 `BaseExceptionGroup`。它是 JavaScript `AggregateError` 的等价表达。

运行：

```bash
uv run pytest Tutorial/10-unified-effects/src/test_chapter10.py -k failure
```

## Step 5：nested Effect 形成诊断树

一个 setup 内再调用 `ctx.effect()` 时，新 Effect 归当前 Effect 所有：

```text
plugin("agent")
├── provide("agent")
├── on("message")
└── task("worker")
```

父 Effect cleanup 会关闭 child Effect。Metadata tree 让 Logger 或 observer 能解释调用链，但真正的清理仍由同一个 Effect 完成；诊断信息不是第二套生命周期机制。

本章用 `contextvars.ContextVar` 记录当前正在 setup 的 Effect。它适合 Python async task 的调用上下文，对应 TypeScript 实现中的当前 effect 追踪能力。

### Checkpoint B

Effect tree 同时表达两件事：

- ownership：父资源结束时子资源必须结束；
- diagnostics：可以看到资源由哪一步创建。
