# HTML 排名图片

今日/生涯水群榜与积分榜使用 Playwright Chromium 截图。趋势图和热力图继续使用原来的绘图库。截图直接在内存中转为 Base64，无需 HTML 服务器，也不再写入固定 PNG 文件。

## 部署

在运行机器人的虚拟环境内安装：

```bash
python -m pip install -r control/requirements.txt
python -m playwright install chromium
```

Linux 需要安装浏览器系统依赖（系统包安装可能需要管理员权限）：

```bash
python -m playwright install --with-deps chromium
```

字体仍然影响中文排版。Linux 建议安装 Noto CJK 字体，例如 Debian/Ubuntu 的 `fonts-noto-cjk`；macOS 使用苹方，Windows 使用微软雅黑。字体次序由 `res/ranking/ranking.css` 的 `font-family` 控制，不再读取 Matplotlib 的 `font` 配置。

新增 Playwright 后移除了旧的 `requests_html` 依赖，它间接依赖的 Pyppeteer 与 Playwright 的 `pyee` 版本要求冲突。原先唯一的 `HTMLSession` 调用只读取响应文本，现改为已有的 `requests.get`。已有环境中的旧 Pyppeteer 可以继续保留，但 `pip check` 可能报告它的历史冲突；需要时可卸载不再使用的 `requests-html`、`pyppeteer`。

项目启动后首次使用排名时启动浏览器，后续复用同一个实例。截图串行执行，每次使用独立浏览器上下文，完成后释放。机器人关闭时释放浏览器。Playwright 升级后重新执行浏览器安装命令。

## 样式与模板

- `res/ranking/ranking.html`：标题、表格结构、页脚。
- `res/ranking/ranking.css`：颜色、圆角、字体、行距及前三名样式。
- `function/ranking_render.py`：转义昵称、生成 HTML、替换 Emoji、截图。
- `application/classic_application.py`：机器人实际注册的 `RankingApplication` 命令入口，今日、生涯、本周、本月、本季度、本年水群榜及积分榜均调用共用 HTML 渲染器。`function/chat_record.py` 中也有同名兼容函数，修改时需同时核对注册入口。

模板使用 Python `string.Template`，占位符使用 `$title` 等形式。宽度固定为 880 CSS 像素，截图倍率 2，高度随行数及换行变化。长昵称完整换行；空数据生成“暂无排名数据”卡片。

昵称只作为转义后的文本进入模板，浏览器拦截所有外部请求。Twemoji 解析器识别完整 Emoji 序列，SVG 从本地 ZIP 读取，支持云朵、肤色、家庭组合和旗帜等。素材不包含的新 Emoji 会保留原始文本，显示效果取决于系统字体。

## Emoji 素材来源

Twemoji **17.0.3**，来自 https://github.com/jdecked/twemoji 。

- `twemoji.min.js`：来自 npm `@twemoji/api@17.0.3`，MIT 许可证见 `LICENSE-TWEMOJI`。
- `twemoji-svg.zip`：来自对应 Git 标签 `v17.0.3` 的 `assets/svg`，保留原文件名；图形许可证 CC BY 4.0 见 `LICENSE-GRAPHICS`。
- 排名卡片页脚保留图形署名。更新素材时一起更新解析器、版本记录及许可证。

## 验证

```bash
python -m unittest discover -s tests -p 'test_ranking*.py' -v
python tools/preview_ranking.py
```

预览输出到 `figs/ranking_preview/`，使用虚构昵称，覆盖普通中文、Emoji 组合、长昵称、空榜单、20 人榜单与积分榜。
