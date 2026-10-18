# RC-LRA 实验报告（清理后）

## 1. 数据完整性检查

| 检查项 | 结果 |
|--------|------|
| baseline 行数 (`trip_initial_plans.jsonl`) | 30 |
| 唯一 ID 数 | 30 |
| 重复 ID | 无 |
| JSON 格式合法性 | 全部合法 |
| 核心字段 (id/request/candidate_attractions/candidate_areas/initial_plan) | 齐全，无缺失 |
| 日期一致性 | 全部通过（5 条旧不一致记录已清理并重生成） |
| 评估 case 数 | 30 |
| case_details.jsonl 必需字段 (id/city/request/before_metrics/after_metrics/baseline_score/repaired_score/risk_count/repairable_count/repaired_count/repair_log_count/latency_ms/risks/repair_log) | 齐全，bad_count=0 |
| summary_metrics.json 论文别名字段 (13 个) | 齐全，missing=[] |

## 2. 关键指标摘要

| 指标 | 值 |
|------|-----|
| 样本数 | 30 |
| WeatherConflictRate_before | 0.1444 |
| WeatherConflictRate_after | 0.1111 |
| LoadViolationRate_before | 0.0111 |
| LoadViolationRate_after | 0.0000 |
| AvgDailyDistance_before (km) | 7.71 |
| AvgDailyDistance_after (km) | 7.63 |
| RouteDistanceReduction | 0.0022 (0.22%) |
| AvgRiskScore_before | 0.1162 |
| AvgRiskScore_after | 0.0995 |
| RiskScoreReduction | 0.082 (8.20%) |
| RepairRate | 0.0722 (7.22%) |
| PlanStructurePreservationRate | 1.0000 |
| LatencyOverheadMs | 2.9 |

## 3. 指标判断

- **AvgRiskScore_after (0.0995) < AvgRiskScore_before (0.1162)**: 风险分下降，符合预期
- **RiskScoreReduction = 8.20%**: 正向改善，但幅度偏小
- **PlanStructurePreservationRate = 1.0000**: 所有修复均未删除景点，结构完全保持
- **RepairRate = 7.22% (case 平均) / 12.90% (全局风险统计)**: 修复率较低，大量可修复风险未被成功修复
- **LatencyOverheadMs = 2.9ms**: 极低延迟，纯规则算法无 LLM 调用
- **LoadViolationRate_before → after**: 0.0111 → 0.0000，过载完全消除
- **WeatherConflictRate_before → after**: 0.1444 → 0.1111，天气冲突部分降低

## 4. 修复率偏低的原因分析

RepairRate 按 case 平均为 7.22%，按可修复风险全局统计为 4/31≈12.90%，主要原因：

1. **hotel_location_mismatch 不修复**：该风险类型标记为 `repairable: false`，因为 RC-LRA 不替换酒店（只给建议），但它是检测数量最多的风险类型（20 次）
2. **route_reorder 全部失败**：路线重排 17 次尝试均未成功，最近邻重排后距离不降则拒绝，修复率 0%。路线距离下降（RouteDistanceReduction=0.0022，仅约 0.22%）主要来自天气交换或过载移动后带来的间接变化，而非路线重排的直接效果
3. **天气交换需要条件**：需要不同天之间存在"雨天户外 + 晴天室内"的配对，且交换后风险分不增，条件较苛刻，13 次可修复中仅 3 次成功（23.1%）

## 5. 典型案例

### Case 1: TRIP-HZ-003 (杭州 3 日历史文化游)

| 属性 | 值 |
|------|-----|
| 风险数 | 1 |
| 可修复数 | 1 |
| 已修复数 | 1 |
| Baseline 风险分 | 0.10 |
| Repaired 风险分 | 0.00 |
| 风险分下降 | 100% |

**风险**: `weather_outdoor_conflict` — 第 2 天小雨，含户外景点"河坊街"
**修复**: `weather_indoor_outdoor_swap` — 将河坊街与第 3 天室内景点"中国丝绸博物馆"交换
**结果**: 交换后风险分从 0.10 降至 0.00，完全消除天气冲突，景点数不变

### Case 2: TRIP-CD-006 (成都 3 日综合游)

| 属性 | 值 |
|------|-----|
| 风险数 | 5 |
| 可修复数 | 3 |
| 已修复数 | 1 |
| Baseline 风险分 | 0.3333 |
| Repaired 风险分 | 0.1167 |
| 风险分下降 | 64.99% |

