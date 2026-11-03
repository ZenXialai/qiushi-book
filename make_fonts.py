"""Instantiate static weights from the installed Source Han Serif SC variable
font (Typst 0.15 does not drive the wght axis), and give them a unique family
name so they win over the installed VF (whose default instance is ExtraLight).
"""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from paths import font_vf
SRC = font_vf()
OUT = Path(__file__).parent / "fonts"
OUT.mkdir(exist_ok=True)

FAMILY = "Qiushi Serif"
WEIGHTS = [(400, "Regular", "Regular", False), (700, "Bold", "Bold", True)]

for wght, style, ps_style, bold in WEIGHTS:
    font = TTFont(SRC)
    inst = instantiateVariableFont(font, {"wght": wght}, updateFontNames=False)
    name = inst["name"]
    full = f"{FAMILY} {style}"
    ps = f"QiushiSerif-{ps_style}"
    for nid, val in [(1, FAMILY), (2, style), (3, f"{ps};{wght}"), (4, full),
                     (6, ps), (16, FAMILY), (17, style)]:
        for rec in list(name.names):
            if rec.nameID == nid:
                try:
                    name.setName(val, nid, rec.platformID, rec.platEncID, rec.langID)
                except Exception:
                    pass
    inst["OS/2"].usWeightClass = wght
    if bold:
        inst["OS/2"].fsSelection = (inst["OS/2"].fsSelection & ~0x40) | 0x20
        inst["head"].macStyle |= 0x01
    else:
        inst["OS/2"].fsSelection = (inst["OS/2"].fsSelection & ~0x20) | 0x40
        inst["head"].macStyle &= ~0x01
    out = OUT / f"QiushiSerif-{ps_style}.ttf"
    inst.save(out)
    print("wrote", out, out.stat().st_size // 1024 // 1024, "MB")
