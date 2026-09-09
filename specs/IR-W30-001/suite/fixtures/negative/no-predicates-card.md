<!-- 夹具（负样例）：谓词缺失——卡格式合法但验收谓词段为零条目，应评 D（结构性）。
     期望评级见 specs/IR-W30-001/spec-draft.md §7；测试树内安置为 specs/no-predicates-card.md。
     注意与"无谓词段的 md=非卡被忽略"区分：本夹具段存在但为空。 -->

# 契约卡 fixture：no-predicates-card（谓词缺失样卡）

- goal: 样例契约卡——验证段存在但零条目时评 D。
- 触及面:
  1. `src/index.ts`（样例）

## 验收谓词
