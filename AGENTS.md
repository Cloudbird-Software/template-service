# 本仓库工作约定（AI 与人都必须遵守）

## 硬规则

1. **认证**：所有 git push / PR / Issue 操作用 cloudbird-agent App 令牌，禁止使用任何个人 PAT。
   获取方式（单仓库最小作用域，1 小时有效）：
   `GH_TOKEN=$(REPO=<repo> bash <(curl -sS https://raw.githubusercontent.com/Cloudbird-Software/.github/main/scripts/gh-app-token.sh))`
   需要环境变量 `CB_APP_ID` + `CB_APP_KEY_FILE`（私钥路径）。App 无 Workflows 权限，
   改 `.github/workflows/**` 的分支会被直接拒收——此类改动由人类用自己的凭据提交。
2. 提交前必须本地 `make check` 全绿。做不到就不要说"完成了"。
3. 不准修改 `.github/workflows/**`、`Makefile` 的 check 目标、ruleset —— 除非我明确要求。
4. 不准新增第三方依赖：先列出"依赖名 / 用途 / 许可证 / 是否能用标准库替代"，等我确认。
   禁止引入 AGPL / GPL-3.0 / SSPL 的库。
5. 任何密钥、客户名、客户数据、真实数据库连接串，一律不进仓库。用 .env.example 占位。
6. 一个 PR 只做一件事，diff 尽量 < 400 行。大改先给我方案再动手。

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

## 架构纪律（每个模块都必须遵守）

1. **每个模块一个 public entry**（`index.ts`）。跨模块只能 import entry，禁止深入内部实现文件。`make arch` 会检查。
2. **entry 文件不 export 内部实现类型**——接口必须真正收敛在边界上。
3. **每个模块目录一份 `AGENTS.md`**：写清该模块负责什么、不变量是什么、禁止做什么、如何独立验证。
4. **契约测试在模块边界**，实现细节内部自由。这样模块内可以大改而外部测试不动。
5. **模块大小上限 3000 行**。超过就拆——一个模块必须能被 agent 一次性完整读完。
6. **生成代码进独立目录**（`*.gen.ts`、`baml_client/` 等），禁止手改。
7. **接口设计标准**：一个 LLM 能否仅凭函数签名 + 一行 docstring 就零样本正确使用？
   答案是否 => 接口太浅，重做。
8. **测试优先级**：行为不变量用 property-based test（vitest + fast-check），
   关键输出用 golden test。先写不变量，再写实现。

## 依赖规则

新增依赖前先看 `zizmor.yml` 同级的许可约束；规则引擎在 `.dependency-cruiser.cjs`，
新模块落地时必须同步补全其中的 TODO 边界规则。
