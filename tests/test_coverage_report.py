# -*- coding: utf-8 -*-
"""IR-W30-001 coverage_report.py 单元测试（测试先行，w30 第三幕 Card C-W30-001）。

框架说明：Python 标准库 unittest——本机无 pytest；仓库既有 tests/ 框架是 vitest
（TypeScript，不适用于 Python 脚本）；quality/ 自测惯例即"零新依赖、标准库"。
unittest 用例可被 pytest 直接收集，将来引入 pytest 无需改动本文件。

运行方式（不依赖 PATH 上的 python，子进程一律用 sys.executable）：
    python tests/test_coverage_report.py
    python -m unittest tests.test_coverage_report -v

夹具映射与期望评级以 specs/IR-W30-001/spec-draft.md §6/§7 为唯一对照真源。
测试树（temp tree）= 夹具台：把 scripts/coverage_report.py 与夹具安置进临时仓，
子进程真实执行脚本，断言 rc / coverage-summary.json / schema 校验三层面。
"""
import hashlib
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "coverage_report.py"
FIX = REPO / "specs" / "IR-W30-001" / "suite" / "fixtures"
CORPUS_NAME = "tests/anchor-corpus.txt"

_IMPL = None


def impl():
    """加载被测脚本为模块（供 schema 校验函数等复用面直接调用）。"""
    global _IMPL
    if _IMPL is None:
        spec = importlib.util.spec_from_file_location("coverage_report_impl", SCRIPT)
        assert spec and spec.loader, f"被测脚本不存在：{SCRIPT}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _IMPL = mod
    return _IMPL


def fx(kind, name):
    return (FIX / kind / name).read_text(encoding="utf-8")


def five_card_spec():
    """§6.1 夹具台映射：5 夹具 → 测试树内安置路径。"""
    return {
        "specs/scheduler-card.md": fx("positive", "scheduler-card.md"),
        "specs/deploy-card.md": fx("positive", "deploy-card.md"),
        "specs/IR-SAMPLE-000/card.yml": fx("positive", "sample-card.yml"),
        "specs/IR-BROKEN-000/card.yml": fx("negative", "broken-card.yml"),
        "specs/no-predicates-card.md": fx("negative", "no-predicates-card.md"),
    }


def build_tree(spec_files, corpus=None):
    """组装临时测试树：<tmp>/repo/{scripts,specs,tests}；返回 repo 根 Path。"""
    root = Path(tempfile.mkdtemp(prefix="w30cov-")) / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, root / "scripts" / "coverage_report.py")
    (root / "tests").mkdir()
    (root / "specs").mkdir()  # specs/ 恒存在：空 specs/ 与缺 specs/ 是两个边界用例
    for rel, text in (corpus or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    for rel, content in spec_files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8", newline="\n")
    return root


def run_tool(root):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "coverage_report.py")],
        cwd=str(root), capture_output=True, env=env, timeout=120,
    )


def summary(root):
    return json.loads((root / "coverage-summary.json").read_text(encoding="utf-8"))


def card_of(rep, card_id):
    for c in rep["cards"]:
        if c["card_id"] == card_id:
            return c
    return None


def assert_schema_ok(testcase, rep):
    errs = impl().validate_summary(rep)
    testcase.assertEqual(errs, [], f"schema 校验失败：{errs}")


def independent_grade(card, corpus_items):
    """测试内独立重实现 §3 判定器（AC-2 交叉比对用），不调用实现代码路径。"""
    if card["kind"] == "missing" or not card["predicates"]:
        return "D"
    cid = card["card_id"]
    anchored = 0
    for p in card["predicates"]:
        pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(p["id"]) + r"(?![A-Za-z0-9_])")
        if any(cid in text and pat.search(text) for _, text in corpus_items):
            anchored += 1
    n = len(card["predicates"])
    if anchored == n:
        return "A"
    if 0 < anchored < n:
        return "B"
    if any(cid in text for _, text in corpus_items):
        return "C"
    return "D"


