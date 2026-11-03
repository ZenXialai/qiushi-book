# -*- coding: utf-8 -*-
"""Turn issue.json into a book-styled Typst document (v2)."""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_args = sys.argv[1:]
JSON_PATH = Path(_args[0]) if _args else ROOT / "issue.json"
OUT_PATH = Path(_args[1]) if len(_args) > 1 else ROOT / "book.typ"
ISSUE = json.loads(JSON_PATH.read_text(encoding="utf-8"))

# ---------- issue metadata (everything is derived, nothing hard-coded) ----------
_M = ISSUE["issue"]
YEAR, NO = int(_M["year"]), int(_M["no"])
_PUB = datetime.strptime(_M["publish"], "%Y-%m-%d %H:%M:%S")
TITLE_CN = "《求是》%d 年第 %d 期" % (YEAR, NO)
ISSUE_CN = "%d 年　第 %d 期" % (YEAR, NO)
DAY_CN = "%d 年 %d 月 %d 日" % (_PUB.year, _PUB.month, _PUB.day)
DOC_TITLE = "求是 %d年第%d期" % (YEAR, NO)
COVER = _M.get("cover", "img/cover.jpg")
_CN = "〇一二三四五六七八九"
CN_YEAR = "".join(_CN[int(c)] for c in str(YEAR))
_CN_M = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
CN_MONTH = _CN_M[_PUB.month] + "月"

PW, PH = 1152, 1536
ML, MR, MT, MB = 128, 128, 130, 128
BODY_W = PW - ML - MR        # 896
TEXT_H = PH - MT - MB        # 1278

FS = 25.5
LEAD = 1.00                  # extra leading in em (typst adds to natural line height)
SPACING = 0.75            # kept for reference (typst par.spacing replaces leading)
PARA_EXTRA = 0.0           # paragraph gap == line pitch (indent only)
MAXIMG_H = 690


def esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def q(s):
    return '"' + esc(s) + '"'


def runs_to_typst(runs):
    out = []
    for r in runs:
        for j, seg in enumerate(r["x"].split("\n")):
            if j:
                out.append("#linebreak()")
            if not seg:
                continue
            expr = q(seg)
            if r.get("b"):
                expr = "strong(" + expr + ")"
            if r.get("i"):
                expr = "emph(" + expr + ")"
            if r.get("k"):
                expr = "super(" + expr + ")"
            out.append("#" + expr)
    return "".join(out).strip()


def img_width(b, maxh=MAXIMG_H):
    w, h = b.get("w") or 0, b.get("h") or 0
    if w > 0 and h > 0:
        width = min(maxh * w / h, BODY_W)
        if width < 200:
            width = min(BODY_W, 520)
        return round(width, 1)
    return float(BODY_W)


