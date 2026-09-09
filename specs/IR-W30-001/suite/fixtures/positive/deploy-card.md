<!-- 夹具（正样例）：md 契约卡。期望评级见 specs/IR-W30-001/spec-draft.md §7；测试树内安置为 specs/deploy-card.md，S3 语料下应评 A。 -->

# 契约卡 fixture：deploy-card（常驻部署样卡）

- goal: 样例契约卡——常驻部署波，验证全锚定路径评级 A。
- 触及面:
  1. `runtime/bin/install_scheduler.sh`（样例）
  2. `runtime/bin/ceo_dispatch.py`（样例）
- 非目标: 不改调度器既有行为。

## 验收谓词

1. 部署脚本幂等：重复执行无副作用且 rc=0（样例谓词）。
2. 心跳时间戳在一个轮询间隔内更新（样例谓词）。
3. 手动触发单轮模式 rc=0（样例谓词）。
