# IR-W30-001 spec 草案：契约卡覆盖率报告（coverage-report）

> 状态：草案（w30 e2e 第二幕产出，过"测试先行门"用）。
> 上游：`specs/IR-W30-001/intent.yml`（已签署冻结，九字段 schema v1）。本文件是规格不是实现；
> 实现波（Wave 3 / Card C-W30-001）按此交付 `scripts/coverage_report.py` + Makefile target + 测试。
> 红线对齐：仓 AGENTS.md 硬规则（不动 `.github/workflows/**`、不改 Makefile check 目标、
> 仅标准库、一个 PR 一件事 diff<400 行）；判定/执行分离（本报告逻辑可本地复算，不依赖外部服务）。

## 0. 一页结论

`make coverage-report`（等价直调 `py -3 scripts/coverage_report.py`）扫描 `specs/` 下全部契约卡，
对每张卡的验收谓词判定测试锚定情况，给出 A/B/C/D 覆盖等级，写仓库根 `coverage-summary.json`，
未覆盖时给逐条补救建议。纯生成侧、零网络、零新依赖（Python 标准库）、输出确定性（同输入同输出）。

## 1. 术语与对象模型

- **契约卡（card）**：`specs/` 树下三类对象之一：
  - `md 卡`：`specs/**/*.md`，且文件内含**精确**验收谓词段（见 §2.1；段标题行必须独占一行，
    带后续文字的标题不是谓词段——本 spec 文件自身即靠此规则避免自命中）；
  - `yaml 卡`：`specs/*/card.yml`（含 `specs/IR-*/card.yml`，按文件名精确匹配 `card.yml`）；
  - `missing 卡`：一级子目录 `specs/IR-*/` 存在、但目录内既无 `card.yml` 也无 md 卡
    ——合成一张"缺卡清单"条目（holdout H1 的判定基础：删卡留目录 → 报 D）。
- **谓词（predicate）**：从卡的验收谓词段提取的条目，含 `id`（`P1..Pn`，文档序）与 `text`。
- **锚定语料（corpus）**：`tests/**` ∪ `quality/**` 下全部文本文件（按相对路径 POSIX 形态排序）。
- **card_id**：md 卡 = 文件名去扩展名；yaml 卡 = 父目录名（`specs/card.yml` → `card`）；missing 卡 = 目录名。

## 2. 卡发现与谓词提取（正则级，quality_speed_knobs 授权）

### 2.1 md 卡识别

验收谓词段起点为以下两种**独占一行**的形态之一（容忍行尾空白与 CRLF；读入先剥 BOM、按 UTF-8 解码失败即按 §2.3 降级）：

- 标题形态：`^#{1,6}[ \t]+验收谓词[ \t]*$`
- 列表形态：`^[-*][ \t]+验收谓词:[ \t]*$`（`state/specs/w31-scheduler.md`、`w32-deploy.md` 风格）

段范围：起点行到下一个同级或更高级 md 标题 / 下一个列表形态字段行 / 文件末。段内谓词条目 = `^[ \t]*(\d+)[.、][ \t]*(.+)$`，
`id = P<编号>`，`text` 为该行剩余内容；续行（非空且不匹配条目、非标题）并入上一条 text，空白串规约单空格。
无验收谓词段的 md = 非卡，**忽略且不入报告**（与"缺卡"区分；这是有意行为，红队可攻击此边界）。

### 2.2 yaml 卡识别（受支持子集）

仅接受行级 YAML 子集：`key: value`、`key: >` 折叠块、`- 文本` 与 `- key: value` 列表项、双引号字符串（必须闭合）、
2 空格缩进、禁 tab。谓词块键名 = `predicates` 或 `expected_changes`（intent.yml 风格）；
条目 `- <ID>: <text>` 提取 `id=<ID>`、`text=<text>`；条目 `- <text>`（无 id）按序编 `P<n>`。
任一行违反子集文法（引号/中括号不闭合、tab 缩进、无法解析的键值）→ **畸形卡**：不中断扫描，该卡记 D（holdout H2 基础）。

### 2.3 读取降级

UTF-8 解码失败 / 不可读文件 → 视为畸形卡（D），不崩溃、rc 不变。任何单卡异常都不得中断整体扫描（fail-soft per card, fail-closed per run）。

### 2.4 扫描排除

路径任一组件名为 `suite` 的子树整体跳过（夹具不是在役卡）；隐藏目录（`.` 开头组件）跳过。

## 3. 锚定与 A/B/C/D 评级规则（精确判定条件）

对每张提取出 n≥1 条谓词的卡，逐谓词判定：

