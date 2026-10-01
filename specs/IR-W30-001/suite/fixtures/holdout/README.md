# holdout（强 holdout · IR-W30-001）

答案层指针（唯一，答案本体永不进仓，FR-001/ADR-0108）：

```
answer_ref: cnb://stronghold/IR-W30-001/holdout-answers.json
```

本地演练镜像（CEO 工作区，不在本仓）：`runtime/runs/stronghold-sim/holdout-answers.json`。

## 三案例程序

每例先组装临时测试树，跑 `coverage-report`，本地复算判定，跑完恢复树。判定不采信任何外部自报数字。

| id | 程序 | 断言 | 答案层期望 |
|----|------|------|-----------|
| H1 | 组装含 `specs/IR-HOLD-001/card.yml` 的树 → **删除该 card.yml**（保留目录）→ 跑报告 | 该一级 IR 目录合成 missing 卡 | `expected_grade: "D"` |
| H2 | 将 `suite/fixtures/negative/broken-card.yml` 内容置为 `specs/IR-BROKEN-000/card.yml` → 跑报告 | rc=0、该卡 D、报告 schema 合法（不崩溃） | `expected_grade: "D"` |
| H3 | `specs/` 为空目录 → 跑报告 | rc=0、cards=[]、totals 全 0、remediation=[] | `expected_grade: "A"`（空集 vacuous） |

## 纪律

- 实现方不得把期望等级硬编码进实现；判定只允许依赖 spec-draft §3 规则。
- 红队（Wave 4）以本指针指向的答案层为盲判基准；breached 项登记 `archive/neg-results/` 五元组。
- 本目录与其余 `suite/**` 一样被扫描器排除，永不作为在役卡出现。