def corpus_items_of(root):
    """从测试树重算锚定语料（tests/** ∪ quality/** 文本，POSIX 路径序）。"""
    items = []
    for top in ("tests", "quality"):
        base = root / top
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                try:
                    items.append((p.relative_to(root).as_posix(), p.read_text(encoding="utf-8")))
                except (UnicodeDecodeError, OSError):
                    pass
    items.sort(key=lambda kv: kv[0])
    return items


def cross_check_grades(testcase, root):
    """AC-2：独立判定器与真实报告逐卡交叉比对（等级 + 逐谓词 anchored/evidence）。"""
    rep = summary(root)
    corpus = corpus_items_of(root)
    for c in rep["cards"]:
        testcase.assertEqual(
            c["grade"], independent_grade(c, corpus),
            f"交叉比对不一致：card={c['card_id']}",
        )
        for p in c["predicates"]:
            pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(p["id"]) + r"(?![A-Za-z0-9_])")
            first = next(
                (rp for rp, text in corpus if c["card_id"] in text and pat.search(text)),
                None,
            )
            testcase.assertEqual(p["anchored"], first is not None, f"anchored 不一致：{c['card_id']}/{p['id']}")
            testcase.assertEqual(p["evidence"], first, f"evidence 不一致：{c['card_id']}/{p['id']}")


