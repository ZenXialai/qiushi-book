# 第三方声明 / Third-Party Notices

本项目（qiushi-book）自身代码以 MIT 许可发布，见 [LICENSE](LICENSE)。
但它**运行时依赖**下面这些第三方组件，各自的许可与义务如下。

---

## 1. XHSecurity/Qiushi-Downloader（必需，未随本项目分发）

- 仓库：https://github.com/XHSecurity/Qiushi-Downloader
- 许可：MIT（文件末尾附有一段关于内容版权的说明，因此 GitHub 识别为 "Other / NOASSERTION"）
- 版权：Copyright (c) 2026 求是刊读下载器 作者

### 用到了什么

只用到它的**「期号发现」**能力：给定年份，列出该年的期号与每期目录页 URL。

| 本项目文件 | 调用 |
|---|---|
| `extract.py` | `from scraper import registry` → `registry.get("qstheory")` → `list_year_pages()` / `list_issues()` |
| `web/list_issues.py` | 同上，为网页版下拉框提供年份/期号列表 |

正文抓取、段落/图注/小标题结构化、Typst 排版、网页服务**均为本项目自行实现**，不含上游代码。

### 你的义务

本项目**不复制也不分发**上游代码，只通过 `sys.path` 导入你本机克隆的那份仓库。
因此 MIT 的署名义务由你（克隆者）在本地使用时自然满足。为免争议，仍在此完整附上其许可文本：

```
MIT License

Copyright (c) 2026 求是刊读下载器 作者

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. 思源宋体 / Source Han Serif SC（字体，未随本项目分发）

- 许可：SIL Open Font License 1.1
- 版权：Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'

本项目**不包含字体文件**。`make_fonts.py` 只是在你本机已安装的思源宋体可变字体
（`SourceHanSerifSC-VF.ttf`）基础上，用 fontTools 生成两份静态字重实例
（Regular / Bold），放在本地 `fonts/` 目录供 Typst 使用——该目录已在 `.gitignore` 中。

OFL 要点：允许自由使用、修改、再分发（含嵌入文档），但**修改后的字体若对外分发，
不得继续使用 "Source" 这个保留字体名**。本项目生成的实例已改名为 `Qiushi Serif`
（正是为了避开保留名），本地自用不涉及分发义务。

---

## 3. Typst（排版引擎，外部程序，未随本项目分发）

- 许可：Apache License 2.0
- https://github.com/typst/typst

本项目通过命令行调用本机安装的 `typst`，不分发其二进制。

---

## 4. Python 依赖（未随本项目分发）

| 包 | 许可 | 用途 |
|---|---|---|
| requests | Apache-2.0 | HTTP |
| beautifulsoup4 | MIT | HTML 解析 |
| lxml | BSD-3-Clause | HTML 解析后端 |
| Pillow | HPND | 图片尺寸 |
| fonttools | MIT | 可变字体实例化 |
| brotli | MIT | fonttools 依赖（woff2） |
| pymupdf（可选） | AGPL-3.0 | 仅用于本地校验页数/字体，可用别的方式替代 |

注意 `pymupdf` 是 **AGPL-3.0**：只在本地自检脚本里用，不参与分发；
如果你要把它嵌进对外提供的服务，请自行评估 AGPL 的传染性，或改用 `pypdf`。

---

## 5. 内容版权（重要）

本项目**只提供工具**，不包含《求是》任何一期的文章正文、图片或成书 PDF。

- 抓取到的文章、图片版权归**求是杂志社 / 求是网**所有；
- 生成的 PDF 仅供**个人学习、研究、离线阅读**，不得再分发、不得商用；
- 请遵守目标站点的 robots.txt 与服务条款，控制抓取频率；
- 本项目与求是杂志社、求是网**无任何隶属或授权关系**，非官方工具。
