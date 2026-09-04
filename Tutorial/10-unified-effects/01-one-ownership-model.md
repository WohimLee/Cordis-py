# 10 — 把所有长期资源统一成 Effect

前面的 Plugin 只返回一个 cleanup。但真实 Plugin 还会创建 Service、listener、child Fiber、background task 和用户资源。如果每种资源各有一套清理表，Fiber dispose 时就要记住所有特殊规则。

Cordis 的答案是：它们都属于 **Effect**。

## 本章目标

```text
Fiber / Context
└── EffectScope
    ├── Service registration Effect
    ├── Event listener Effect
    ├── Child Fiber Effect
    ├── Task Effect
    └── User Effect
```

资源的创建方式不同，但都能表达为：

```text
setup → cleanup
```

Fiber 只需要关闭自己的 EffectScope。

## Step 0：Effect 是一次可逆操作

Effect 不等于 cleanup 函数。它包含完整关系：

```text
执行 setup
    ↓
收集 setup 产生的 cleanup
    ↓
owner 结束时逆序执行 cleanup
```

setup 可以产生零个、一个或多个 cleanup，也可以异步产生它们。

## Step 1：EffectScope 是 owner

每个 activation epoch 创建一个新的 `EffectScope`。安装 Effect 时先把它登记给 scope，再开始 setup；这样 setup 与 dispose 交错时，资源不会逃出所有权。

Scope 关闭后不再接受新 Effect：

```python
await scope.close()
await scope.install(...)  # InactiveEffectError
```

这是“disposed Fiber 永不重新拥有资源”的局部保证。

## Step 2：清理顺序与幂等性

Effect 内多个 cleanup 使用逆序：后创建的资源通常依赖先创建的资源，所以应先拆后创建的。

```text
setup:   A → B → C
cleanup: C → B → A
```

`effect.dispose()` 和 `scope.close()` 都共享第一次创建的 cleanup task，多次调用不会重复清理。

运行：

```bash
uv run pytest Tutorial/10-unified-effects/src/test_chapter10.py -k reverse
```

### Checkpoint A

到这里，Fiber 不再拥有一组裸 cleanup；它拥有 EffectScope，EffectScope 再拥有完整的可逆操作。