def emit_body(blocks, float_from=0, maxh=MAXIMG_H, placement="bottom"):
    out = []
    i, n = 0, len(blocks)
    pos = 0                      # characters emitted so far in this article
    while i < n:
        b = blocks[i]
        t = b["t"]
        if t == "p":
            pos += sum(len(r["x"]) for r in b["runs"])
            out.append(runs_to_typst(b["runs"]) + "\n\n")
        elif t == "h":
            body = runs_to_typst(b["runs"])
            plain = "".join(r["x"] for r in b["runs"]).strip()
            if plain.endswith("：") and len(plain) <= 8:
                out.append("#block(above: 0.6em, below: 0.35em)[#text(weight: \"bold\")["
                           + body + "]]\n\n")
            elif re.fullmatch(r"[一二三四五六七八九十]{1,2}", plain):
                out.append("#v(26pt)\n#align(center)[#text(size: 26pt, weight: \"bold\")["
                           + body + "]]\n#v(18pt)\n\n")
            else:
                out.append("#heading(level: 2)[" + body + "]\n#v(38pt, weak: false)\n\n")
        elif t == "quote":
            out.append(
                "#block(inset: (left: 24pt, right: 8pt),"
                " stroke: (left: 2pt + accent), above: 1em, below: 1em)[\n"
                "  #text(size: %gpt, fill: luma(60))[%s]\n]\n\n" % (FS - 2, runs_to_typst(b["runs"]))
            )
        elif t == "img":
            cap = ""
            if i + 1 < n and blocks[i + 1]["t"] == "cap":
                cap = runs_to_typst(blocks[i + 1]["runs"])
                i += 1
            floating = pos >= float_from
            f = ["#figure(",
                 '  image("%s", width: %gpt),' % (b["src"], img_width(b, maxh)),
                 "  placement: %s, gap: 9pt, numbering: none," % (placement if floating else "none")]
            if cap:
                f.append("  caption: [#align(center)[")
                f.append("    #set par(leading: 14pt, first-line-indent: 0pt, justify: false, spacing: 0pt)")
                f.append('    #text(size: 16.5pt, font: kai, fill: luma(96))[%s]' % cap)
                f.append("  ]],")
            else:
                f.append("  caption: none,")
            f.append(")")
            if floating:
                out.append("\n".join(f) + "\n")
            else:
                out.append("#block(above: 16pt, below: 16pt, breakable: false)[\n"
                           + "\n".join(f) + "\n]\n")
        elif t == "table":
            rows = b.get("rows") or []
            if rows:
                cells = []
                for row in rows:
                    cells.append("  " + ", ".join(
                        "[#text(size: %gpt)[%s]]" % (FS - 3, esc(c.replace("\n", " ")).strip())
                        for c in row
                    ) + ",")
                out.append(
                    "#v(18pt)\n#table(columns: %d, stroke: 0.5pt + luma(150), inset: 6pt,\n%s\n)\n#v(18pt)\n\n"
                    % (len(rows[0]), "\n".join(cells))
                )
        else:
            if b.get("runs"):
                out.append(runs_to_typst(b["runs"]) + "\n\n")
        i += 1
    return "".join(out)