class Differential(unittest.TestCase):
    """§6.1 差分矩阵 S0–S4 + 异常 YAML 三形态。"""

    def _run_five(self, corpus=None):
        root = build_tree(five_card_spec(), corpus)
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        cross_check_grades(self, root)
        return root, rep

    def test_s0_empty_corpus_all_structural(self):
        _, rep = self._run_five()
        self.assertEqual(card_of(rep, "IR-BROKEN-000")["grade"], "D")
        self.assertEqual(card_of(rep, "IR-BROKEN-000")["predicates"], [])
        self.assertEqual(card_of(rep, "IR-BROKEN-000")["kind"], "yaml")
        self.assertEqual(card_of(rep, "no-predicates-card")["grade"], "D")
        self.assertEqual(card_of(rep, "scheduler-card")["grade"], "D")
        self.assertEqual(card_of(rep, "deploy-card")["grade"], "D")
        self.assertEqual(card_of(rep, "IR-SAMPLE-000")["grade"], "D")
        self.assertEqual(rep["totals"]["cards"], 5)
        self.assertEqual(rep["totals"]["predicates_total"], 10)
        self.assertEqual(rep["totals"]["suite_grade"], "D")

    def test_s1_mention_only_scheduler_c(self):
        _, rep = self._run_five({"tests/anchor-corpus.txt": "regression: scheduler-card only mentioned.\n"})
        sched = card_of(rep, "scheduler-card")
        self.assertEqual(sched["grade"], "C")
        self.assertTrue(all(p["anchored"] is False and p["evidence"] is None for p in sched["predicates"]))
        self.assertEqual(card_of(rep, "deploy-card")["grade"], "D")
        self.assertEqual(card_of(rep, "IR-SAMPLE-000")["grade"], "D")
        self.assertGreater(len(rep["remediation"]), 0)

    def test_s2_partial_anchor_sample_b(self):
        _, rep = self._run_five(
            {CORPUS_NAME: "coverage for IR-SAMPLE-000 predicate P2 exists.\n"})
        sample = card_of(rep, "IR-SAMPLE-000")
        self.assertEqual(sample["kind"], "yaml")
        self.assertEqual(len(sample["predicates"]), 3)
        self.assertEqual(sample["grade"], "B")
        anchored = [p for p in sample["predicates"] if p["anchored"]]
        self.assertEqual([p["id"] for p in anchored], ["P2"])
        self.assertEqual(anchored[0]["evidence"], CORPUS_NAME)
        self.assertEqual(card_of(rep, "scheduler-card")["grade"], "D")

    def test_s3_full_anchor_deploy_a(self):
        _, rep = self._run_five(
            {CORPUS_NAME: "deploy-card P1 P2 P3 all anchored in one file.\n"})
        deploy = card_of(rep, "deploy-card")
        self.assertEqual(deploy["grade"], "A")
        self.assertTrue(all(p["anchored"] and p["evidence"] == CORPUS_NAME for p in deploy["predicates"]))
        self.assertNotIn("deploy-card", [r["card_id"] for r in rep["remediation"]])
        self.assertEqual(card_of(rep, "scheduler-card")["grade"], "D")

    def test_s4_malformed_variant_does_not_pollute(self):
        spec = five_card_spec()
        # 单维变更：合法 sample 副本删一个引号 → 畸形，置入独立 IR 目录
        mutated = fx("positive", "sample-card.yml").replace(
            "- P1: 示例谓词一——命令 rc=0", '- P1: "示例谓词一——命令 rc=0')
        spec["specs/IR-SAMPLE-BAD/card.yml"] = mutated
        root = build_tree(spec, {CORPUS_NAME: "coverage for IR-SAMPLE-000 predicate P2 exists.\n"})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        self.assertEqual(card_of(rep, "IR-SAMPLE-000")["grade"], "B")   # 合法版按 S2
        self.assertEqual(card_of(rep, "IR-SAMPLE-BAD")["grade"], "D")   # 畸形版 D
        self.assertEqual(card_of(rep, "IR-SAMPLE-BAD")["predicates"], [])
        self.assertEqual(card_of(rep, "scheduler-card")["grade"], "D")  # 他卡不受污染
        self.assertEqual(card_of(rep, "IR-BROKEN-000")["grade"], "D")
        cross_check_grades(self, root)

    def test_malformed_yaml_tab_indent(self):
        spec = five_card_spec()
        spec["specs/IR-TAB-001/card.yml"] = (
            "ir_id: IR-TAB-001\npredicates:\n\t- P1: tab 缩进条目\n")
        _, rep = self._run_spec(spec)
        self.assertEqual(card_of(rep, "IR-TAB-001")["grade"], "D")
        self.assertEqual(card_of(rep, "IR-TAB-001")["predicates"], [])
        self.assertEqual(card_of(rep, "IR-SAMPLE-000")["grade"], "D")  # 空语料基线不受污染

    def test_malformed_yaml_unclosed_bracket(self):
        spec = five_card_spec()
        spec["specs/IR-BRACKET-001/card.yml"] = (
            "ir_id: IR-BRACKET-001\npredicates:\n  - P1: [1, 2\n")
        _, rep = self._run_spec(spec)
        self.assertEqual(card_of(rep, "IR-BRACKET-001")["grade"], "D")

    def test_malformed_yaml_key_no_value_no_child(self):
        spec = five_card_spec()
        spec["specs/IR-EMPTYKEY-001/card.yml"] = (
            "ir_id: IR-EMPTYKEY-001\npredicates:\nnext: x\n")
        _, rep = self._run_spec(spec)
        self.assertEqual(card_of(rep, "IR-EMPTYKEY-001")["grade"], "D")

    def test_ir_id_first_intent_yml_by_path_order(self):
        # §4：ir_id 取 specs/**/intent.yml 按路径序首个（多 IR 目录时不得取反序）
        spec = dict(five_card_spec())
        spec["specs/IR-A-1/intent.yml"] = "ir_id: IR-A-1\n"
        spec["specs/IR-Z-9/intent.yml"] = "ir_id: IR-Z-9\n"
        _, rep = self._run_spec(spec)
        self.assertEqual(rep["ir_id"], "IR-A-1")

    def _run_spec(self, spec, corpus=None):
        root = build_tree(spec, corpus)
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        return root, rep


