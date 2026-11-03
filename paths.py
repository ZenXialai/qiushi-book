"""路径解析：上游仓库位置、输出目录。

只用到 XHSecurity/Qiushi-Downloader 的「期号发现」能力（列年份页、列期号页），
所以需要那份仓库在本机存在。查找顺序：
    1. 命令行/参数显式指定
    2. 环境变量 QIUSHI_REPO
    3. ./Qiushi-Downloader、./vendor/Qiushi-Downloader、../Qiushi-Downloader
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_repo(explicit: str | None = None) -> Path:
    cands: list[Path] = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get("QIUSHI_REPO"):
        cands.append(Path(os.environ["QIUSHI_REPO"]))
    cands += [
        ROOT / "Qiushi-Downloader",
        ROOT / "vendor" / "Qiushi-Downloader",
        ROOT.parent / "Qiushi-Downloader",
    ]
    for c in cands:
        if (c / "scraper.py").exists():
            return c.resolve()
    raise SystemExit(
        "找不到 Qiushi-Downloader 仓库（本项目只借用它的期号发现能力）。\n"
        "请克隆到本项目目录下：\n"
        "    git clone https://github.com/XHSecurity/Qiushi-Downloader "
        "vendor/Qiushi-Downloader\n"
        "或用环境变量指定：set QIUSHI_REPO=D:\\path\\to\\Qiushi-Downloader\n"
    )


def output_dir(explicit: str | None = None) -> Path:
    p = explicit or os.environ.get("QIUSHI_OUT") or (ROOT / "output")
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def font_vf() -> Path:
    """找一个思源宋体可变字体（VF）作为静态实例的来源。"""
    cands: list[Path] = []
    if os.environ.get("QIUSHI_VF"):
        cands.append(Path(os.environ["QIUSHI_VF"]))
    local = os.environ.get("LOCALAPPDATA")
    win = os.environ.get("WINDIR", r"C:\Windows")
    if local:
        cands.append(Path(local) / "Microsoft/Windows/Fonts/SourceHanSerifSC-VF.ttf")
        cands.append(Path(local) / "Microsoft/Windows/Fonts/SourceHanSerifCN-VF.ttf")
    cands += [
        Path(win) / "Fonts/NotoSerifSC-VF.ttf",
        Path(win) / "Fonts/SourceHanSerifSC-VF.ttf",
        Path("/usr/share/fonts/opentype/source-han-serif/SourceHanSerifSC-VF.otf"),
        Path("/System/Library/Fonts/SourceHanSerifSC-VF.ttc"),
    ]
    for c in cands:
        if c.exists():
            return c
    raise SystemExit(
        "找不到思源宋体可变字体（SourceHanSerif*VF）。\n"
        "请安装思源宋体，或用 QIUSHI_VF 指向 .ttf/.otf 文件。\n"
    )