def build():
    arts = ISSUE["articles"]
    nimg = sum(1 for a in arts for b in a["blocks"] if b["t"] == "img")

    cover_w = 596.0
    try:                                  # 按封面图真实比例定高，换一期也不会变形
        from PIL import Image as _I
        _cw, _ch = _I.open(ROOT / COVER).size
        cover_h = cover_w * _ch / _cw
    except Exception:
        cover_h = cover_w * 527 / 395
    ctop = 296.0

    L = []
    add = L.append

    # ================= 封面 =================
    add("// ================= 封面 =================")
    add("#page(margin: 0pt, header: none, footer: none)[")
    add('  #place(top + center, dy: 104pt)[#text(size: 20pt, tracking: 6pt, fill: luma(105))[中国共产党中央委员会主办]]')
    add('  #place(top + center, dy: %gpt)[#image("%s", width: %gpt)]' % (ctop, COVER, cover_w))
    add('  #place(top + center, dy: %gpt)[#text(size: 32pt, weight: "bold", tracking: 4pt)[《求是》]]' % (ctop + cover_h + 44))
    add('  #place(top + center, dy: %gpt)[#line(length: 208pt, stroke: 1pt + accent)]' % (ctop + cover_h + 98))
    add('  #place(top + center, dy: %gpt)[#text(size: 27pt, tracking: 7pt)[%s]]' % (ctop + cover_h + 124, ISSUE_CN))
    add('  #place(top + center, dy: %gpt)[#text(size: 19pt, fill: luma(115), tracking: 2pt)[%s]]' % (ctop + cover_h + 172, DAY_CN))
    add('  #place(bottom + center, dy: -92pt)[#text(size: 17pt, tracking: 3pt, fill: luma(120))[求是杂志社　主办]]')
    add("]")

    # ================= 扉页 =================
    add("")
    add("// ================= 扉页 =================")
    add("#page(margin: (x: 128pt, top: 0pt, bottom: 0pt), header: none, footer: none)[")
    add("  #v(258pt)")
    add('  #align(center)[#text(size: 104pt, weight: "bold", tracking: 20pt)[求是]]')
    add("  #v(36pt)")
    add('  #align(center)[#line(length: 216pt, stroke: 1.1pt + accent)]')
    add("  #v(34pt)")
    add('  #align(center)[#text(size: 26pt, tracking: 6pt)[%s]]' % ISSUE_CN)
    add("  #v(18pt)")
    add('  #align(center)[#text(size: 19pt, fill: luma(120), tracking: 2pt)[%s]]' % DAY_CN)
    add("  #v(226pt)")
    add('  #align(center)[#text(size: 17pt, fill: luma(108), font: kai)[主办　中国共产党中央委员会]]')
    add("  #v(8pt)")
    add('  #align(center)[#text(size: 17pt, fill: luma(108), font: kai)[出版　求是杂志社]]')
    add("  #v(8pt)")
    add('  #align(center)[#text(size: 17pt, fill: luma(108), font: kai)[来源　求是网　www.qstheory.cn]]')
    add("]")

    # ================= 编辑说明 =================
    add("")
    add("// ================= 编辑说明 =================")
    add("#page(margin: (x: 128pt, top: 132pt, bottom: 140pt), header: none, footer: none)[")
    add("  #v(132pt)")
    add('  #align(center)[#text(size: 24pt, weight: "bold", tracking: 6pt)[编 辑 说 明]]')
    add("  #v(20pt)")
    add('  #align(center)[#line(length: 118pt, stroke: 0.8pt + luma(175))]')
    add("  #v(52pt)")
    add("  #set par(first-line-indent: 2em, justify: true, leading: 19pt, spacing: 33pt)")
    add("  #set text(size: 21.5pt, fill: luma(45))")
    add("  本书为%s的数字阅读版，依照求是网《求是》目录页所刊发的 " % TITLE_CN
        + str(len(arts)) + " 篇文章编排，篇次与原刊一致，收图 " + str(nimg) + " 幅。")
    add("")
    add("  正文文字、图片与版面信息均取自求是网（www.qstheory.cn），检索及下载于 " + DAY_CN + " 完成。"
        "文章著作权归原作者及求是杂志社所有，本电子书仅供个人学习阅读，不作商业用途。")
    add("")
    add("  排印采用思源宋体（Source Han Serif SC），由 Typst 排版系统生成；"
        "版面按 3:4 比例的平板阅读屏设计，正文 %g 磅、首行缩进两字，篇名另页起排，"
        "页眉标篇名，图注用楷体随图。" % FS)
    add("]")

    # TOC 条目间距随篇数自适应，保证 20~26 篇都能排在一页内
    _n = len(arts)
    toc_gap = min(40.0, max(9.0, (1330.0 - 190.0) / max(1, _n - 1) - 17.0))

    # ================= 目录 =================
    add("")
    add("// ================= 目录 =================")
    add("#page(margin: (x: 122pt, top: 130pt, bottom: 120pt), header: none,")
    add('  footer: context align(center)[#text(size: 16pt, fill: luma(120))[#counter(page).display("i")]])[')
    add("  #set par(first-line-indent: 0pt, justify: false, leading: 9pt, spacing: 0pt)")
    add('  #text(size: 27pt, weight: "bold", tracking: 8pt)[目　录]')
    add("  #v(6pt)")
    add("  #line(length: 100%, stroke: 1.1pt + accent)")
    add("  #v(30pt)")
    add("  #context {")
    add("    let items = query(<art>)")
    add("    for it in items {")
    add("      let d = it.value")
    add("      let pg = counter(page).at(it.location()).first()")
    add("      link(it.location())[#grid(columns: (30pt, auto, 1fr, 40pt), column-gutter: 8pt,")
    add("        align: (left, left, bottom, right))[")
    add('        #text(size: 17pt, fill: luma(155))[#d.idx]')
    add("      ][")
    add('        #if d.column != "" [#text(size: 13.5pt, fill: accent, tracking: 2pt)[#d.column] #h(10pt)]')
    add("        #text(size: 20.5pt)[#d.title]")
    add("      ][")
    add('        #text(size: 12pt, fill: luma(165))[#repeat([·])]')
    add("      ][")
    add('        #text(size: 18pt, fill: luma(90))[#pg]')
    add("      ]]")
    add("      v(%gpt)" % toc_gap)
    add("    }")
    add("  }")
    add("]")

    # ================= 正文 =================
    add("")
    add("// ================= 正文 =================")
    add("#counter(page).update(1)")
    add("")
    add("  #set par(first-line-indent: (amount: 2em, all: true), justify: true,")
    add("    leading: %gem, spacing: %gpt)" % (LEAD, LEAD * FS + PARA_EXTRA))

    for a in arts:
        title = a["title"].strip()
        column = (a.get("column") or "").strip()
        author = (a.get("author") or "").strip()
        idx = "%02d" % a["idx"]

        add("")
        add("#page(margin: (x: %gpt, top: %gpt, bottom: %gpt)," % (ML, MT, MB))
        add('  footer: context align(center)[#text(size: 16pt, fill: luma(105))[#counter(page).display("1")]],')
        add("  header: [")
        add('  #set text(size: 13pt, fill: luma(125))')
        add("  #grid(columns: (1fr, 1fr), align: (left, right))[%s][%s]" % (TITLE_CN, esc(title)))
        add("  #v(4pt)")
        add("  #line(length: 100%, stroke: 0.45pt + luma(185))")
        add("])[")
        add("  #metadata((idx: %s, title: %s, column: %s, author: %s)) <art>"
            % (q(idx), q(title), q(column), q(author)))
        add("  #place(top + left, hide[#heading(level: 1, outlined: true)[%s]])" % esc(title))
        if column:
            add('  #align(center)[#text(size: 16.5pt, weight: "bold", fill: accent, tracking: 5pt)[%s]]'
                % esc(column))
            add("  #v(24pt)")
        add("  #align(center)[#par(leading: 24pt)[#text(size: 36pt, weight: \"bold\")[%s]]]" % esc(title))
        if author:
            add("  #v(15pt)")
            add('  #align(center)[#text(size: 19.5pt, font: kai, fill: luma(78))[%s]]' % esc(author))
        add("  #v(16pt)")
        add("  #align(center)[#line(length: 46pt, stroke: 0.9pt + accent)]")
        add("  #v(28pt)")
        nchar = sum(len(r["x"]) for bl in a["blocks"] for r in bl.get("runs", []))
        nimg = sum(1 for bl in a["blocks"] if bl["t"] == "img")
        single = nimg == 1 and nchar < 300
        body_txt = emit_body(a["blocks"],
                             maxh=(1000 if single else MAXIMG_H),
                             placement=("none" if single else "bottom"))
        for line in body_txt.split("\n"):
            add(("  " + line) if line.strip() else "")
        add("]")

    # 版权尾页
    add("")
    add("#page(margin: (x: %gpt, top: %gpt, bottom: %gpt), header: none, footer: none)[" % (ML, MT, MB))
    add("  #v(830pt)")
    add("  #align(center)[#line(length: 46pt, stroke: 0.9pt + accent)]")
    add("  #v(20pt)")
    add('  #align(center)[#text(size: 16.5pt, fill: luma(115), font: kai)[%s]]' % TITLE_CN)
    add("  #v(8pt)")
    add('  #align(center)[#text(size: 15pt, fill: luma(140), font: kai)[求是杂志社出版　·　%s年%s排印]]' % (CN_YEAR, CN_MONTH))
    add("]")

    head = [
        "// " + TITLE_CN + " —— Typst 书籍排版",
        '#let accent = rgb("#a8191c")',
        '#let kai = "KaiTi"',
        "",
        '#set document(title: "%s", author: "求是杂志社")' % DOC_TITLE,
        "#set page(width: %gpt, height: %gpt, fill: white)" % (PW, PH),
        '#set text(font: "Qiushi Serif", size: %gpt, lang: "zh", region: "cn",' % FS,
        '  hyphenate: false, fill: rgb("#141414"))',
        "#set par(justify: true, leading: %gem, first-line-indent: (amount: 2em, all: true))" % LEAD,
        "",
        "// ---------- 标题：l1 只作书签，l2 为小标题 ----------",
        "#show heading.where(level: 1): it => hide(it)",
        "#show heading.where(level: 2): it => block(above: 1.9em, below: 0em, sticky: true)[",
        "  #set par(first-line-indent: 0pt, leading: 0.5em)",
        '  #text(size: 26.5pt, weight: "bold")[#it.body]',
        "]",
        "",
    ]

    typ = "\n".join(head) + "\n".join(L) + "\n"
    OUT_PATH.write_text(typ, encoding="utf-8")
    print("wrote", OUT_PATH.name, len(typ), "bytes")


if __name__ == "__main__":
    build()
