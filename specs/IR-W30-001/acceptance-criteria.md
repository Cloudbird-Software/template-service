# IR-W30-001 验收标准（逐条机器可验证）

> 上游：`specs/IR-W30-001/intent.yml`（P1–P4）+ `specs/IR-W30-001/spec-draft.md`（规则与 schema 的定义真源）。
> 本清单供第三幕实现自查、第四幕红队攻击、第六幕终验复用；每条给出验证命令与通过判据，无散文验收。
> 命令默认在仓根执行；`SCHEMA` 指 spec-draft §4 的 schema 校验函数（实现须以可独立调用形式交付）。

## AC-1（P1 报告产出且 schema 合法）

- 验证：`py -3 scripts/coverage_report.py`；随后以任意树校验 `SCHEMA(coverage-summary.json)` 无错误。
- 通过：rc=0；`coverage-summary.json` 存在于仓根；`json.load` 成功；schema 校验通过
  （顶层/嵌套键集合精确、类型、枚举 A|B|C|D 与 md|yaml|missing、`sum(by_grade)==cards`、
  cards 按 path 码点序、所有 path 位于 `specs/` 下且无 `..`/盘符/UNC/反斜杠组件、
  `len(remediation)==uncovered_total`、全文件无时间戳键）。

## AC-2（P2 逐卡等级正确）

- 验证：按 spec-draft §6.1 差分矩阵 S0–S4 组装夹具树（映射见 §6.1/§7），逐场景跑命令。
- 通过：S0 三卡（broken→D、no-predicates→D、正样例→D）；S1 scheduler-card→C 其余 D；
  S2 sample 卡（n=3）→B；S3 deploy 卡（n=3）→A；S4 畸形版→D 且不污染同树其他卡评级；
  测试内独立重实现 §3 判定器交叉比对真实树逐卡等级一致。

## AC-3（P3 补救建议）

- 验证：S1（空锚定、有提及）与 S0（空语料）场景跑命令。
- 通过：`uncovered_total>0 ⟺ len(remediation)>0`；每 uncovered 谓词一条且 target=谓词 id，
  每结构性 D 卡一条且 target=`card`；所有 suggestion 非空且为确定性模板（无时间戳）；
  S3 场景全锚定卡无 remediation 条目。

## AC-4（P4 确定性）

- 验证：同树连跑两次比对 `sha256(coverage-summary.json)`；再 `touch` 树内一文件（仅 mtime 变）重跑再比对。
- 通过：三次输出字节全等；rc 均=0。

## AC-5（holdout 三案例）

- 验证：按 `suite/fixtures/holdout/README.md` 程序执行 H1/H2/H3。
- 通过：H1 删卡后该 IR 目录报 D；H2 畸形卡报 D 且 rc=0 不崩溃；H3 空目录空报告 rc=0 且 suite_grade=A；
  三案与答案层（`answer_ref: cnb://stronghold/IR-W30-001/holdout-answers.json`，本体不进仓）期望一致；
  实现代码中 grep 不到任何硬编码期望等级。

## AC-6（属性：任意输入不崩溃）

- 验证：§6.2 属性测试（≥50 组随机字节/空文件/超长行/CRLF/BOM/零宽字符/万条谓词卡）。
- 通过：全部 rc=0、schema 合法、单文件异常不污染他卡评级。

## AC-7（边界）

- 验证：§6.3 六用例（空 specs/、specs 缺失、≥180 字符文件名、≥8 层深度、末尾无换行谓词段、一级 IR 目录缺卡）。
- 通过：空 specs→空报告 suite_grade=A rc=0；specs 缺失→rc=2 且不写/不改输出文件；其余用例不崩溃、schema 合法。

## AC-8（状态）

- 验证：§6.4 三用例（无 suite/ 目录、已有旧输出重跑、夹具在树内）。
- 通过：无 suite/ 照常工作；旧输出被覆盖更新；`specs/**/suite/**` 永不出现在 cards 中。

## AC-9（工程红线）

- 验证：`git diff` 检视 + 依赖 grep。
- 通过：实现仅 Python 标准库（无第三方 import）；不改 `.github/workflows/**` 与 Makefile check 目标；
  Makefile 新增独立 `coverage-report` target（grep 到目标行）；一个 PR 一件事、diff<400 行；
  PR body 含 `Card: template-service#C-W30-001`；无密钥/客户名入仓。

## AC-10（红队攻击面，Wave 4 输入门）

- 验证：独立红队按设计文档 Wave 4 清单攻击：删卡（H1 逃逸尝试）、畸形 YAML 注入、超长路径、
  `../` 相对穿越、`C:\Windows\win.ini` 风格绝对路径、符号链接逃逸、同文件多卡裸 P 号误锚。
- 通过：verdicts.jsonl 全 `survived`（或 breached→修复复验 survived）；输出文件所有路径字段始终界内；
  误锚攻击若实发，按 spec-draft R1 登记并降级复议，不得静默。