class Property(unittest.TestCase):
    """§6.2 属性：任意 specs/ 文件内容 → rc=0、schema 合法、不污染他卡。"""

    ROUNDS = 50

    def generators(self, rng):
        yield "random-bytes", bytes(rng.randrange(256) for _ in range(256))
        yield "empty-file", ""
        yield "long-single-line", "x" * 100000
        yield "crlf", "## 验收谓词\r\n1. pred-crlf-样例\r\n"
        yield "bom", "﻿## 验收谓词\n1. pred-bom-样例\n"
        yield "zero-width", "# 卡\n## 验收\u200b谓词\n1. pred-zwsp-样例\n"
        yield "mega-10k", "## 验收谓词\n" + "".join(
            f"{i}. 谓词{i}样例\n" for i in range(1, 10001))

    def test_any_content_never_crashes_and_isolates(self):
        rng = random.Random(20260910)
        gens = list(self.generators(rng))
        for i in range(self.ROUNDS):
            name, content = gens[i % len(gens)]
            if name == "random-bytes":
                content = bytes(rng.randrange(256) for _ in range(256))
            spec = five_card_spec()
            corpus = {}
            if name == "mega-10k":
                rel, card_id = "specs/mega-fuzz-card.md", "mega-fuzz-card"
                corpus[CORPUS_NAME] = "mega-fuzz-card anchors P5000 only.\n"
            elif i % 2 == 0:
                rel, card_id = f"specs/fuzz-{i}-card.md", f"fuzz-{i}-card"
            else:
                rel, card_id = "specs/IR-FUZZ/card.yml", "IR-FUZZ"
            spec[rel] = content
            root = build_tree(spec, corpus)
            with self.subTest(round=i, kind=name):
                proc = run_tool(root)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
                rep = summary(root)
                assert_schema_ok(self, rep)
                # 稳定卡不受污染（空语料基线 = D；mega 轮部分锚定基线 = B）
                self.assertEqual(card_of(rep, "scheduler-card")["grade"], "D")
                self.assertEqual(card_of(rep, "IR-SAMPLE-000")["grade"], "D")
                # 任意文件：要么被忽略要么有等级
                fuzz = card_of(rep, card_id)
                if fuzz is not None:
                    self.assertIn(fuzz["grade"], ("A", "B", "C", "D"))
                if name == "mega-10k" and fuzz is not None:
                    self.assertEqual(len(fuzz["predicates"]), 10000)
                    self.assertEqual(fuzz["grade"], "B")
            shutil.rmtree(root.parent, ignore_errors=True)

    def test_mega_card_partial_anchor_scales(self):
        mega = "## 验收谓词\n" + "".join(f"{i}. 谓词{i}样例\n" for i in range(1, 10001))
        root = build_tree(
            {"specs/mega-card.md": mega},
            {CORPUS_NAME: "mega-card anchors P5000 only.\n"})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        mega_card = card_of(rep, "mega-card")
        self.assertEqual(len(mega_card["predicates"]), 10000)
        self.assertEqual(mega_card["grade"], "B")
        anchored = [p for p in mega_card["predicates"] if p["anchored"]]
        self.assertEqual([p["id"] for p in anchored], ["P5000"])
        self.assertEqual(rep["totals"]["predicates_total"], 10000)
        self.assertEqual(rep["totals"]["predicates_anchored"], 1)
        shutil.rmtree(root.parent, ignore_errors=True)


