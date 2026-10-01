<!-- 夹具（正样例）：md 契约卡。期望评级见 specs/IR-W30-001/spec-draft.md §7；扫描器跳过 specs/**/suite/**，本文件永不作为在役卡出现。测试树内安置为 specs/scheduler-card.md。 -->

# 契约卡 fixture：scheduler-card（调度外壳样卡）

- goal: 样例契约卡——验证 md 卡识别、谓词提取与分级；结构仿 state/specs/w31-scheduler.md 风格。
- 触及面:
  1. `runtime/bin/scheduler.py`（样例）
  2. `runtime/bin/test_scheduler.py`（样例）
- 内容要求:
  1. 单轮与常驻两种模式（样例）
  2. 事件日志 append-only（样例）
- 不做: 不做真实部署；本卡仅为夹具。

## 验收谓词

1. 单测入口全绿：空输入 rc=0 且产出心跳文件（样例谓词）。
2. team 路由任务端到端完成后任务文件移入 done 目录（样例谓词）。
3. schema 缺字段任务被阻断并产生 blocked 事件（样例谓词）。
4. 沙箱根隔离：环境变量重定向后不触碰在役树（样例谓词）。
