# 网页版

一个单页本地界面：选年份期号 → 开始生成 → 下载 PDF。

## 启动

- Windows：双击 `start.bat`
- 其它系统：`python app.py`（可加 `--port 9000 --no-open`）

浏览器访问 <http://127.0.0.1:8720/>。已在运行时再次启动不会多开，只会把浏览器打开。

## 关闭

页面底部「退出服务」，或关闭命令行窗口（`Ctrl + C`）。

## 端口被占用

`app.py` 会从 8720 起自动找一个空闲端口，并把实际地址打印在窗口里；也可以用 `--port` 指定。

## 依赖

`app.py` 只用 Python 标准库（`http.server`），不需要 Flask/FastAPI。
真正干活的是父目录的 `extract.py` / `build.py` 和本机的 `typst`。
找不到上游仓库时，用环境变量 `QIUSHI_REPO` 指定。
