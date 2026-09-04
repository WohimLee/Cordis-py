# 07 — Dependency Epoch

第 06 章已经能让 PENDING Consumer 在 Provider 到达后激活。但 Provider 消失后，Consumer 仍然保持 ACTIVE。

只保存“依赖名称”无法解决这个问题：

```text
Consumer 依赖 database

旧 Provider 提供 database
新 Provider 也提供 database
```

名称没有变化，但具体 Service Impl 已经不同。Consumer 上一次运行创建的资源可能仍引用旧 Impl。

Cordis 使用 **Dependency Epoch** 区分这些运行周期。

## 什么是 Epoch

Epoch 是 Fiber 某次 activation 使用的完整依赖快照。快照保存的是 Impl identity，不只是 Service name 或 value。

```text
Epoch A = (database Impl A, cache Impl A)
Epoch B = (database Impl B, cache Impl A)
```

即使两个 database value 都是字符串 `"db"`，只要 Impl 不是同一个对象，它们就属于不同 Epoch。

## Step 0：从名称检查升级为 Impl 快照

第 06 章只判断：

```python
all(ctx.get(name) is not None for name in runtime.inject)
```

现在 Reflect 返回 Impl：

```python
def resolve_epoch(self):
    implementations = []
    for name in self.runtime.inject:
        impl = self.ctx.resolve_impl(name)
        if impl is None:
            return None
        implementations.append(impl)
    return tuple(implementations)
```

返回 `None` 表示至少一个依赖缺失；tuple 表示当前完整 Epoch。

## Step 1：记录正在运行的 Epoch

Fiber 激活前保存候选 Epoch。Plugin setup 完成后再次解析：

```text
setup 前 Epoch == setup 后 Epoch
    ↓
可以发布 ACTIVE

setup 前 Epoch != setup 后 Epoch
    ↓
本次结果已经过期，立即 Cleanup
```

这次“完成后再检查”非常重要，因为异步 setup 期间 Provider 可能已经被替换。

### Checkpoint A

Fiber 不再只知道“依赖齐全”，还知道“本次 activation 使用了哪几个具体 Impl”。下一节用 Epoch 变化驱动卸载和恢复。