class Boundary(unittest.TestCase):
    """§6.3 边界六用例。"""

    def test_empty_specs_empty_report(self):
        root = build_tree({})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        self.assertEqual(rep["cards"], [])
        self.assertEqual(rep["totals"]["cards"], 0)
        self.assertEqual(rep["totals"]["predicates_total"], 0)
        self.assertEqual(rep["totals"]["predicates_anchored"], 0)
        self.assertEqual(rep["totals"]["uncovered_total"], 0)
        self.assertEqual(rep["totals"]["suite_grade"], "A")
        self.assertEqual(rep["remediation"], [])
        self.assertIsNone(rep["ir_id"])

    def test_specs_missing_rc2_no_output(self):
        root = Path(tempfile.mkdtemp(prefix="w30cov-")) / "repo"
        (root / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, root / "scripts" / "coverage_report.py")
        (root / "coverage-summary.json").write_text('{"sentinel": true}', encoding="utf-8")
        before = (root / "coverage-summary.json").read_bytes()
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 2)
        stderr_lines = [l for l in proc.stderr.decode("utf-8", "replace").splitlines() if l.strip()]
        self.assertEqual(len(stderr_lines), 1, "stderr 应为一行错误")
        self.assertEqual((root / "coverage-summary.json").read_bytes(), before, "不得改写既有输出")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_long_filename_180(self):
        name = "L" * 180 + "-card.md"
        section = "## 验收谓词\n1. 长文件名样例谓词\n"
        root = build_tree({f"specs/{name}": section})
        created = (root / "specs" / name).exists()
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        if created:
            card = card_of(rep, name[:-3])
            self.assertIsNotNone(card)
            self.assertEqual(card["path"], f"specs/{name}")
        else:
            self.assertEqual([c for c in rep["cards"] if c["kind"] == "md"], [])
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_deep_path_and_no_missing_rule_below_level1(self):
        spec = {
            "specs/a/b/c/d/e/f/g/card.md": "## 验收谓词\n1. 深路径谓词\n",
        }
        root = build_tree(spec, {CORPUS_NAME: "card P1 deep anchored.\n"})
        (root / "specs" / "a" / "b" / "IR-NEST").mkdir(parents=True)   # 非一级 IR 目录
        (root / "specs" / "IR-TOP").mkdir()                            # 一级 IR 目录（缺卡）
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        deep = card_of(rep, "card")
        self.assertIsNotNone(deep)
        self.assertEqual(deep["path"], "specs/a/b/c/d/e/f/g/card.md")
        self.assertEqual(deep["grade"], "A")
        self.assertIsNone(card_of(rep, "IR-NEST"), "非一级 IR-* 目录不触发缺卡规则")
        top = card_of(rep, "IR-TOP")
        self.assertIsNotNone(top)
        self.assertEqual(top["kind"], "missing")
        self.assertEqual(top["grade"], "D")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_predicate_section_no_trailing_newline(self):
        root = build_tree({"specs/eof-card.md": "# 卡\n## 验收谓词\n1. 末尾无换行谓词"})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        card = card_of(rep, "eof-card")
        self.assertIsNotNone(card)
        self.assertEqual([p["id"] for p in card["predicates"]], ["P1"])
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_missing_card_first_level_ir_dir(self):
        root = build_tree({})
        (root / "specs" / "IR-MISS-1").mkdir()
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        miss = card_of(rep, "IR-MISS-1")
        self.assertIsNotNone(miss)
        self.assertEqual(miss["kind"], "missing")
        self.assertEqual(miss["grade"], "D")
        self.assertEqual(miss["path"], "specs/IR-MISS-1/")
        self.assertEqual(miss["predicates"], [])
        self.assertIn("card", [r["target"] for r in rep["remediation"] if r["card_id"] == "IR-MISS-1"])
        shutil.rmtree(root.parent, ignore_errors=True)


class State(unittest.TestCase):
    """§6.4 状态三用例 + P4 确定性（AC-4）。"""

    def _tree(self):
        return build_tree(five_card_spec(), {CORPUS_NAME: "deploy-card P1 P2 P3 anchored.\n"})

    def test_works_without_suite_dir(self):
        root = self._tree()
        self.assertFalse((root / "specs" / "IR-W30-001" / "suite").exists())
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(card_of(summary(root), "deploy-card")["grade"], "A")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_rerun_overwrites_deterministic_and_mtime_immune(self):
        root = self._tree()
        (root / "coverage-summary.json").write_text("stale", encoding="utf-8")
        p1 = run_tool(root)
        self.assertEqual(p1.returncode, 0, p1.stderr.decode("utf-8", "replace"))
        out = root / "coverage-summary.json"
        self.assertNotEqual(out.read_text(encoding="utf-8"), "stale", "旧输出应被覆盖")
        h1 = hashlib.sha256(out.read_bytes()).hexdigest()
        p2 = run_tool(root)
        self.assertEqual(p2.returncode, 0)
        h2 = hashlib.sha256(out.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "同树两跑 sha256 必须相等")
        target = root / "specs" / "deploy-card.md"
        os.utime(target, (target.stat().st_atime + 50, target.stat().st_mtime + 50))
        p3 = run_tool(root)
        self.assertEqual(p3.returncode, 0)
        h3 = hashlib.sha256(out.read_bytes()).hexdigest()
        self.assertEqual(h1, h3, "touch（仅 mtime 变）后输出必须不变")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_suite_subtree_never_a_card(self):
        spec = five_card_spec()
        spec["specs/IR-SAMPLE-000/suite/positive/sample-card.yml"] = fx("positive", "sample-card.yml")
        spec["specs/suite/nested.md"] = "## 验收谓词\n1. 夹具自指谓词\n"
        root = build_tree(spec)
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        for c in rep["cards"]:
            self.assertNotIn("suite", Path(c["path"]).parts, f"suite 泄漏为在役卡：{c['path']}")
        shutil.rmtree(root.parent, ignore_errors=True)


