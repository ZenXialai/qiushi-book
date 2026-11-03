"""《求是》PDF 生成器 —— 本地网页版（只用标准库，双击 start.bat 即可）。

    python app.py [--port 8720] [--no-open]

流程：列期号 → 抓取(extract.py) → 排版(build2.py + typst) → 复制到输出目录。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))    # 仓库根目录（paths.py 在这里）
from paths import output_dir  # noqa: E402
BOOK = BASE.parent
OUT_DIR = output_dir()
PY = sys.executable
UI = BASE / "index.html"

TYPST_CANDIDATES = [
    shutil.which("typst") or "",
    r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages"
    r"\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\typst-x86_64-pc-windows-msvc\typst.exe",
]

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# --------------------------------------------------------------------------
# 环境检查
# --------------------------------------------------------------------------
def find_typst() -> str:
    for c in TYPST_CANDIDATES:
        if c and Path(c).exists():
            return c
    return ""


def env_status() -> dict:
    typst = find_typst()
    fonts = [BOOK / "fonts" / "QiushiSerif-Regular.ttf",
             BOOK / "fonts" / "QiushiSerif-Bold.ttf"]
    return {
        "typst": typst,
        "fonts_ok": all(f.exists() for f in fonts),
        "out_dir": str(OUT_DIR),
        "missing": [x for x in (["typst"] if not typst else [])
                    + ([] if all(f.exists() for f in fonts) else ["字体"]) if x],
    }


# --------------------------------------------------------------------------
# 任务
# --------------------------------------------------------------------------
class Job:
    def __init__(self, year: int, issue_no: int):
        self.id = uuid.uuid4().hex[:12]
        self.year = year
        self.no = issue_no
        self.state = "running"          # running | done | error | cancelled
        self.stage = "准备"
        self.pct = 0.0
        self.log: list[str] = []
        self.pdf: Path | None = None
        self.name = ""
        self.pages = 0
        self.size = 0
        self.error = ""
        self.proc: subprocess.Popen | None = None
        self.t0 = time.time()
        self.lock = threading.Lock()

    def add(self, line: str) -> None:
        line = line.rstrip()
        with self.lock:
            self.log.append(line)
            if len(self.log) > 500:
                del self.log[:100]

    def snap(self) -> dict:
        with self.lock:
            return {
                "id": self.id, "state": self.state, "stage": self.stage,
                "pct": round(self.pct, 1), "log": self.log[-60:],
                "name": self.name, "pages": self.pages, "size": self.size,
                "error": self.error, "elapsed": round(time.time() - self.t0, 1),
                "has_file": bool(self.pdf and self.pdf.exists()),
            }


JOBS: dict[str, Job] = {}


def run_stream(job: Job, cmd: list[str], stage: str, base_pct: float, span: float,
               weight_of=None) -> int:
    """跑子进程并把 stdout 实时写进日志，按需更新进度。"""
    job.stage = stage
    job.pct = max(job.pct, base_pct)
    job.add("$ " + " ".join(cmd))
    job.proc = subprocess.Popen(
        cmd, cwd=str(BOOK), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    for line in job.proc.stdout:            # type: ignore[union-attr]
        job.add(line)
        if weight_of:
            frac = weight_of(line)
            if frac is not None:
                job.pct = base_pct + span * min(1.0, max(0.0, frac))
    code = job.proc.wait()
    job.proc = None
    return code


def run_job(job: Job) -> None:
    try:
        if job.state == "cancelled":
            return
        tag = "%d-%02d" % (job.year, job.no)
        js = BOOK / ("issue-%s.json" % tag)
        typ = BOOK / ("book-%s.typ" % tag)
        pdf = BOOK / ("book-%s.pdf" % tag)

        total = {"n": 0}

        def wt(line: str):
            m = re.match(r"\s*articles in TOC:\s*(\d+)", line)
            if m:
                total["n"] = int(m.group(1))
                return 0.02
            m = re.match(r"\s*(\d+)\s*\[", line)
            if m and total["n"]:
                return int(m.group(1)) / total["n"]
            if line.startswith("downloading images"):
                return 0.96
            if line.startswith("saved "):
                return 1.0
            return None

        code = run_stream(job, [PY, "extract.py", "--year", str(job.year),
                                "--issue", str(job.no),
                                "--imgdir", "img/%s" % tag,
                                "--out", js.name],
                          "抓取正文与图片", 2, 68, wt)
        if job.state == "cancelled":
            return
        if code != 0 or not js.exists():
            raise RuntimeError("抓取失败（exit %d）。若站点改版，请把上面日志发我。" % code)

        if job.state == "cancelled":
            return
        code = run_stream(job, [PY, "build2.py", js.name, typ.name],
                          "排版（生成 Typst 源）", 72, 6)
        if code != 0:
            raise RuntimeError("排版脚本失败（exit %d）" % code)

        if job.state == "cancelled":
            return
        typst = find_typst()
        if not typst:
            raise RuntimeError("找不到 typst，无法编译 PDF")
        code = run_stream(job, [typst, "compile", typ.name, pdf.name,
                                "--font-path", "fonts"],
                          "编译 PDF", 78, 18)
        if code != 0 or not pdf.exists():
            raise RuntimeError("PDF 编译失败（exit %d）" % code)

        meta = json.loads(js.read_text(encoding="utf-8"))["issue"]
        job.stage = "归档"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        name = "求是%d年第%d期-精排版.pdf" % (meta["year"], meta["no"])
        dst = OUT_DIR / name
        for i in range(2, 20):                      # 同名文件被占用时自动改名
            try:
                shutil.copyfile(pdf, dst)
                break
            except PermissionError:
                dst = OUT_DIR / ("求是%d年第%d期-精排版（%d）.pdf" % (meta["year"], meta["no"], i))
        else:
            raise RuntimeError("输出文件被占用，请关闭正在查看的 PDF 后重试")

        job.pdf = dst
        job.name = dst.name
        job.size = dst.stat().st_size
        try:
            import pymupdf
            job.pages = pymupdf.open(dst).page_count
        except Exception:
            job.pages = 0
        job.pct = 100.0
        job.state = "done"
        job.stage = "完成"
        job.add("完成：%s（%d 页，%.1f MB）" % (dst, job.pages, job.size / 1048576))
    except Exception as exc:
        job.state = "error"
        job.error = str(exc)
        job.stage = "出错"
        job.add("!! " + str(exc))
        job.add(traceback.format_exc()[-1500:])


# --------------------------------------------------------------------------
# 期号列表
# --------------------------------------------------------------------------
CACHE = {"t": 0.0, "data": None}


def issues_payload(force: bool = False) -> dict:
    if not force and CACHE["data"] and time.time() - CACHE["t"] < 900:
        return {"ok": True, "years": CACHE["data"], "cached": True}
    try:
        r = subprocess.run([PY, str(BASE / "list_issues.py")], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180,
                           creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "")[-500:])
        data = json.loads(r.stdout.strip().splitlines()[-1])
        for yr in data:                       # 用目录页 URL 里的日期补上发布日期
            for it in yr["issues"]:
                m = re.search(r"/(\d{4})(\d{2})(\d{2})/", it.get("url", ""))
                if m and not it.get("publish"):
                    it["publish"] = "%s-%s-%s" % m.groups()
        CACHE.update(t=time.time(), data=data)
        return {"ok": True, "years": data, "cached": False}
    except Exception as exc:
        return {"ok": False, "error": "取期号列表失败：%s" % exc, "years": []}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "QiushiPDF/1.0"

    def log_message(self, fmt, *args):        # 控制台安静一点
        pass

    # ---- helpers
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path

        if p in ("/", "/index.html"):
            if not UI.exists():
                return self._send(500, b"index.html missing", "text/plain; charset=utf-8")
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")

        if p == "/api/health":
            return self._json({"ok": True, **env_status()})

        if p == "/api/issues":
            return self._json(issues_payload(force=q.get("force", ["0"])[0] == "1"))

        if p == "/api/job":
            job = JOBS.get((q.get("id") or [""])[0])
            if not job:
                return self._json({"ok": False, "error": "任务不存在"}, 404)
            return self._json({"ok": True, **job.snap()})

        if p == "/api/download":
            job = JOBS.get((q.get("id") or [""])[0])
            if not job or not job.pdf or not job.pdf.exists():
                return self._json({"ok": False, "error": "文件不存在"}, 404)
            data = job.pdf.read_bytes()
            fn = job.pdf.name
            from urllib.parse import quote
            return self._send(200, data, "application/pdf",
                              {"Content-Disposition":
                               "attachment; filename*=UTF-8''%s" % quote(fn)})

        return self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        d = self._body()

        if p == "/api/build":
            try:
                year = int(d.get("year") or 0)
                no = int(d.get("issue") or 0)
            except Exception:
                return self._json({"ok": False, "error": "期号参数不对"}, 400)
            if not (year > 2000 and 0 < no < 60):
                return self._json({"ok": False, "error": "请选择年份和期号"}, 400)
            for j in JOBS.values():
                if j.state == "running" and j.year == year and j.no == no:
                    return self._json({"ok": False,
                                       "error": "该期正在生成中，请等它完成"}, 409)
            if len(JOBS) > 60:                       # 只保留最近的记录
                for k in sorted(JOBS, key=lambda k: JOBS[k].t0)[:20]:
                    JOBS.pop(k, None)
            job = Job(year, no)
            JOBS[job.id] = job
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            return self._json({"ok": True, "id": job.id})

        if p == "/api/cancel":
            job = JOBS.get(d.get("id") or "")
            if not job:
                return self._json({"ok": False, "error": "任务不存在"}, 404)
            job.state = "cancelled"
            job.stage = "已取消"
            if job.proc:
                try:
                    job.proc.terminate()
                except Exception:
                    pass
            job.add("已取消")
            return self._json({"ok": True})

        if p == "/api/shutdown":
            self._json({"ok": True})
            def _bye():
                time.sleep(0.3)
                self.server.shutdown()      # 停止 serve_forever，主线程退出
                time.sleep(0.3)
                os._exit(0)                 # 兜底
            threading.Thread(target=_bye, daemon=True).start()
            return

        if p == "/api/openfolder":
            try:
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                os.startfile(str(OUT_DIR))     # type: ignore[attr-defined]
                return self._json({"ok": True})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)})

        return self._json({"ok": False, "error": "not found"}, 404)


def already_running(port: int = 8720) -> bool:
    """已有一个实例在跑就复用它，避免每次双击都多开一个服务。"""
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % port,
                                    timeout=1.5) as r:
            d = json.loads(r.read().decode("utf-8"))
        return bool(d.get("ok") and "out_dir" in d)
    except Exception:
        return False


def free_port(start: int) -> int:
    import socket
    for port in range(start, start + 40):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8720)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    if already_running(a.port):                 # 已经开着了：只把浏览器叫起来
        url0 = "http://127.0.0.1:%d/" % a.port
        print("Already running: %s" % url0)
        if not a.no_open:
            webbrowser.open(url0)
        raise SystemExit(3)

    st = env_status()
    if st["missing"]:
        print("!! missing: %s" % ", ".join(st["missing"]))

    port = free_port(a.port)
    url = "http://127.0.0.1:%d/" % port
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Qiushi PDF maker: %s" % url)
    print("Close this window (or press Ctrl+C) to stop the service.")
    if not a.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
