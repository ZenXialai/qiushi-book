# -*- coding: utf-8 -*-
"""冒烟测试：不需要网络、上游仓库、字体，就能发现"改名没改引用"这类问题。

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixture"

PY_FILES = ["build.py", "extract.py", "make.py", "make_fonts.py", "paths.py",
            "web/app.py", "web/list_issues.py"]
TYPST_CANDIDATES = [
    shutil.which("typst") or "",
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\typst-x86_64-pc-windows-msvc\typst.exe",
]


def typst() -> str | None:
    for c in TYPST_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


class RepoTest(unittest.TestCase):
    def test_syntax(self) -> None:
        """所有脚本都能编译（语法错误/缩进错误第一时间暴露）。"""
        for rel in PY_FILES:
            with self.subTest(file=rel):
                src = (ROOT / rel).read_text(encoding="utf-8")
                compile(src, rel, "exec")

    def test_script_references_exist(self) -> None:
        """代码里引用的 foo.py 必须真的存在（曾经把 build2.py 改名成 build.py 漏改）。"""
        pattern = re.compile(r'"([\w./-]+\.py)"')
        for rel in ("make.py", "web/app.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for name in sorted(set(pattern.findall(text))):
                with self.subTest(referenced_from=rel, target=name):
                    found = (ROOT / name).exists() or (ROOT / "web" / name).exists()
                    self.assertTrue(found, "%s 引用了不存在的 %s" % (rel, name))

    def test_start_bat_is_crlf_ascii(self) -> None:
        """批处理必须是 CRLF + 纯 ASCII，否则 cmd 解析会错乱（真实踩过的坑）。"""
        data = (ROOT / "web" / "start.bat").read_bytes()
        self.assertIn(b"\r\n", data)
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), "存在裸 LF")
        self.assertEqual([b for b in data if b > 127], [], "含非 ASCII 字节")

    def test_no_hardcoded_machine_paths(self) -> None:
        """不能把开发机路径写死，否则别人 clone 下来就跑不了。"""
        bad = ("D:\\\\Documents", "求是PDF", "C:\\\\Users\\\\Administrator")
        for rel in PY_FILES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for token in bad:
                with self.subTest(file=rel, token=token):
                    self.assertNotIn(token, text)

    def test_bat_crlf_in_git_attributes(self) -> None:
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.bat -text", attrs)


class BuildTest(unittest.TestCase):
    def test_build_fixture(self) -> None:
        """从 fixture 生成 Typst 文档，检查关键结构都在。"""
        tmp = Path(tempfile.mkdtemp(prefix="qiushi-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURE / "img", tmp / "img")
        out = tmp / "book.typ"
        r = subprocess.run([sys.executable, str(ROOT / "build.py"),
                            str(FIXTURE / "issue.json"), str(out)],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        typ = out.read_text(encoding="utf-8")
        for token in ("#set page(width:", "目录", "一篇带图片与引用的测试文章",
                      "深度调研", "#figure(", "caption:", "qiushi serif"):
            with self.subTest(token=token):
                self.assertIn(token.lower(), typ.lower())
        # 两篇文章 -> 两条一级书签
        self.assertEqual(typ.count("#heading(level: 1"), 2)

    def test_typst_compiles_if_available(self) -> None:
        """本机有 typst 时，顺带验证生成的 .typ 能被编译。"""
        exe = typst()
        if not exe:
            self.skipTest("没有 typst，跳过")
        tmp = Path(tempfile.mkdtemp(prefix="qiushi-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FIXTURE / "img", tmp / "img")
        subprocess.run([sys.executable, str(ROOT / "build.py"),
                        str(FIXTURE / "issue.json"), str(tmp / "book.typ")],
                       cwd=ROOT, check=True, capture_output=True)
        r = subprocess.run([exe, "compile", str(tmp / "book.typ"), str(tmp / "book.pdf")],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertTrue((tmp / "book.pdf").stat().st_size > 10000)


class PathsTest(unittest.TestCase):
    def test_output_dir_env(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="qiushi-out-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        env = dict(os.environ, QIUSHI_OUT=str(tmp / "books"))
        r = subprocess.run([sys.executable, "-c",
                            "import paths;print(paths.output_dir())"],
                           cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("books", r.stdout)

    def test_find_repo_message(self) -> None:
        """找不到上游仓库时，要给清楚的提示而不是抛栈。"""
        tmp = Path(tempfile.mkdtemp(prefix="qiushi-norepo-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        code = ("import paths;"
                "paths.ROOT = __import__('pathlib').Path(%r);"
                "print(paths.find_repo())" % str(tmp))
        env = {k: v for k, v in os.environ.items() if k != "QIUSHI_REPO"}
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Qiushi-Downloader", r.stderr + r.stdout)


class RepoContentTest(unittest.TestCase):
    def test_gitignore_covers_artifacts(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for token in ("img/", "output/", "issue*.json", "*.pdf", "fonts/"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_no_content_tracked(self) -> None:
        """仓库里不许出现文章、图片、成书 PDF、字体（docs/ 的 README 截图除外）。"""
        if not (ROOT / ".git").exists():
            self.skipTest("不是 git 仓库")
        r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8")
        if r.returncode != 0:
            self.skipTest("git 不可用")
        bad = []
        for line in r.stdout.splitlines():
            name = line.strip()
            if not name or name.startswith("docs/") or name.startswith("tests/fixture/"):
                continue
            if re.search(r"\.(pdf|jpe?g|png|ttf|otf)$", name) or name.startswith(("img/", "fonts/")):
                bad.append(name)
            if re.match(r"issue.*\.json$", Path(name).name):
                bad.append(name)
        self.assertEqual(bad, [], "仓库里不该有内容文件：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
