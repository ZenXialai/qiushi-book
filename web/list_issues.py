"""列出求是网可用的年份与期号（给网页版用），输出 JSON 到 stdout。

    python list_issues.py [--year 2026]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import find_repo  # noqa: E402

sys.path.insert(0, str(find_repo()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    a = ap.parse_args()

    from scraper import registry  # 仓库里的站点适配器

    src = registry.get("qstheory")
    years = [(int(y), u) for y, u in src.list_year_pages()]
    years.sort(reverse=True)
    if a.year:
        years = [y for y in years if y[0] == a.year]

    out = []
    for y, url in years:
        try:
            issues = src.list_issues(y, url)
        except Exception as exc:                      # 单年失败不影响其他年
            print("warn:", y, exc, file=sys.stderr)
            continue
        items = []
        for it in issues:
            pub = getattr(it, "publish_dt", None)
            items.append({
                "no": getattr(it, "issue_no", None),
                "name": getattr(it, "title", "") or "",
                "publish": pub.strftime("%Y-%m-%d %H:%M:%S") if pub else "",
                "url": getattr(it, "toc_url", "") or "",
            })
        items = [i for i in items if i["no"]]
        items.sort(key=lambda i: i["no"], reverse=True)
        out.append({"year": y, "issues": items})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