- **anchored(谓词)** = 存在语料文件 f，使 f 同时包含 card_id（子串精确匹配）与该谓词 id 的整词匹配
  （`(?<![A-Za-z0-9_])P<k>(?![A-Za-z0-9_])`；yaml 卡自定义 id 同理做整词匹配）。**同文件共现**是 v1.0 有意语义：
  跨卡同 P 号碰撞由共现条件消除；已知残余风险（同文件提多卡+裸 P 号互相误锚）记 §9，红队 Wave 4 重点攻击面。
- **mentioned(卡)** = 存在语料文件包含 card_id。

评级（按序短路判定；结构性问题优先，宁保守不误高）：

| 条件（按序） | 等级 |
|---|---|
| missing 卡 / 畸形卡 / n=0（谓词缺失） | **D** |
| anchored 数 == n（n≥1，全部锚定） | **A** |
| 1 ≤ anchored 数 < n | **B** |
| anchored 数 == 0 且 mentioned | **C**（仅提及） |
| anchored 数 == 0 且未提及 | **D**（无覆盖） |

- **suite_grade** = 全卡最差等级（D>C>B>A 序）；卡数为 0 时 = **A**（空集 vacuous truth，与
  stronghold 答案层 H3 `expected_grade: "A"` 对齐，见 §8）。
- evidence 字段：取语料序中**第一个**满足 anchored 的文件相对路径（POSIX 正斜杠）；未锚定 = `null`。排序保证确定性。

## 4. coverage-summary.json schema（v1.0）

仓库根 UTF-8（无 BOM）、LF、结尾换行；`json.dumps(..., ensure_ascii=False, indent=2)`，键序固定如下，
**无任何时间戳/mtime 字段**（P4 确定性由构造保证）。顶层键集合**精确**为：

```json
{
  "schema_version": "1.0",
  "ir_id": "从 specs/**/intent.yml 按路径序首个提取 ir_id；无则 null",
  "tool": "coverage-report",
  "spec_root": "specs",
  "totals": {
    "cards": "int ≥0，== len(cards)",
    "predicates_total": "int ≥0",
    "predicates_anchored": "int ≥0",
    "uncovered_total": "int ≥0，== Σ uncovered_count + 结构性 D 卡数（grade=D 且 predicates 空）",
    "by_grade": {"A": "int", "B": "int", "C": "int", "D": "int", "四键合计 == cards"},
    "suite_grade": "enum A|B|C|D"
  },
  "cards": [
    {
      "card_id": "string",
      "path": "仓库相对 POSIX 路径；missing 卡 = 目录路径 + '/'。必须位于 specs/ 下、无 .. 组件、无盘符/UNC/反斜杠",
      "kind": "enum md|yaml|missing",
      "grade": "enum A|B|C|D",
      "predicates": [
        {"id": "string", "text": "string", "anchored": "bool", "evidence": "string|null"}
      ],
      "uncovered_count": "int ≥0，== anchored==false 的谓词数"
    }
  ],
  "remediation": [
    {"card_id": "string", "target": "谓词 id 或字面 card", "suggestion": "非空 string，确定性模板"}
  ]
}
```

- `cards` 按 `path` 码点序排序；`predicates` 按文档序；`remediation` 按 (card_id, target) 排序。
- **remediation 完备律**：`len(remediation) == uncovered_total`；`remediation 非空 ⟺ uncovered_total > 0`（P3）。
  每 uncovered 谓词一条（target=谓词 id）；每个结构性 D 卡一条（target=`card`）。建议文案用固定模板（含 card_id/id，不含时间）。
- schema 校验 = 全部上述约束的机器检查（键集合精确、类型、枚举、排序、路径约束、完备律），实现为可独立复用的校验函数，测试直接调用。

## 5. 验收谓词 P1–P4 的机器可判定定义（intent.yml 逐条对应）

- **P1（报告产出且 schema 合法）**
  判定方法：仓根执行 `py -3 scripts/coverage_report.py`，断言 rc=0；`coverage-summary.json` 存在；
  `json.load` 成功；调用 §4 schema 校验函数返回无错误（键集合精确/类型/枚举/合计恒等/排序/路径约束/完备律全过）。
- **P2（逐卡 A/B/C/D 等级）**
  判定方法：差分夹具矩阵（§6.1、§7）逐 fixture 断言期望等级；属性测试断言任意卡文件都有等级（§6.2）；
  等级值 ∈ enum 且与 §3 规则独立重推导一致（测试内重实现一份判定器交叉比对）。
