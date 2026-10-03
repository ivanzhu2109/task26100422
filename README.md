# call_router —— 语音来电批量路由规划库

纯内存、无外部依赖的 Python 库，由上层呼叫系统直接调用：
传入待分配来电、当前可用坐席与每通来电的三级候选名单，
一次规划整批来电的坐席分配方案。

## 使用

```python
from datetime import datetime
from call_router import Call, Snapshot, plan

snapshot = Snapshot(
    calls=(
        Call(call_id=1, emotion=1,
             enqueued_at=datetime(2026, 10, 3, 9, 0),
             candidates=((10,), (20,))),   # 一级坐席10，二级坐席20
        Call(call_id=2, emotion=2,
             enqueued_at=datetime(2026, 10, 3, 9, 1),
             candidates=((10,),)),
    ),
    available_agents=frozenset({10, 20}),
)
result = plan(snapshot)
result.assignments  # {1: 20, 2: 10} —— 来电编号 -> 坐席编号
result.waiting      # 未接通、继续等待的来电编号（升序）
```

## 规划目标（按字典序依次优化）

1. 接通来电总数最多；
2. 接通名单按来电优先级（情绪分低 → 等待早 → 编号小）逐通字典序最大；
3. 三级（升级）分配数最少，其次二级分配数最少；
4. 已接通来电按优先级依次获得尽可能小的坐席编号。

约束：每通来电最多一名坐席，每名坐席最多接一通；只能使用候选名单中
且当前可用的坐席；同一坐席出现在多个层级时按最低层级计算。
相同快照重复计算或改变输入排列顺序，结果一致。

## 测试

```bash
python3 -m pytest tests/ -q
```