class Holdout(unittest.TestCase):
    """§8 holdout 三案例（答案层期望 D/D/A，判定只依赖 §3 规则）。"""

    def test_h1_delete_card_leaves_missing_d(self):
        spec = {"specs/IR-HOLD-001/card.yml":
                "ir_id: IR-HOLD-001\npredicates:\n  - P1: holdout 谓词一\n"}
        root = build_tree(spec)
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0)
        self.assertIsNotNone(card_of(summary(root), "IR-HOLD-001"))
        (root / "specs" / "IR-HOLD-001" / "card.yml").unlink()  # 删卡留目录
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        miss = card_of(rep, "IR-HOLD-001")
        self.assertEqual(miss["kind"], "missing")
        self.assertEqual(miss["grade"], "D")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_h2_broken_card_d_without_crash(self):
        root = build_tree({"specs/IR-BROKEN-000/card.yml": fx("negative", "broken-card.yml")})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        assert_schema_ok(self, rep)
        self.assertEqual(card_of(rep, "IR-BROKEN-000")["grade"], "D")
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_h3_empty_dir_empty_report_a(self):
        root = build_tree({})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        rep = summary(root)
        self.assertEqual(rep["cards"], [])
        self.assertEqual(rep["totals"]["suite_grade"], "A")
        shutil.rmtree(root.parent, ignore_errors=True)