- **P3（未覆盖给补救建议）**
  判定方法：构造空语料场景（见 §6.1 S1）运行 → 断言 `remediation` 非空且 `len == uncovered_total`，
  每条 suggestion 非空；再构造全锚定场景（S3）→ 断言 `remediation == []`。
- **P4（可重复执行、输出确定）**
  判定方法：同树连跑两次 → 两份 `coverage-summary.json` 字节相等（sha256 相同）；
  再对树内一文件 touch（仅改 mtime 不改内容）后重跑 → 输出仍不变（证明无时间/ctime 泄漏）。

## 6. 测试设计（逐类；测试先行门要求件）

### 6.1 差分（正常/异常 YAML）

同一引擎、单维变更、结果按期望表翻转。夹具→测试树映射由夹具台（harness）执行：
`positive/sample-card.yml → specs/IR-SAMPLE-000/card.yml`，`positive/*-card.md → specs/<stem>.md`，
`negative/broken-card.yml → specs/IR-BROKEN-000/card.yml`，`negative/no-predicates-card.md → specs/no-predicates-card.md`。

| 场景 | 语料（tests/ 注入文件） | 期望 |
|---|---|---|
| S0 纯结构差分 | 空 | broken-card→D（rc=0 不崩溃）；no-predicates→D；positive 各卡→D（无语料即无覆盖） |
| S1 仅提及 | 文件含 `scheduler-card` | scheduler-card→C，其余卡→D；remediation 非空 |
| S2 部分（yaml 差分正侧） | 文件含 `IR-SAMPLE-000` 与 `P2` | sample 卡 n=3、anchored=1 → B |
| S3 全锚定 | 文件含 `deploy-card` 与 `P1`、`P2`、`P3` | deploy 卡 → A，remediation 对该卡为空 |
| S4 畸形差分 | 把 sample-card.yml 删一个引号变畸形 | 同树内合法版→按 S2，畸形版→D，其余卡评级不受污染 |

异常 YAML 除 S4 外覆盖：tab 缩进、`[1, 2` 未闭合中括号、`key:` 后无值且无子块（按 §2.2 子集判畸形）。

### 6.2 属性（任意卡文件都能出报告）

性质：**对任意**放入 `specs/` 的文件内容（随机字节、空文件、超长单行、CRLF、带 BOM、全 Unicode 零宽字符、
10,000 条谓词的超大卡），命令 rc=0、产出 schema 合法报告、该文件要么被忽略要么获得等级，绝不崩溃、绝不污染其他卡评级。
实现为循环 N≥50 组生成输入的属性测试；"出报告"是全函数——输入树是自变量，报告是全定义的因变量。

### 6.3 边界（空 specs/、超长文件名等）

| 用例 | 期望 |
|---|---|
| `specs/` 存在且为空 | 空报告：cards=[]、totals 全 0、suite_grade=A、remediation=[]、rc=0（holdout H3） |
| `specs/` 目录不存在 | rc=2、stderr 一行错误、不写/不改 coverage-summary.json |
| 文件名 ≥180 字符（逼近/超 Windows 常规路径预算） | 不崩溃：文件系统接受则正常扫出该卡并全路径入报告；FS 拒建则该卡缺席且 schema 仍合法、rc=0 |
| 路径深度 ≥8 层的 `specs/a/b/.../card.md` | 正常扫描（递归行走）；其所在非一级 `IR-*` 目录不触发缺卡规则 |
| 谓词段位于文件末且无换行符 | 正常提取 |
| 一级 `IR-*` 目录存在但无任何卡文件 | 合成 missing 卡、grade=D（holdout H1 规则常态版） |

### 6.4 状态（suite/ 目录不存在等）

