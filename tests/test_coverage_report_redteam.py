# -*- coding: utf-8 -*-
"""IR-W30-001 红队夹具常驻回归（w30 修复波，Card C-W30-001）。

把红队 breached 两项（RT06 symlink 目录逃逸、RT20 谓词块外列表项混入）与 RT07
观察项（symlink 自指环别名）固化为常驻回归；规则依据 spec-draft.md §10 v1.1 erratum
（E1 符号链接一律跳过 / E2 谓词块键名单独封闭）。
证据（只读，不改）：CEO 工作区 reports/redteam-w30-sim/{summary.md,verdicts.jsonl}。

运行方式（与 test_coverage_report.py 同法）：
    python tests/test_coverage_report_redteam.py
    python -m unittest tests.test_coverage_report_redteam -v
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_coverage_report import (  # noqa: E402
    CORPUS_NAME,
    assert_schema_ok,
    build_tree,
    card_of,
    five_card_spec,
    run_tool,
    summary,
)


def _symlink(link: Path, target: Path, dir_: bool) -> bool:
    """建符号链接；无权限/不支持时返回 False（用例自行 skipTest）。"""
    try:
        os.symlink(str(target), str(link), target_is_directory=dir_)
        return True
    except (OSError, NotImplementedError):
        return False


class RedteamSymlink(unittest.TestCase):
    """RT06/RT07：specs/ 与语料两侧符号链接一律跳过；自指环不产生别名卡。"""

    def test_rt06_specs_dir_symlink_escape_not_reported(self):
        # 红队复现：specs/escape-dir → 仓外 vault/（含 secret-card.md）→ 不得入报告
        base = Path(tempfile.mkdtemp(prefix="w30rt-"))
        outside = base / "outside-repo" / "vault"
        outside.mkdir(parents=True)
        (outside / "secret-card.md").write_text("## 验收谓词\n1. 绝密谓词\n", encoding="utf-8")
        root = build_tree(five_card_spec())
        try:
            if not _symlink(root / "specs" / "escape-dir", outside, dir_=True):
                self.skipTest("本机无符号链接权限")
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            self.assertNotIn("secret-card", [c["card_id"] for c in rep["cards"]],
                             "仓外卡经目录符号链接入报告（RT06 breach）")
            self.assertNotIn("secret", (root / "coverage-summary.json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
            shutil.rmtree(base, ignore_errors=True)

    def test_rt06_specs_file_symlink_not_a_card(self):
        base = Path(tempfile.mkdtemp(prefix="w30rt-"))
        outside = base / "outside-repo"
        outside.mkdir(parents=True)
        (outside / "escape-card.md").write_text("## 验收谓词\n1. 逃逸谓词\n", encoding="utf-8")
        root = build_tree(five_card_spec())
        try:
            if not _symlink(root / "specs" / "escape-card.md", outside / "escape-card.md", dir_=False):
                self.skipTest("本机无符号链接权限")
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            self.assertNotIn("escape-card", [c["card_id"] for c in rep["cards"]],
                             "仓外卡经文件符号链接入报告")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
            shutil.rmtree(base, ignore_errors=True)

    def test_rt06_corpus_dir_symlink_no_leak(self):
        # 对称性：tests/ 侧目录符号链接同样不跟随，投毒语料不得抬高等级
        base = Path(tempfile.mkdtemp(prefix="w30rt-"))
        outside = base / "outside-repo" / "vault"
        outside.mkdir(parents=True)
        (outside / "poison-corpus.txt").write_text(
            "deploy-card P1 P2 P3 all anchored.\nsecret-card P1 anchored.\n", encoding="utf-8")
        root = build_tree(five_card_spec())
        try:
            if not _symlink(root / "tests" / "escape-corpus", outside, dir_=True):
                self.skipTest("本机无符号链接权限")
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            self.assertEqual(card_of(rep, "deploy-card")["grade"], "D",
                             "语料经目录符号链接泄漏（两侧不对称）")
            self.assertNotIn("secret", (root / "coverage-summary.json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
            shutil.rmtree(base, ignore_errors=True)

    def test_rt06_corpus_file_symlink_no_leak(self):
        # 对称性最强形态：tests/ 下文件符号链接直指仓外语料文件
        base = Path(tempfile.mkdtemp(prefix="w30rt-"))
        outside = base / "outside-repo"
        outside.mkdir(parents=True)
        (outside / "poison.txt").write_text("deploy-card P1 P2 P3 all anchored.\n", encoding="utf-8")
        root = build_tree(five_card_spec())
        try:
            if not _symlink(root / "tests" / "poison-file.txt", outside / "poison.txt", dir_=False):
                self.skipTest("本机无符号链接权限")
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            self.assertEqual(card_of(rep, "deploy-card")["grade"], "D",
                             "语料经文件符号链接泄漏")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
            shutil.rmtree(base, ignore_errors=True)

    def test_rt07_symlink_loop_no_alias_cards(self):
        # 红队观察项：specs/loop → specs 自指环。跳过后环自然消失：真卡在报、
        # 无别名重复卡（路径不含 loop）、rc=0 有界返回
        root = build_tree({"specs/real-card.md": "## 验收谓词\n1. 环测试谓词\n"})
        try:
            if not _symlink(root / "specs" / "loop", root / "specs", dir_=True):
                self.skipTest("本机无符号链接权限")
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            self.assertEqual([c["card_id"] for c in rep["cards"]], ["real-card"],
                             "自指环应被跳过：仅真卡在报，无别名重复卡")
            self.assertTrue(all("loop" not in c["path"] for c in rep["cards"]))
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)


class RedteamPredicateBlock(unittest.TestCase):
    """RT20：谓词块键名单独封闭——其它键（含空值键）复位列表延续，其列表项永不成为谓词。"""

    def test_rt20_stray_key_list_items_not_predicates(self):
        # 红队复现用例：predicates 后跟 other: 及 2 个列表项 → 应仅 P1；语料提 P2 不得虚高
        spec = five_card_spec()
        spec["specs/IR-STRAY-1/card.yml"] = (
            "ir_id: IR-STRAY-1\npredicates:\n  - P1: 真谓词\n"
            "other:\n  - 游离条目一\n  - 游离条目二\n")
        root = build_tree(spec, {CORPUS_NAME: "IR-STRAY-1 is mentioned with stray P2 token.\n"})
        try:
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            card = card_of(rep, "IR-STRAY-1")
            self.assertEqual([p["id"] for p in card["predicates"]], ["P1"],
                             "other: 键的列表项不得成为谓词（RT20 breach：n=3）")
            self.assertEqual(card["uncovered_count"], 1)
            self.assertEqual(card["grade"], "C",
                             "仅提及：P2 在语料中不再误抬等级（breach 时为 B）")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)

    def test_rt20_expected_changes_block_still_closed_by_notes(self):
        # 正则性 + 封闭性：expected_changes 仍是谓词块键；其后 notes: 不延续
        spec = five_card_spec()
        spec["specs/IR-EC-2/card.yml"] = (
            "ir_id: IR-EC-2\npredicates:\n  - P1: 真谓词\n"
            "expected_changes:\n  - EC1: 期望变化一\n"
            "notes:\n  - 笔记条目一\n")
        root = build_tree(spec, {CORPUS_NAME: "IR-EC-2 mentioned only.\n"})
        try:
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            card = card_of(rep, "IR-EC-2")
            self.assertEqual([p["id"] for p in card["predicates"]], ["P1", "EC1"],
                             "expected_changes 条目仍是谓词；notes 条目不得混入")
            self.assertEqual(card["grade"], "C")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)

    def test_rt20_stray_between_predicate_blocks_then_reopen(self):
        # 复位后可再开启：stray 键隔开后，expected_changes 块照常提取
        spec = five_card_spec()
        spec["specs/IR-STRAY-2/card.yml"] = (
            "ir_id: IR-STRAY-2\npredicates:\n  - P1: 第一条\n"
            "other:\n  - 游离条目\n"
            "expected_changes:\n  - EC1: 变化一条\n")
        root = build_tree(spec, {CORPUS_NAME: "IR-STRAY-2 mentioned only.\n"})
        try:
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            card = card_of(rep, "IR-STRAY-2")
            self.assertEqual([p["id"] for p in card["predicates"]], ["P1", "EC1"])
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)

    def test_rt20_nested_stray_key_inside_predicate_block(self):
        # 谓词块内嵌套其它空值键：其子块列表项同样不是谓词（键名单独封闭）
        spec = five_card_spec()
        spec["specs/IR-STRAY-3/card.yml"] = (
            "ir_id: IR-STRAY-3\npredicates:\n  - P1: 真谓词\n"
            "  nested:\n    - 嵌套游离项\n")
        root = build_tree(spec, {CORPUS_NAME: "IR-STRAY-3 mentioned only.\n"})
        try:
            proc = run_tool(root)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            rep = summary(root)
            assert_schema_ok(self, rep)
            card = card_of(rep, "IR-STRAY-3")
            self.assertEqual([p["id"] for p in card["predicates"]], ["P1"])
            self.assertEqual(card["grade"], "C")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
