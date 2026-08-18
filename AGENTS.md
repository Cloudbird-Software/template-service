# 本仓库工作约定（AI 与人都必须遵守）

## 硬规则

1. 提交前必须本地 `make check` 全绿。做不到就不要说"完成了"。
2. 不准修改 `.github/workflows/**`、`Makefile` 的 check 目标、ruleset —— 除非我明确要求。
3. 不准新增第三方依赖：先列出"依赖名 / 用途 / 许可证 / 是否能用标准库替代"，等我确认。
   禁止引入 AGPL / GPL-3.0 / SSPL 的库。
4. 任何密钥、客户名、客户数据、真实数据库连接串，一律不进仓库。用 .env.example 占位。
5. 一个 PR 只做一件事，diff 尽量 < 400 行。大改先给我方案再动手。

## 必须做

- 改任何行为，同时补/改测试；bug 修复必须先写一个能复现的失败测试。
- 对外接口变更写进 CHANGELOG.md。
- 提交信息用 Conventional Commits：feat/fix/chore/refactor/docs/test。
- 涉及数据库或数据结构变更，写正向迁移 + 回滚说明。

## 交付上下文

- 客户在本地部署，升级靠 GitHub Release 附件；不要假设有 CI/CD 直连生产。
- 兼容性优先于优雅：不为了重构去动客户已经在跑的路径。

## 怎么算完成

`make check` 绿 + PR 描述写清"怎么验证" + gate 通过。