| 用例 | 期望 |
|---|---|
| 仓内无任何 `suite/` 目录（先有鸡先有蛋场景） | 命令照常工作——扫描不依赖夹具存在（§2.4 只是从卡面排除 suite） |
| 仓根已有上一次 coverage-summary.json | 重跑覆盖写，内容随树更新（幂等）；结合 P4 双跑比对 |
| 夹具目录自身在树内（specs/**/suite/**） | 被跳过：夹具永不作为卡出现在报告里（自指防护） |

## 7. 夹具期望表（fixtures 与 spec 的唯一对照真源）

| 夹具 | 树内安置 | 任意语料下的结构期望 |
|---|---|---|
| `suite/fixtures/positive/scheduler-card.md` | `specs/scheduler-card.md` | md 卡、n=4；等级随语料 D/C/B/A（见 §6.1 S0–S3） |
| `suite/fixtures/positive/deploy-card.md` | `specs/deploy-card.md` | md 卡、n=3；S3 语料下 A |
| `suite/fixtures/positive/sample-card.yml` | `specs/IR-SAMPLE-000/card.yml` | yaml 卡、n=3；S2 语料下 B |
| `suite/fixtures/negative/broken-card.yml` | `specs/IR-BROKEN-000/card.yml` | 畸形 yaml 卡、predicates=[]、D、rc=0 |
| `suite/fixtures/negative/no-predicates-card.md` | `specs/no-predicates-card.md` | md 卡、n=0（段存在但空）、D |

## 8. holdout 设计（强 holdout，ADR-0108 三阵地）

- **答案层唯一指针**：`answer_ref: cnb://stronghold/IR-W30-001/holdout-answers.json`。
  答案本体存 CNB 私有阵地（本地演练镜像 `runtime/runs/stronghold-sim/holdout-answers.json`，在 CEO 工作区，**永不进仓**）；
  仓内侧只见本节与 `suite/fixtures/holdout/README.md` 的指针与流程（FR-001 信息梯度）。
- **三案例程序**（每例跑完恢复树，判定全部本地复算、不采信外部自报）：
  - **H1 删卡标 D**：组装含 `specs/IR-HOLD-001/card.yml` 的树 → 删除该 card.yml（保留目录）→ 跑报告 →
    断言该目录合成 missing 卡 grade=D。答案层期望 `expected_grade: "D"`。
  - **H2 畸形标 D 不崩溃**：置 `negative/broken-card.yml` 内容为 `specs/IR-BROKEN-000/card.yml` → 跑报告 →
    断言 rc=0、该卡 grade=D、报告 schema 合法。答案层期望 `expected_grade: "D"`。
  - **H3 空目录空报告**：`specs/` 为空目录 → 跑报告 → 断言 rc=0、cards=[]、suite_grade=A。
    答案层期望 `expected_grade: "A"`。
- 答案层文件含 `suite_id` 与逐案 `id/desc/expected_grade`；红队与验收方以答案层为盲判基准，
  实现方不得将期望值硬编码进实现（判定只允许依赖 §3 规则）。

## 9. 非目标与已知残余风险

- 非目标（承 intent.yml nongoals）：不做行级代码覆盖率；不改 CI workflow 与 Makefile check 目标；
  零新依赖；不自动修复只出建议。
- 已知风险 R1：同文件共现锚定的跨卡误锚残余（两卡被同一测试文件提及+裸 P 号）——v1.0 接受，
  Wave 4 红队攻击面，误锚实发时按宁保守原则降级规则复议。
- 已知风险 R2：md 无谓词段被忽略（非卡）与"删卡"的区分依赖 missing 卡规则只在一级 `IR-*` 目录生效——
  非该形态的删卡不可检（记录为能力边界）。
- 已知风险 R3：`specs/IR-W30-001/` 自身在现状（只有 intent.yml，无 card.yml）首跑即正确报 missing D——
  这不是缺陷而是 H1 规则的正确行为；实现波可补 `card.yml` 消除该噪声。

## 10. v1.1 勘误（w30 修复波，依据红队 RT06/RT20）

> 本节是对 §2.2/§2.4 的两条规则澄清（v1.1），由 w30 红队（24 攻击 2 breached）驱动，
> 实现与常驻回归（`tests/test_coverage_report_redteam.py`）已按此对齐。证据（只读）：
> `reports/redteam-w30-sim/{summary.md,verdicts.jsonl}`（CEO 工作区）。

- **E1 符号链接一律跳过（修订 §2.4）**：specs/ 与语料侧（tests/ ∪ quality/）枚举目录项时，
  符号链接（文件或目录）一律跳过——不跟随、不作为卡、不作为语料、不参与一级 IR-* 目录的
  missing 合成、因而不产生别名重复卡。两侧行为自此对称。
  依据：**RT06**（specs/ 内目录符号链接→仓外卡以 `specs/escape-dir/secret-card.md` 入报告；
  语料侧链接未被跟随，行为不对称）与 **RT07** 观察项（specs/loop→specs 自指环产生 63 条别名卡）。
- **E2 谓词块键名单独封闭（澄清 §2.2）**：谓词块仅由键名 `predicates` / `expected_changes` 的
  空值键开启；解析器遇**其它**键的空值键（任意缩进，含谓词块内嵌套键）时复位列表延续状态，
  该键子块下的列表项永不成为谓词；谓词块被复位后可由后续谓词块键名再次开启。
  依据：**RT20**（`predicates:` 后跟 `other:` 及 2 个列表项被续收为 P2/P3，n=1→3，
  语料含裸 P2 时等级 C→B 虚高，违反宁保守原则）。
