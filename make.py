# -*- coding: utf-8 -*-
"""一条命令出书：抓取 → 结构化 → Typst 排版 → PDF。

用法：
    python make.py                      # 最新一期
    python make.py --issue 20           # 2026 年第 20 期（自动定位目录页）
    python make.py --year 2025 --issue 3
    python make.py --issue 20 --force   # 忽略已缓存的 JSON，重新抓取

产物：
    issue-YYYY-NN.json / img/YYYY-NN/   中间数据
    book-YYYY-NN.pdf                    成书（同时复制到 输出目录）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from paths import output_dir
OUT_DIR = output_dir()

TYPST_CANDIDATES = [
    shutil.which("typst") or "",
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\typst-x86_64-pc-windows-msvc\typst.exe",
]


def typst() -> str:
    for c in TYPST_CANDIDATES:
        if c and Path(c).exists():
            return c
    sys.exit("找不到 typst，可先 winget install --id Typst.Typst -e")


def run(cmd: list[str]) -> None:
    print("$", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        sys.exit("command failed: %s" % cmd[0])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--issue", type=int)
    ap.add_argument("--url", help="直接给目录页 URL")
    ap.add_argument("--force", action="store_true", help="忽略缓存，重新抓取")
    ap.add_argument("--out", help="PDF 输出目录（默认 ./output）")
    a = ap.parse_args()
    global OUT_DIR
    if a.out:
        OUT_DIR = output_dir(a.out)

    tag = ("%d-%02d" % (a.year, a.issue)) if (a.year and a.issue) else None
    if tag is None:                       # 未知期号时先探一次，拿到元数据再定文件名
        probe = ROOT / "issue.json"
        if a.force or not probe.exists():
            run([sys.executable, "extract.py", "--imgdir", "img"])
        meta = json.loads(probe.read_text(encoding="utf-8"))["issue"]
        tag = "%d-%02d" % (meta["year"], meta["no"])

    js = ROOT / ("issue-%s.json" % tag)
    if a.force or not js.exists():
        cmd = [sys.executable, "extract.py", "--imgdir", "img/%s" % tag,
               "--out", js.name]
        if a.year:
            cmd += ["--year", str(a.year)]
        if a.issue:
            cmd += ["--issue", str(a.issue)]
        if a.url:
            cmd += ["--url", a.url]
        run(cmd)

    typ = ROOT / ("book-%s.typ" % tag)
    pdf = ROOT / ("book-%s.pdf" % tag)
    run([sys.executable, "build2.py", js.name, typ.name])
    run([typst(), "compile", typ.name, pdf.name, "--font-path", "fonts"])

    meta = json.loads(js.read_text(encoding="utf-8"))["issue"]
    name = "求是%d年第%d期-精排版.pdf" % (meta["year"], meta["no"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, OUT_DIR / name)
    print("\n完成：%s" % (OUT_DIR / name))
    print("      %d 篇 / %d 幅图 / 元数据 %s" %
          (meta["n_articles"], meta.get("n_images", 0), meta["publish"]))


if __name__ == "__main__":
    main()
