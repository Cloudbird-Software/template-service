# IR-WG-001 spec 草案：wg_counter 词数统计模块

> 状态：草案（wg-e2e-2026 治理模拟第二幕产出）。
> 上游：`specs/IR-WG-001/intent.yml`（已签署冻结，九字段 schema v1）。

## 1. 术语

- **词（word）**：按 Python `str.split()` 语义切分后的非空片段数。
- **空白（whitespace）**：含 ASCII 空格/制表符/换行、Unicode 空格类别（包括全角空格 `\u3000`）。

## 2. 功能规格

- 暴露 `word_count(text: str) -> int`
- `text` 为 `None` 时视为 `""`，返回 0
- 按上述空白定义分词，返回片段数
- 不抛异常：任意 Unicode 输入均返回非负整数

## 3. 测试规格

- `tests/test_wg_counter.py` 存在且可被 `py -3 -m pytest` 收集
- 至少覆盖：空串、纯空白、英文多词、中英文混合、含全角空格

## 4. 非目标

- 不做词频/统计分布
- 不做 NLP 分词器集成

## 5. 工程红线

- 仅使用 Python 标准库
- 不改 `.github/workflows/**` 与 `Makefile` check 目标
- diff < 400 行
