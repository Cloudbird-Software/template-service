# -*- coding: utf-8 -*-
"""IR-W30-001 契约卡覆盖率报告（coverage-report）。

扫描 specs/ 下全部契约卡，对每张卡的验收谓词判定测试锚定情况，给出 A/B/C/D
覆盖等级，写仓库根 coverage-summary.json，未覆盖时给逐条补救建议。

规格真源：specs/IR-W30-001/spec-draft.md（§1 对象模型、§2 卡发现与谓词提取、
§3 锚定与评级、§4 schema、§9 残余风险）。纯生成侧、零网络、零新依赖（仅
Python 标准库）、输出确定性（同输入同输出，无任何时间戳字段）。
判定/执行分离：本脚本可本地独立复算，不依赖外部服务。

用法（仓库根）：
    py -3 scripts/coverage_report.py        # 或 python3 / python
退出码：0 正常（含空 specs/、含畸形卡）；2 specs/ 缺失或非目录（不写输出）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0"
TOOL = "coverage-report"
SPEC_ROOT = "specs"
OUTPUT_NAME = "coverage-summary.json"
CORPUS_TOPS = ("tests", "quality")

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}  # 值越大越差

# §2.1 md 验收谓词段起点：标题形态 / 列表形态（均须独占一行，容忍行尾空白）
MD_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+验收谓词[ \t]*$")
MD_LIST_FIELD_RE = re.compile(r"^[-*][ \t]+验收谓词:[ \t]*$")
MD_ANY_HEADING_RE = re.compile(r"^(#{1,6})(?:[ \t]+|$)")
MD_LIST_ANY_FIELD_RE = re.compile(r"^[-*][ \t]+[^ \t][^:]*:[ \t]*$")
MD_ITEM_RE = re.compile(r"^[ \t]*(\d+)[.、][ \t]*(.+)$")

# §3 整词匹配锚定
WORD_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9_]+)(?![A-Za-z0-9_])")

TS_KEY_RE = re.compile(
    r"^(ts|time|timestamp|mtime|ctime|atime|date|generated_at|created_at|updated_at|scanned_at)$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# 卡发现（§1/§2）
# --------------------------------------------------------------------------

def iter_tree(root: Path):
    """递归枚举 root 下文件；跳过 suite/ 子树与隐藏组件（§2.4）。返回 POSIX 相对路径。"""
    if not root.is_dir():
        return
    stack = [""]
    while stack:
        rel = stack.pop()
        base = root / rel if rel else root
        try:
            entries = sorted(base.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            child = f"{rel}/{entry.name}" if rel else entry.name
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if entry.name == "suite":
                    continue
                stack.append(child)
            elif entry.is_file():
                yield child


def discover_cards(spec_root: Path):
    """返回 (md 卡, yaml 卡, missing 卡, 畸形 md 路径集)。

    md 卡=含精确验收谓词段的 .md；yaml 卡=文件名精确 card.yml；missing 卡=一级
    IR-* 目录内既无 card.yml 也无 md 卡（§1）。md 无谓词段=非卡，忽略不入报告。
    """
    all_rel = list(iter_tree(spec_root))
    yaml_cards = []
    dir_has_yml = set()   # 含 card.yml 的一级目录
    for rel in all_rel:
        parts = rel.split("/")
        if parts[-1] == "card.yml":
            yaml_cards.append(rel)
            if len(parts) >= 2:
                dir_has_yml.add(parts[0])

    md_cards = []
    malformed_md = set()
    md_card_dirs = set()  # 含 md 卡的一级目录
    for rel in all_rel:
        parts = rel.split("/")
        if not parts[-1].endswith(".md"):
            continue
        card_id = parts[-1][:-3]
        try:
            text = (spec_root / rel).read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            malformed_md.add(rel)  # 解码失败=畸形 md 卡，仍入报告（§2.3）
            md_cards.append(rel)
            if len(parts) >= 2:
                md_card_dirs.add(parts[0])
            continue
        if extract_md_section(text) is not None:
            md_cards.append(rel)
            if len(parts) >= 2:
                md_card_dirs.add(parts[0])

    missing = []
    try:
        level1 = sorted(p.name for p in spec_root.iterdir()
                        if p.is_dir() and not p.name.startswith(".") and p.name != "suite")
    except OSError:
        level1 = []
    for dirname in level1:
        if not dirname.startswith("IR-"):
            continue
        if dirname not in dir_has_yml and dirname not in md_card_dirs:
            missing.append(f"{SPEC_ROOT}/{dirname}/")

    return md_cards, yaml_cards, missing, malformed_md


# --------------------------------------------------------------------------
# 谓词提取（§2.1 md / §2.2 yaml 子集）
# --------------------------------------------------------------------------

def extract_md_section(text: str):
    """返回谓词条目 [(id, text)]；无谓词段=None（非卡）；段存在但空=[]。

    段范围（§2.1）：起点行到下一个同级或更高级 md 标题 / 下一个列表形态字段行 /
    文件末。续行（非空且不匹配条目、非标题）并入上一条 text，空白串规约单空格。
    """
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    start_idx = start_level = None
    is_list_form = False
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        m = MD_HEADING_RE.match(line)
        if m:
            start_idx, start_level = i, len(m.group(1))
            break
        if MD_LIST_FIELD_RE.match(line):
            start_idx, start_level, is_list_form = i, None, True
            break
    if start_idx is None:
        return None
    entries = []
    for raw in lines[start_idx + 1:]:
        line = raw.rstrip()
        hm = MD_ANY_HEADING_RE.match(line)
        if hm:
            # 标题形态段：同级或更高级（级别数 ≤ 起点级）结束；列表形态段：任意标题结束
            if is_list_form or start_level is None or len(hm.group(1)) <= start_level:
                break
            continue
        if MD_LIST_ANY_FIELD_RE.match(line):
            break
        m = MD_ITEM_RE.match(line)
        if m:
            entries.append([f"P{m.group(1)}", re.sub(r"\s+", " ", m.group(2)).strip()])
            continue
        stripped = line.strip()
        if stripped and entries:
            entries[-1][1] = re.sub(r"\s+", " ", f"{entries[-1][1]} {stripped}").strip()
    return entries


class YamlMalformed(Exception):
    """§2.2 行级 YAML 子集违例（引号/中括号不闭合、tab 缩进、无法解析的键值）。"""


def _check_value(value: str):
    v = value.strip()
    if not v:
        return
    if v.startswith('"'):
        if len(v) < 2 or not v.endswith('"'):
            raise YamlMalformed(f"未闭合引号: {v!r}")
        return
    if "[" in v and "]" not in v.split("[", 1)[1]:
        raise YamlMalformed(f"未闭合中括号: {v!r}")
    if v.count('"') % 2 == 1:
        raise YamlMalformed(f"未闭合引号: {v!r}")


def parse_yaml_subset(text: str):
    """行级 YAML 子集解析（§2.2），返回谓词条目 [(id, text)]；违例抛 YamlMalformed。"""
    entries = []
    counter = 0
    folded_indent = None  # `key: >` 折叠块的键缩进
    list_indent = None    # predicates/expected_changes 列表块的键缩进
    lines = text.splitlines()
    nonblank = [i for i, l in enumerate(lines) if l.strip() and not l.lstrip().startswith("#")]
    for idx, raw in enumerate(lines):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent + 1]:
            raise YamlMalformed("tab 缩进")
        if folded_indent is not None:
            if indent > folded_indent:
                continue  # 折叠块内容，忽略
            folded_indent = None
        stripped = raw.strip()
        if stripped.startswith("- ") or stripped == "-":
            body = stripped[2:].strip()
            if list_indent is not None and indent > list_indent:
                # 谓词块内条目：- <ID>: <text> 取自定义 id；- <text> 按序编 P<n>（§2.2）
                counter += 1
                m = re.match(r"^([^:\s]+):[ \t]*(.*)$", body)
                if m and not body.startswith('"'):
                    pid, ptext = m.group(1), m.group(2).strip()
                    _check_value(ptext)
                    entries.append((pid, ptext))
                else:
                    _check_value(body)
                    entries.append((f"P{counter}", body))
            else:
                # 谓词块外的列表项：仅验子集文法，不取谓词
                if body.startswith('"'):
                    _check_value(body)
                elif ":" in body:
                    _check_value(body.split(":", 1)[1])
            continue
        m = re.match(r"^([^:\s]+):[ \t]*(.*)$", stripped)
        if not m:
            raise YamlMalformed(f"无法解析的键值: {stripped!r}")
        key, value = m.group(1), m.group(2).strip()
        if value == ">":
            folded_indent = indent
            continue
        if not value:
            # key: 后无值：须有更缩进的子块，否则畸形（§6.1 异常 YAML 形态三）
            nxt = next((lines[j] for j in nonblank if j > idx), None)
            nxt_indent = (len(nxt) - len(nxt.lstrip(" "))) if nxt is not None else -1
            if nxt is None or nxt_indent <= indent:
                raise YamlMalformed(f"键 {key} 后无值且无子块")
            if key in ("predicates", "expected_changes"):
                list_indent = indent
            continue
        _check_value(value)
        if list_indent is not None and indent <= list_indent:
            list_indent = None  # 缩进回到键级：谓词块结束
    return entries


def read_text_relaxed(path: Path):
    """读文件并按 UTF-8 解码；失败返回 None（§2.3 降级：畸形，不崩溃）。"""
    try:
        return path.read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


# --------------------------------------------------------------------------
# 锚定语料与判定（§3）
# --------------------------------------------------------------------------

def load_corpus(repo_root: Path):
    """tests/** ∪ quality/** 全部可解码为 UTF-8 的文本文件，POSIX 相对路径序。"""
    items = []
    for top in CORPUS_TOPS:
        base = repo_root / top
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                items.append((p.relative_to(repo_root).as_posix(), p.read_bytes().decode("utf-8")))
            except (UnicodeDecodeError, OSError):
                continue  # 不可解码/不可读 → 不入语料（保守）
    items.sort(key=lambda kv: kv[0])
    return items


def anchor_card(card_id: str, preds, corpus):
    """逐谓词返回 evidence（语料序首个 card_id×谓词 id 同文件共现文件；未锚定=None）。

    语料文件含 card_id（子串）才成为候选；候选文件整词 token 集只建一次，
    万条谓词卡仍 O(语料+谓词数)。
    """
    cands = []
    for rel, content in corpus:
        if card_id in content:
            cands.append((rel, content, frozenset(WORD_TOKEN_RE.findall(content))))
    evidences = []
    for pid, _text in preds:
        ev = None
        if re.fullmatch(r"[A-Za-z0-9_]+", pid):
            for rel, _content, toks in cands:
                if pid in toks:
                    ev = rel
                    break
        else:  # 自定义 id 含非单词字符 → 正则整词匹配
            pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(pid) + r"(?![A-Za-z0-9_])")
            for rel, content, _toks in cands:
                if pat.search(content):
                    ev = rel
                    break
        evidences.append(ev)
    return evidences


def grade_card(kind: str, malformed: bool, n: int, anchored: int, mentioned: bool):
    """§3 按序短路：结构性问题优先，宁保守不误高。"""
    if kind == "missing" or malformed or n == 0:
        return "D"
    if anchored == n:
        return "A"
    if anchored > 0:
        return "B"
    return "C" if mentioned else "D"


# --------------------------------------------------------------------------
# coverage-summary.json schema 校验（§4，可独立复用的校验函数）
# --------------------------------------------------------------------------

def validate_summary(rep):
    """校验 coverage-summary 结构；返回错误列表（空=合法）。防御式，不抛异常。"""
    errs = []

    def bad(msg):
        errs.append(msg)

    def exact_keys(obj, keys, where):
        if not isinstance(obj, dict):
            bad(f"{where}: 应为 object")
            return False
        miss = [k for k in keys if k not in obj]
        extra = [k for k in obj if k not in keys]
        if miss:
            bad(f"{where}: 缺键 {miss}")
        if extra:
            bad(f"{where}: 多键 {extra}")
        return not miss and not extra

    TOP = ("schema_version", "ir_id", "tool", "spec_root", "totals", "cards", "remediation")
    if not isinstance(rep, dict) or not exact_keys(rep, TOP, "顶层"):
        return errs or ["顶层: 应为 object"]
    if rep.get("schema_version") != SCHEMA_VERSION:
        bad(f"schema_version 应为 {SCHEMA_VERSION!r}")
    if rep.get("tool") != TOOL:
        bad(f"tool 应为 {TOOL!r}")
    if rep.get("spec_root") != SPEC_ROOT:
        bad(f"spec_root 应为 {SPEC_ROOT!r}")
    if not (rep.get("ir_id") is None or isinstance(rep["ir_id"], str)):
        bad("ir_id 应为 string|null")

    def find_ts_keys(obj, where):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and TS_KEY_RE.match(k):
                    bad(f"{where}: 时间戳键 {k}")
                find_ts_keys(v, where)
        elif isinstance(obj, list):
            for v in obj:
                find_ts_keys(v, where)

    find_ts_keys(rep, "顶层")

    T_KEYS = ("cards", "predicates_total", "predicates_anchored", "uncovered_total",
              "by_grade", "suite_grade")
    totals = rep.get("totals")
    if not isinstance(totals, dict) or not exact_keys(totals, T_KEYS, "totals"):
        return errs
    for k in T_KEYS[:4]:
        v = totals.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            bad(f"totals.{k} 应为 int>=0")

    cards = rep.get("cards")
    if not isinstance(cards, list):
        bad("cards 应为 array")
        return errs
    paths = []
    grade_count = {"A": 0, "B": 0, "C": 0, "D": 0}
    structural_d = 0
    preds_total = anchored_total = uncovered_sum = 0
    CARD_KEYS = ("card_id", "path", "kind", "grade", "predicates", "uncovered_count")
    PRED_KEYS = ("id", "text", "anchored", "evidence")
    for idx, c in enumerate(cards):
        where = f"cards[{idx}]"
        if not isinstance(c, dict) or not exact_keys(c, CARD_KEYS, where):
            continue
        cid, path, kind, grade = c.get("card_id"), c.get("path"), c.get("kind"), c.get("grade")
        if not isinstance(cid, str) or not cid:
            bad(f"{where}.card_id 应为非空 string")
        if not isinstance(path, str):
            bad(f"{where}.path 应为 string")
        else:
            paths.append(path)
            if "\\" in path or re.match(r"^[A-Za-z]:", path) or path.startswith("//"):
                bad(f"{where}.path 非法（盘符/UNC/反斜杠）: {path}")
            if ".." in path.split("/"):
                bad(f"{where}.path 含 .. 组件: {path}")
            if not (path == SPEC_ROOT or path.startswith(SPEC_ROOT + "/")):
                bad(f"{where}.path 不在 {SPEC_ROOT}/ 下: {path}")
        if kind not in ("md", "yaml", "missing"):
            bad(f"{where}.kind 枚举错: {kind!r}")
        if grade not in GRADE_ORDER:
            bad(f"{where}.grade 枚举错: {grade!r}")
        if kind == "missing" and isinstance(path, str) and not path.endswith("/"):
            bad(f"{where}: missing 卡 path 应以 / 结尾: {path}")
        preds = c.get("predicates")
        if not isinstance(preds, list):
            bad(f"{where}.predicates 应为 array")
            continue
        unc = 0
        for j, p in enumerate(preds):
            pj = f"{where}.predicates[{j}]"
            if not isinstance(p, dict) or not exact_keys(p, PRED_KEYS, pj):
                continue
            if not isinstance(p.get("id"), str) or not p["id"]:
                bad(f"{pj}.id 应为非空 string")
            if not isinstance(p.get("text"), str):
                bad(f"{pj}.text 应为 string")
            anchored = p.get("anchored")
            if not isinstance(anchored, bool):
                bad(f"{pj}.anchored 应为 bool")
            ev = p.get("evidence")
            if not isinstance(ev, (str, type(None))):
                bad(f"{pj}.evidence 应为 string|null")
            elif isinstance(anchored, bool):
                if anchored and not isinstance(ev, str):
                    bad(f"{pj}: anchored=true 则 evidence 须为 string")
                if not anchored and ev is not None:
                    bad(f"{pj}: anchored=false 则 evidence 须为 null")
            if anchored is False:
                unc += 1
        preds_total += len(preds)
        anchored_total += sum(1 for p in preds if isinstance(p, dict) and p.get("anchored") is True)
        uncovered_sum += unc
        if c.get("uncovered_count") != unc:
            bad(f"{where}.uncovered_count({c.get('uncovered_count')}) != 未锚定数({unc})")
        if grade in grade_count:
            grade_count[grade] += 1
        if grade == "D" and not preds:
            structural_d += 1
    if paths != sorted(paths):
        bad("cards 未按 path 码点序排序")

    bg = totals.get("by_grade")
    if isinstance(bg, dict) and not (set(bg) - {"A", "B", "C", "D"}) and set(bg) == {"A", "B", "C", "D"}:
        for k in "ABCD":
            if not isinstance(bg[k], int) or isinstance(bg[k], bool) or bg[k] < 0:
                bad(f"totals.by_grade.{k} 应为 int>=0")
        if sum(bg.values()) != totals.get("cards"):
            bad(f"sum(by_grade)({sum(bg.values())}) != totals.cards({totals.get('cards')})")
        for k in "ABCD":
            if bg[k] != grade_count[k]:
                bad(f"by_grade.{k}({bg[k]}) 与逐卡计数({grade_count[k]})不一致")
    else:
        bad("totals.by_grade 键集合应精确为 A|B|C|D")
    if totals.get("predicates_total") != preds_total:
        bad(f"totals.predicates_total({totals.get('predicates_total')}) != 逐卡合计({preds_total})")
    if totals.get("predicates_anchored") != anchored_total:
        bad(f"totals.predicates_anchored({totals.get('predicates_anchored')}) != 逐卡合计({anchored_total})")
    expected_unc = uncovered_sum + structural_d
    if totals.get("uncovered_total") != expected_unc:
        bad(f"totals.uncovered_total({totals.get('uncovered_total')}) != Σuncovered+结构性D({expected_unc})")
    worst = "A"
    for c in cards:
        g = c.get("grade") if isinstance(c, dict) else None
        if g in GRADE_ORDER and GRADE_ORDER[g] > GRADE_ORDER[worst]:
            worst = g
    if cards and totals.get("suite_grade") != worst:
        bad(f"suite_grade({totals.get('suite_grade')}) 应为全卡最差({worst})")
    if not cards and totals.get("suite_grade") != "A":
        bad("空集 suite_grade 应为 A（vacuous truth）")

    rem = rep.get("remediation")
    if not isinstance(rem, list):
        bad("remediation 应为 array")
        return errs
    ut = totals.get("uncovered_total")
    if isinstance(ut, int) and not isinstance(ut, bool):
        if len(rem) != ut:
            bad(f"remediation 完备律: len({len(rem)}) != uncovered_total({ut})")
        if bool(rem) != (ut > 0):
            bad("remediation 非空 ⟺ uncovered_total>0 破")
    keys = []
    for idx, r in enumerate(rem):
        if not isinstance(r, dict) or not exact_keys(
                r, ("card_id", "target", "suggestion"), f"remediation[{idx}]"):
            continue
        if not isinstance(r.get("card_id"), str):
            bad(f"remediation[{idx}].card_id 应为 string")
        if not isinstance(r.get("target"), str) or not r["target"]:
            bad(f"remediation[{idx}].target 应为非空 string")
        if not isinstance(r.get("suggestion"), str) or not r["suggestion"].strip():
            bad(f"remediation[{idx}].suggestion 应为非空 string")
        keys.append((r.get("card_id"), r.get("target")))
    if keys != sorted(keys):
        bad("remediation 未按 (card_id, target) 排序")
    return errs


# --------------------------------------------------------------------------
# 报告生成
# --------------------------------------------------------------------------

def extract_ir_id(spec_root: Path):
    """specs/**/intent.yml 按路径序首个的 ir_id；无则 null（§4）。"""
    for rel in sorted(iter_tree(spec_root)):
        if rel.split("/")[-1] != "intent.yml":
            continue
        text = read_text_relaxed(spec_root / rel)
        if text is None:
            continue
        for line in text.splitlines():
            m = re.match(r"^ir_id:[ \t]*[\"']?([^\"'\s]+)[\"']?[ \t]*$", line.strip())
            if m:
                return m.group(1)
    return None


def suggest_for(target: str, card_id: str, path: str, kind: str, malformed: bool) -> str:
    """确定性建议模板（含 card_id/target，不含时间；§4 完备律配套）。"""
    if target == "card":
        if kind == "missing":
            return (f"卡 {card_id} 缺失：{path} 存在但无 card.yml 或含验收谓词段的 md 卡，"
                    f"请补齐契约卡文件")
        if malformed:
            return (f"卡 {card_id} 畸形：{path} 解析失败（YAML 子集违例或 UTF-8 解码失败），"
                    f"请按 specs/IR-W30-001/spec-draft.md §2 修复卡文件文法")
        return (f"卡 {card_id} 无验收谓词：{path} 谓词段存在但零条目，"
                f"请补充可机器判定的验收谓词")
    return (f"卡 {card_id} 谓词 {target} 未被测试锚定：请在 tests/** 或 quality/** "
            f"任一文件中同时引用 {card_id} 与 {target}（同文件共现），或补充对应测试用例")


def build_report(repo_root: Path):
    spec_root = repo_root / SPEC_ROOT
    corpus = load_corpus(repo_root)
    md_rels, yaml_rels, missing_rels, malformed_md = discover_cards(spec_root)

    # (card_id, path, kind, entries, malformed)；entries=None 仅出现在非卡（不应发生）
    cards = []
    for rel in md_rels:
        parts = rel.split("/")
        text = read_text_relaxed(spec_root / rel)
        entries = extract_md_section(text) if text is not None else []
        cards.append((parts[-1][:-3], f"{SPEC_ROOT}/{rel}", "md",
                      [] if entries is None else [tuple(e) for e in entries],
                      text is None or rel in malformed_md))
    for rel in yaml_rels:
        parts = rel.split("/")
        card_id = parts[-2] if len(parts) >= 2 else parts[-1][:-4]  # specs/card.yml → card（§1）
        text = read_text_relaxed(spec_root / rel)
        if text is None:
            entries, bad = [], True
        else:
            try:
                entries, bad = parse_yaml_subset(text), False
            except YamlMalformed:
                entries, bad = [], True
        cards.append((card_id, f"{SPEC_ROOT}/{rel}", "yaml", entries, bad))
    for rel in missing_rels:
        card_id = rel[len(SPEC_ROOT) + 1:].strip("/").split("/")[0]
        cards.append((card_id, rel, "missing", [], False))

    out_cards = []
    remediation = []
    for card_id, path, kind, entries, malformed in cards:
        mentioned = any(card_id in content for _rel, content in corpus)
        evidences = anchor_card(card_id, entries, corpus) if entries else []
        anchored_n = sum(1 for ev in evidences if ev is not None)
        grade = grade_card(kind, malformed, len(entries), anchored_n, mentioned)
        pred_objs = [
            {"id": pid, "text": text, "anchored": ev is not None, "evidence": ev}
            for (pid, text), ev in zip(entries, evidences)
        ]
        out_cards.append({
            "card_id": card_id,
            "path": path,
            "kind": kind,
            "grade": grade,
            "predicates": pred_objs,
            "uncovered_count": len(pred_objs) - anchored_n,
        })
        if grade == "D" and not entries:
            remediation.append({
                "card_id": card_id, "target": "card",
                "suggestion": suggest_for("card", card_id, path, kind, malformed),
            })
        for p in pred_objs:
            if not p["anchored"]:
                remediation.append({
                    "card_id": card_id, "target": p["id"],
                    "suggestion": suggest_for(p["id"], card_id, path, kind, malformed),
                })

    out_cards.sort(key=lambda c: c["path"])
    remediation.sort(key=lambda r: (r["card_id"], r["target"]))
    by_grade = {g: sum(1 for c in out_cards if c["grade"] == g) for g in "ABCD"}
    suite_grade = "A"
    for c in out_cards:
        if GRADE_ORDER[c["grade"]] > GRADE_ORDER[suite_grade]:
            suite_grade = c["grade"]
    structural_d = sum(1 for c in out_cards if c["grade"] == "D" and not c["predicates"])
    return {
        "schema_version": SCHEMA_VERSION,
        "ir_id": extract_ir_id(spec_root),
        "tool": TOOL,
        "spec_root": SPEC_ROOT,
        "totals": {
            "cards": len(out_cards),
            "predicates_total": sum(len(c["predicates"]) for c in out_cards),
            "predicates_anchored": sum(1 for c in out_cards for p in c["predicates"] if p["anchored"]),
            "uncovered_total": sum(c["uncovered_count"] for c in out_cards) + structural_d,
            "by_grade": by_grade,
            "suite_grade": suite_grade,
        },
        "cards": out_cards,
        "remediation": remediation,
    }


def main() -> int:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass
    repo_root = Path(__file__).resolve().parent.parent
    spec_root = repo_root / SPEC_ROOT
    if not spec_root.is_dir():
        print(f"coverage-report: {SPEC_ROOT}/ 目录不存在（仓库根 {repo_root}）", file=sys.stderr)
        return 2
    report = build_report(repo_root)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with open(repo_root / OUTPUT_NAME, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    t = report["totals"]
    print(f"coverage-report: cards={t['cards']} predicates={t['predicates_total']}"
          f" anchored={t['predicates_anchored']} suite_grade={t['suite_grade']}"
          f" -> {OUTPUT_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