class SchemaValidator(unittest.TestCase):
    """§4 schema 校验函数（可独立复用）——正例通过 + 逐项负例。"""

    def _base(self):
        return {
            "schema_version": "1.0",
            "ir_id": None,
            "tool": "coverage-report",
            "spec_root": "specs",
            "totals": {
                "cards": 1, "predicates_total": 1, "predicates_anchored": 0,
                "uncovered_total": 2,
                "by_grade": {"A": 0, "B": 0, "C": 0, "D": 1},
                "suite_grade": "D",
            },
            "cards": [{
                "card_id": "X", "path": "specs/X.md", "kind": "md", "grade": "D",
                "predicates": [{"id": "P1", "text": "t", "anchored": False, "evidence": None}],
                "uncovered_count": 1,
            }],
            "remediation": [
                {"card_id": "X", "target": "P1", "suggestion": "s1"},
                {"card_id": "X", "target": "card", "suggestion": "s2"},
            ],
        }

    def test_valid_report_passes(self):
        root = build_tree(five_card_spec(), {CORPUS_NAME: "deploy-card P1 P2 P3 anchored.\n"})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(impl().validate_summary(summary(root)), [])
        shutil.rmtree(root.parent, ignore_errors=True)

    def test_mutations_each_fail(self):
        def mut(fn):
            rep = self._base()
            fn(rep)
            return rep

        cases = {
            "缺顶层键": lambda r: r.pop("remediation"),
            "多顶层键": lambda r: r.update({"generated_at": "2026-09-10"}),
            "嵌套时间戳键": lambda r: r["totals"].update({"mtime": 1}),
            "schema_version 错": lambda r: r.update({"schema_version": "2.0"}),
            "tool 错": lambda r: r.update({"tool": "other"}),
            "spec_root 错": lambda r: r.update({"spec_root": "src"}),
            "ir_id 类型错": lambda r: r.update({"ir_id": 7}),
            "suite_grade 枚举错": lambda r: r["totals"].update({"suite_grade": "E"}),
            "by_grade 合计不等于 cards": lambda r: r["totals"]["by_grade"].update({"A": 1}),
            "by_grade 键集合错": lambda r: r["totals"]["by_grade"].pop("D"),
            "uncovered_total 恒等破": lambda r: r["totals"].update({"uncovered_total": 0}),
            "predicates_total 恒等破": lambda r: r["totals"].update({"predicates_total": 5}),
            "cards 未按 path 排序": lambda r: r["cards"].insert(0, dict(r["cards"][0], card_id="A", path="specs/A.md")),
            "path 反斜杠": lambda r: r["cards"][0].update({"path": "specs\\X.md"}),
            "path 穿越": lambda r: r["cards"][0].update({"path": "specs/../X.md"}),
            "path 盘符": lambda r: r["cards"][0].update({"path": "C:specs/X.md"}),
            "path 不在 specs 下": lambda r: r["cards"][0].update({"path": "src/X.md"}),
            "kind 枚举错": lambda r: r["cards"][0].update({"kind": "pdf"}),
            "grade 枚举错": lambda r: r["cards"][0].update({"grade": "F"}),
            "卡键集合错": lambda r: r["cards"][0].pop("uncovered_count"),
            "uncovered_count 错": lambda r: r["cards"][0].update({"uncovered_count": 0}),
            "anchored 与 evidence 矛盾": lambda r: r["cards"][0]["predicates"][0].update({"evidence": "tests/x.txt"}),
            "remediation 完备律破": lambda r: r["remediation"].pop(),
            "remediation 应空非空": lambda r: (r["remediation"].clear(), r["totals"].update({"uncovered_total": 0})),
            "suggestion 空": lambda r: r["remediation"][0].update({"suggestion": ""}),
            "remediation 未排序": lambda r: r["remediation"].reverse(),
        }
        for name, fn in cases.items():
            with self.subTest(case=name):
                errs = impl().validate_summary(mut(fn))
                self.assertTrue(errs, f"负例未被检出：{name}")

    def test_garbage_input_returns_errors_not_crash(self):
        for garbage in ({}, None, [], "x", {"schema_version": "1.0"}):
            with self.subTest(garbage=type(garbage).__name__):
                self.assertTrue(impl().validate_summary(garbage))


class Remediation(unittest.TestCase):
    """AC-3：补救建议完备律与确定性模板。"""

    def test_empty_corpus_remediation_complete(self):
        root = build_tree(five_card_spec())
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0)
        rep = summary(root)
        self.assertGreater(rep["totals"]["uncovered_total"], 0)
        self.assertEqual(len(rep["remediation"]), rep["totals"]["uncovered_total"])
        for r in rep["remediation"]:
            self.assertTrue(r["suggestion"].strip())
            self.assertIn(r["card_id"], r["suggestion"], "建议模板须含 card_id")
        # 逐 uncovered 谓词一条（target=id）+ 结构性 D 卡一条（target=card）
        targets = sorted((r["card_id"], r["target"]) for r in rep["remediation"])
        self.assertEqual(targets, sorted(set(targets)), "remediation 不得重复")

    def test_full_anchor_no_remediation_for_that_card(self):
        root = build_tree(five_card_spec(), {CORPUS_NAME: "deploy-card P1 P2 P3 anchored.\n"})
        proc = run_tool(root)
        self.assertEqual(proc.returncode, 0)
        rep = summary(root)
        self.assertNotIn("deploy-card", [r["card_id"] for r in rep["remediation"]])

    def test_suggestion_deterministic(self):
        spec = five_card_spec()
        root_a = build_tree(spec)
        root_b = build_tree(spec)
        self.assertEqual(run_tool(root_a).returncode, 0)
        self.assertEqual(run_tool(root_b).returncode, 0)
        self.assertEqual(summary(root_a)["remediation"], summary(root_b)["remediation"])
        for root in (root_a, root_b):
            shutil.rmtree(root.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