**风险类型**:
- `weather_outdoor_conflict` (第 3 天雷阵雨，含户外景点大熊猫基地) — 可修复，已修复
- `route_distance_too_long` (第 2 天 13.6km, 第 3 天 54.0km) — 可修复，重排后距离未降，拒绝
- `hotel_location_mismatch` (第 2、3 天酒店距景点 13.5km/53.9km) — 不可修复

**修复 log**:
1. route_reorder 第 2 天: 距离 13.6km → 13.6km，未降低，拒绝
2. route_reorder 第 3 天: 距离 54.0km → 54.0km，未降低，拒绝
3. weather_indoor_outdoor_swap: 大熊猫基地与第 2 天室内景点交换，0.3333 → 0.1167，接受

**景点数保持**: 修复前后总景点数不变

### Case 3: TRIP-XA-002 (西安 3 日亲子美食游)

| 属性 | 值 |
|------|-----|
| 风险数 | 5 |
| 可修复数 | 3 |
| 已修复数 | 1 |
| Baseline 风险分 | 0.3167 |
| Repaired 风险分 | 0.2333 |
| 风险分下降 | 26.33% |

**风险类型**:
- `daily_load_overflow` (第 2 天 4 景点 > 轻松型上限 3) — 可修复，已修复
- `route_distance_too_long` (第 1 天 33.0km, 第 3 天 26.8km) — 可修复，重排后距离未降，拒绝
- `hotel_location_mismatch` (第 1、3 天酒店距景点 34.1km/27.0km) — 不可修复

**修复 log**:
1. daily_load_overflow: 将第 2 天低优先级景点移至第 3 天，0.3167 → 0.2333，接受
2. route_reorder 第 1 天: 距离未降，拒绝
3. route_reorder 第 3 天: 距离未降，拒绝

**景点数保持**: 修复前后总景点数不变

## 6. 风险类型分布统计

| 风险类型 | 出现次数 | 可修复次数 | 已修复次数 | 修复率 |
|----------|----------|-----------|-----------|--------|
| hotel_location_mismatch | 20 | 0 | 0 | N/A (仅建议) |
| route_distance_too_long | 17 | 17 | 0 | 0% |
| weather_outdoor_conflict | 13 | 13 | 3 | 23.1% |
| daily_load_overflow | 1 | 1 | 1 | 100% |
| location_missing | 1 | 0 | 0 | N/A |
| **合计** | **52** | **31** | **4** | **12.90%** |

注:
1. hotel_location_mismatch 和 location_missing 的 repairable=false，不计入 RepairRate 分母。
2. summary_metrics.json 中的 RepairRate=0.0722 是按 case 平均后的修复率；按全部可修复风险数量统计，全局可修复风险修复率为 4/31≈12.90%。
3. route_distance_too_long 17 次尝试均未成功，路线距离下降（RouteDistanceReduction=0.0022，仅约 0.22%）主要来自天气交换或过载移动后带来的间接变化，而非路线重排的直接效果。

## 7. 实事记录

1. RC-LRA 的核心优势是**零 LLM 调用 + 极低延迟 (2.9ms)**，适合作为行程规划的实时安全网
2. `daily_load_overflow` 修复效果好（100%），过载景点可成功移动至轻载天
3. `weather_indoor_outdoor_swap` 修复率 23.1%（13 次可修复中 3 次成功），受限于配对条件
4. `route_reorder` 17 次尝试全部失败，修复率 0%，路线距离下降（RouteDistanceReduction=0.0022）主要来自天气交换或过载移动的间接影响，而非路线重排本身
5. `hotel_location_mismatch` 仅检测和建议，不执行修复（出现 20 次，占比最高）
6. `PlanStructurePreservationRate = 1.0` 是 RC-LRA "局部修复" 设计的体现——任何修复不得删除景点
7. 5 条旧日期不一致记录（TRIP-HZ-005/CD-005/BJ-005/XA-005/XM-005）已清理并重生成，当前 30 条 baseline 日期全部一致

## 8. 数据清理操作记录

| 操作 | 详情 |
|------|------|
| 备份 | `trip_initial_plans.before_fix_005.backup.jsonl` |
| 删除 | 5 条日期不一致记录 (TRIP-*-005) |
| 补生成 | 通过 `--ids` 参数只补 5 条，25 条已有样本不受影响 |
| 日期一致性验证 | 30 条全部通过，line_count=30, unique_count=30, bad=[] |
| case_details 补全 | 新增 `request`/`before_metrics`/`after_metrics` 字段，`repaired_score` 改为完整 dict |
| 重新评估 | 基于 30 条干净 baseline 重跑 RC-LRA 评估 |
