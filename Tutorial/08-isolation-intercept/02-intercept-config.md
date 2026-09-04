# 用 Intercept 逐层修改 Service 配置

Isolation 回答“使用哪一个 Service”。有时 Consumer 找到同一个 Service 后，还需要按所在 Context 调整配置。

例如，最外层规定重试次数，应用作用域补上区域，某个 Inject 再给出本次调用的 timeout。Cordis 把 Context 中间层配置称为 **Intercept**。

## Step 4：`Context.intercept()` 仍然返回派生 Context

```python
regional = root.intercept("database", {"region": "cn"})
```

它不修改 root，而是：

1. 创建 derived Context；
2. 复制已经继承的 intercept chain；
3. 把新配置追加到 `database` 的 chain 尾部。

继续派生时：

```python
tuned = regional.intercept("database", {"timeout": 3})
```

配置顺序是从外到内：

```text
{"region": "cn"} → {"timeout": 3}
```

后加入的内层配置优先级更高。

运行：

```bash
uv run pytest Tutorial/08-isolation-intercept/src/test_chapter08.py -k intercept
```

## Step 5：默认使用 shallow merge

Service 配置有三层来源：

```text
base → Context intercepts（外到内）→ head
```

- `base` 是 Service 提供的基础配置；
- `intercepts` 是 Consumer Context 继承的中间配置；
- `head` 是 Inject mapping 为这次依赖声明提供的配置。

默认合并等价于依次执行 `dict.update()`。后面的同名 key 覆盖前面：

```python
base = {"retry": 1, "shared": "base"}
outer = {"region": "cn", "shared": "outer"}
head = {"timeout": 3, "shared": "inject"}

# 结果：retry、region、timeout 都保留，shared == "inject"
```

这正好启用第 06 章留下的 Inject mapping：

```python
consumer.inject = {
    "database": {"timeout": 3},
}
```

其中 `{"timeout": 3}` 就是 head，优先级最高。

## Step 6：Service 可以定义自定义 merge

Shallow merge 不适合所有数据。例如多个 scope 可能希望把 tag 列表连接起来，而不是让后一个列表覆盖前一个。

Service 可以通过 `Config.merge` 定义自己的规则：

```python
class Config:
    @staticmethod
    def merge(*configs):
        return {"tags": [tag for item in configs for tag in item["tags"]]}
```

Runtime 仍按 `base → outer intercept → inner intercept → head` 传入配置，只把“怎样合并”交给 Service。

本章会验证自定义 merge 收到的顺序。它不是另一套 Intercept 系统。

### Checkpoint B

Intercept 不会改变 Reflect 选择出的 Impl，也不会决定 Fiber 是否激活。它只为已经选中的 Service 解析 Consumer 所需配置。
