"""Extract one issue of 《求是》 into a structured JSON for book typesetting.

Keeps inline emphasis (strong/em/sup), image positions, photo captions and
column labels -- things the original downloader's sanitiser throws away.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).parent
IMG = ROOT / "img"
IMG.mkdir(exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(UA)

TOC_URL = ""                # set by main()
IMGDIR = "img"              # per-issue image folder
from paths import find_repo   # 只用来定位上游仓库（期号发现）
JUNK_HINTS = ("zxcode", "weixin_share", "/n6/", "/n7/")


def get(url: str) -> tuple[BeautifulSoup, requests.Response]:
    r = S.get(url, timeout=40)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    time.sleep(0.3)
    return BeautifulSoup(r.text, "lxml"), r


def text_of(node: Tag) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000]+", " ", node.get_text(" ", strip=True)).strip()


# --------------------------------------------------------------------------
# rich-text runs
# --------------------------------------------------------------------------
def runs_of(node: Tag) -> list[dict]:
    out: list[dict] = []

    def add(text: str, b: bool, i: bool, k: bool):
        text = text.replace("\xa0", " ")
        text = re.sub(r"[\u2002\u2003]+", "\u3000", text)
        text = re.sub(r"[ \t]+", " ", text)
        if not text:
            return
        if out and out[-1]["b"] == b and out[-1]["i"] == i and out[-1]["k"] == k:
            out[-1]["x"] += text
        else:
            out.append({"x": text, "b": b, "i": i, "k": k})

    def walk(n, b=False, i=False, k=False):
        for ch in n.children:
            if isinstance(ch, NavigableString):
                add(str(ch), b, i, k)
                continue
            if not isinstance(ch, Tag):
                continue
            name = ch.name.lower()
            if name == "br":
                add("\n", b, i, k)
                continue
            if name in ("script", "style"):
                continue
            nb, ni, nk = b, i, k
            if name in ("strong", "b"):
                nb = True
            elif name in ("em", "i"):
                ni = True
            elif name == "sup":
                nk = True
            elif name == "sub":
                nk = True
            style = (ch.get("style") or "").replace(" ", "").lower()
            if "font-weight:bold" in style or "font-weight:700" in style:
                nb = True
            if "font-style:italic" in style:
                ni = True
            walk(ch, nb, ni, nk)

    walk(node)
    # tidy: strip leading/trailing spaces, drop empty runs
    while out and not out[0]["x"].strip():
        out.pop(0)
    while out and not out[-1]["x"].strip():
        out.pop()
    if out:
        out[0]["x"] = out[0]["x"].lstrip(" \u3000")
        out[-1]["x"] = out[-1]["x"].rstrip()
    return [r for r in out if r["x"]]


CAP_HINTS = ("摄影", "摄/", "新华社", "资料图", "资料照片", "图/", "图片来源", "编者注", "注：", "本刊记者")


def is_caption_node(p: Tag, txt: str) -> bool:
    if not txt or len(txt) > 400:
        return False
    style = (p.get("style") or "").replace(" ", "").lower()
    inner_styles = " ".join(
        (t.get("style") or "").replace(" ", "").lower() for t in p.find_all("span")
    )
    small = "font-size:1" in inner_styles or "font-size:1" in style
    colored = "color:#000080" in inner_styles or "color:#000080" in style
    kai = any(k in inner_styles for k in ("kaiti", "楷体", "fangsong", "仿宋"))
    hinted = any(h in txt for h in CAP_HINTS)
    if colored:
        return True
    if small and len(txt) < 200:
        return True
    if kai and len(txt) < 220 and (hinted or txt.endswith("摄") or "/" in txt[-6:]):
        return True
    if hinted and len(txt) < 90:
        return True
    return False


def clean_title(t: str) -> str:
    return re.sub(r"[\s※＊*]+$", "", t).strip()


# --------------------------------------------------------------------------
# article body -> blocks
# --------------------------------------------------------------------------
def parse_blocks(content: Tag, base_url: str, art_i: int, title: str, author: str,
                 img_count: list[int]) -> list[dict]:
    blocks: list[dict] = []
    pending_caption: dict | None = None

    def push(blk: dict):
        nonlocal pending_caption
        if blk["t"] == "p":
            txt = "".join(r["x"] for r in blk["runs"])
            if not txt.strip():
                return
            if is_caption_node_last[0] and pending_caption is None:
                pass
        blocks.append(blk)

    is_caption_node_last = [False]

    def handle_p(p: Tag):
        txt = text_of(p)
        imgs = p.find_all("img")
        if imgs:
            for im in imgs:
                src = im.get("src") or im.get("data-src") or ""
                if not src or any(h in src.lower() for h in JUNK_HINTS):
                    continue
                img_count[0] += 1
                local = f"{IMGDIR}/a{art_i:02d}_{img_count[0]}.jpg"
                blocks.append({"t": "img", "src": local, "url": urljoin(base_url, src)})
            rest = re.sub(r"\s+", "", txt)
            if rest and len(rest) < 120:
                blocks.append({"t": "cap", "runs": runs_of(p)})
            return

        if not txt:
            return

        # duplicated title / byline at the head of the body
        norm = clean_title(txt)
        if norm == clean_title(title) or (
            len(norm) <= len(title) + 8 and clean_title(title) in norm and len(norm) < 90
        ):
            return
        if author and (norm in (author, f"作者：{author}")
                       or re.sub(r"\s+", "", norm) == re.sub(r"\s+", "", author)):
            return
        if txt.startswith(("来源：《求是》", "作者：", "来源:")):
            return

        if is_caption_node(p, txt):
            if blocks and blocks[-1]["t"] in ("img", "cap"):
                blocks.append({"t": "cap", "runs": runs_of(p)})
                return

        runs = runs_of(p)
        if not runs:
            return
        # sub-headline: fully bold and short
        full = "".join(r["x"] for r in runs)
        bold_all = all(r["b"] for r in runs if r["x"].strip())
        if bold_all and len(full) < 60 and (len(full) > 1 or re.fullmatch("[一二三四五六七八九十]", full)):
            blocks.append({"t": "h", "runs": runs})
            return
        blocks.append({"t": "p", "runs": runs})

    def handle_table(tb: Tag):
        rows = []
        for tr in tb.find_all("tr"):
            cells = [re.sub(r"\s+", "", text_of(c)) for c in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        if rows:
            blocks.append({"t": "table", "rows": rows})

    def walk(node: Tag):
        for ch in node.children:
            if not isinstance(ch, Tag):
                continue
            n = ch.name.lower()
            if n in ("script", "style"):
                continue
            if n == "p":
                handle_p(ch)
            elif n == "table":
                handle_table(ch)
            elif n in ("h2", "h3", "h4"):
                txt = text_of(ch)
                if txt and len(txt) < 80:
                    blocks.append({"t": "h", "runs": runs_of(ch)})
            elif n == "blockquote":
                blocks.append({"t": "quote", "runs": runs_of(ch)})
            elif n == "img":
                src = ch.get("src") or ""
                if src and not any(h in src.lower() for h in JUNK_HINTS):
                    img_count[0] += 1
                    blocks.append({"t": "img", "src": f"{IMGDIR}/a{art_i:02d}_{img_count[0]}.jpg",
                                   "url": urljoin(base_url, src)})
            else:
                walk(ch)

    walk(content)
    return blocks


def download_image(url: str, local: str) -> tuple[int, int]:
    path = ROOT / local
    if not path.exists():
        r = S.get(url, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    with Image.open(io.BytesIO(path.read_bytes())) as im:
        w, h = im.size
    return w, h


# --------------------------------------------------------------------------
def resolve_issue(args):
    """Locate the TOC page for the requested issue. Returns (url, meta)."""
    if args.url:
        soup, _ = get(args.url)
        txt = soup.get_text(" ", strip=True)
        m = re.search(r"(\d{4})年第(\d+)期", txt)
        year, no = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        mm = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", txt)
        return args.url, {"year": year, "no": no, "publish": mm.group(0) if mm else ""}

    repo = find_repo(getattr(args, "repo", None))
    sys.path.insert(0, str(repo))
    from scraper import registry  # 上游 Qiushi-Downloader 的站点适配器（MIT）
    src = registry.get("qstheory")
    for year, yurl in sorted(src.list_year_pages(), reverse=True):
        if args.year and year != args.year:
            continue
        issues = sorted(src.list_issues(year, yurl), key=lambda i: i.issue_no)
        for iss in issues:
            if args.issue is not None and iss.issue_no != args.issue:
                continue
            if args.issue is None and iss is not issues[-1]:
                continue
            pub = iss.publish_dt.strftime("%Y-%m-%d %H:%M:%S") if iss.publish_dt else ""
            return iss.toc_url, {"year": year, "no": iss.issue_no, "publish": pub}
    raise SystemExit("找不到指定期号：%s" % (args.issue if args.issue else "最新"))


def main():
    ap = argparse.ArgumentParser(description="抓取《求是》某一期，输出结构化 issue.json")
    ap.add_argument("--year", type=int, help="年份，默认最新")
    ap.add_argument("--issue", type=int, help="期号，默认最新一期")
    ap.add_argument("--url", help="直接指定目录页 URL")
    ap.add_argument("--imgdir", default="img", help="图片子目录，默认 img")
    ap.add_argument("--out", default="issue.json", help="输出 JSON 文件名")
    ap.add_argument("--repo", help="Qiushi-Downloader 仓库路径（默认自动查找）")
    args = ap.parse_args()

    global TOC_URL, IMGDIR
    TOC_URL, meta = resolve_issue(args)
    IMGDIR = args.imgdir
    (ROOT / IMGDIR).mkdir(parents=True, exist_ok=True)
    print("TOC:", TOC_URL, "|", meta)

    soup, _ = get(TOC_URL)
    if not meta.get("publish"):
        _m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", soup.get_text(" ", strip=True))
        if _m:
            meta["publish"] = _m.group(0)
        print("publish:", meta["publish"])
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(TOC_URL, a["href"])
        t = text_of(a)
        if not t or len(t) < 2:
            continue
        if "qssyggw" in href or "网站声明" in t:
            continue
        if not re.search(r"/\d{8}/[0-9a-f]{32}/c\.html$", href):
            continue
        if t == "理论资源导航":
            continue
        if any(x[1] == href for x in links):
            continue
        links.append((t, href))

    print(f"articles in TOC: {len(links)}")
    articles = []
    for i, (toc_text, url) in enumerate(links, start=1):
        art_soup, _ = get(url)
        h1 = art_soup.find("h1")
        title = text_of(h1) if h1 else toc_text
        h2 = art_soup.select_one("h2")
        subtitle = text_of(h2) if h2 and text_of(h2) != title else ""
        author = ""
        for sp in art_soup.select("span.appellation"):
            t = text_of(sp)
            if t.startswith("作者"):
                author = re.sub(r"^作者[:：]\s*", "", t).strip()
        # many h1s carry the column label: "深度调研 | 脑机接口产业调查：……"
        column = ""
        m = re.match(r"^(.{2,10}?)\s*[|｜]\s*(.+)$", clean_title(title))
        if m:
            column, title = m.group(1).strip(), m.group(2).strip()
        if not column:
            m2 = re.match(r"^(.{2,10}?)\s*[|｜]\s*(.+)$", toc_text)
            if m2:
                column = m2.group(1).strip()

        content = art_soup.select_one("#detailContent")
        if content is None:
            for sel in ("#detail", ".text", "#content", ".content"):
                content = art_soup.select_one(sel)
                if content is not None:
                    break
        if content is None:
            print("  !! no content:", title)
            continue

        cnt = [0]
        blocks = parse_blocks(content, url, i, title, author, cnt)
        # drop leading sub-heads that merely repeat the column / title
        while blocks and blocks[0]["t"] == "h":
            first = "".join(r["x"] for r in blocks[0]["runs"]).strip()
            if first in (column, clean_title(title), author) and first:
                blocks.pop(0)
            else:
                break
        articles.append({
            "idx": i, "column": column, "title": clean_title(title),
            "subtitle": subtitle, "author": author, "url": url, "blocks": blocks,
        })
        print(f"  {i:02d} [{column or '-':<6}] {clean_title(title)[:34]:<36} "
              f"blocks={len(blocks):3d} chars={sum(len(''.join(r['x'] for r in b.get('runs',[]))) for b in blocks)}")

    # images: download and record sizes
    print("\ndownloading images ...")
    for art in articles:
        for b in art["blocks"]:
            if b["t"] == "img":
                try:
                    w, h = download_image(b["url"], b["src"])
                    b["w"], b["h"] = w, h
                except Exception as exc:  # noqa: BLE001
                    print("  img failed", b["url"], exc)
                    b["w"], b["h"] = 0, 0

    cover_url = ""
    for im in soup.find_all("img", src=True):
        cand = urljoin(TOC_URL, im["src"])
        if any(h in cand.lower() for h in JUNK_HINTS):
            continue
        cover_url = cand
        break
    cover_rel = IMGDIR + "/cover.jpg"
    download_image(cover_url, cover_rel)

    pub = meta.get("publish") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    year, no = meta.get("year") or 0, meta.get("no") or 0
    if not year:
        year = int(pub[:4])
    pub_day = "%d年%d月%d日" % (int(pub[:4]), int(pub[5:7]), int(pub[8:10]))
    n_img = sum(1 for a in articles for b in a["blocks"] if b["t"] == "img")
    data = {
        "issue": {"title": "%d年第%d期" % (year, no), "year": year, "no": no,
                  "publish": pub, "publish_day": pub_day,
                  "source": "www.qstheory.cn", "toc_url": TOC_URL,
                  "cover": cover_rel, "n_articles": len(articles), "n_images": n_img},
        "articles": articles,
    }
    (ROOT / args.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nsaved %s: %d articles, %d images" % (args.out, len(articles), n_img))


if __name__ == "__main__":
    main()
