# call-router

语音来电批量路由规划库。上层呼叫系统在一次快照上调用 `plan_calls`，
为整批等待中的来电规划坐席分配；候选、坐席快照与结果全部在内存中，
无任何外部服务依赖。

## 使用

```python
from call_router import Call, plan_calls

calls = [
    Call(call_id=1, mood_score=1, enqueued_at=1712.5,
         tier_candidates=([10], [20])),   # 一级坐席10，二级坐席20
    Call(call_id=2, mood_score=2, enqueued_at=1713.0,
         tier_candidates=([10],)),
]
result = plan_calls(calls, available_agents=[10, 20])
result.assignments        # {1: 20, 2: 10}
result.waiting_call_ids   # ()  未接通的来电（按优先级排序）
```

- `mood_score`：1–5，越低优先级越高；同分比等待时间（早者优先），再同比编号（小者优先）。
- `tier_candidates`：按层级给出的候选坐席，下标 0 为一级；同一坐席出现在多个层级按最低层级计。
- 只能使用候选名单中且当前可用的坐席；每通来电最多一名坐席，每名坐席最多一通来电。

## 优化目标（按字典序）

1. 接通来电总数最多；
2. 按来电优先级逐通比较是否接通，首个不同处接通者胜；
3. 三级候选使用数最少，再二级候选使用数最少；
4. 已接通来电按优先级依次比较坐席编号，小者胜。

实现上将各目标按严格支配关系编码为单个大整数边权，用一次
最大流 + 最小费用流求解（`src/call_router/_flow.py`），结果与输入
排列顺序无关，相同快照重复计算结果一致。

## 测试

```bash
PYTHONPATH=src python3 -m pytest tests -q
```

包含两个必备场景、优先级/层级/坐席编号择优、输入排列不变性，
以及 300 个随机小实例对蛮力枚举的对拍验证。
