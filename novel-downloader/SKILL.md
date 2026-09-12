---
name: novel-downloader
description: >
  下载网络小说（完本或连载中）的 TXT 电子书技能。当用户想下载小说、找小说txt、下载完本小说、
  获取连载小说最新章节、把小说转成txt文件时触发。触发词包括但不限于：下载小说、小说txt、
  完本下载、txt全集、小说全本、帮我下小说、下载XXX（书名）、XXX有txt吗、找小说资源、
  最新章节下载。即使用户只是说"能把XXX下载下来吗"、"XXX这本书有完本吗"，只要意图是获取
  小说的 TXT 文本文件，都应触发本技能。本技能内置多个小说下载数据源的搜索与打包下载逻辑
  （速读谷/平板电子书网/TXT图书下载网等），并自动完成编码转换（GBK→UTF-8）与完整性验证。
---
# novel-downloader — 网络小说 TXT 下载

## 核心能力

1. **多数据源搜索**：站内搜索 + 全网搜索定位书籍 ID
2. **打包下载**：从支持 txt 打包下载的站点直接获取全本（或最新章节）
3. **章节爬虫**：对只有在线阅读、无打包接口的站点，逐章抓取拼接完整 txt
4. **自动转码**：GBK/其他编码 → UTF-8，中文不乱码
5. **完整性验证**：章节数统计、最大章节号、开头/结尾检查
6. **按需整理**：合并指定章节、生成章节目录、按卷拆分

## 数据源清单（按优先级）

| 优先级 | 数据源 | 地址 | 特点 | 下载方式 |
|---|---|---|---|---|
| 1 | 速读谷 | sudugu.co | jieqi 系统，**txt 打包直链，无反爬** | `packdown.php?aid={id}`，支持分卷 |
| 2 | 我书阁 | woshuge.com | **API 返回 zip 直链，无反爬，全自动** | 搜索 `/search.html` → POST `/api/download/{id}` → 下载 zip → 解压 |
| 3 | 平板电子书网 | qiqixs.info / 77nt.info | 信息全（字数/章节/最新章节），txt 直链 | `txt.qiqixs.info/txt/{id}/{书名}.txt`（**有 Cloudflare 防护**） |
| 4 | TXT图书下载网 | wap.bookshuku.org | txt/zip 双格式 | `txt.bookshuku.org/home/down/txt/id/{id}`（**有 Cloudflare 防护**） |
| 5 | 百度网盘分享 | pan.baidu.com | 免登录 API 下载 | 分享页参数 → wlist → sharedownload → dlink |
| 6 | 贴吧 | tieba.baidu.com | 常有校对版全本 | 需过百度安全验证（滑块），链接多为网盘/工具站 |
| 7 | 其他 jieqi 系统站 | 任意含 `modules/article/packdown.php` 的站 | 接口通用 | 同速读谷 |

辅助参考源（信息查询/兜底）：歌书网 gebiqu.com、炫书网 ibiquta.net、天骄无双 tianjiaowushuangxiaoshuo.com、sjwx.info、m.bookdown.net。
已知不可用/低价值源：txtxiaoshuo.com（下载指向城通网盘 ctfile，需验证码，非全自动）、奇书网系列 qishu66/qishu99（域名已失效）、txt80.cc（搜索接口 404）、23qb.net（失效）、88dus.com（域名已出售）。

## 执行流程

### 第一步：解析需求

确认：书名（必填）、作者（可选，用于排除同名书）、版本偏好（最新连载 / 完本）、输出目录（默认 `d:/yousen/`，文件名 `{书名}.txt`）。

### 第二步：定位书籍 ID（并行执行）

```bash
py scripts/novel_download.py 书名 --search --author 作者(可选)
```

脚本会对速读谷、平板电子书网、TXT图书下载网做**站内搜索**，同时提示用 web_search 补一轮全网搜索（找贴吧/知乎/百度知道的资源帖）。输出：候选书籍（书名/作者/ID/收录范围/最新章节）。

选书要点：
- 优先选与用户作者名匹配、章节数最多、状态标注"完本/连载至最新"的候选
- 同书多候选时，把速读谷（直链无防护）排最前

### 第三步：下载（按优先级自动回退）

```bash
# 速读谷（无防护，首选）
py scripts/novel_download.py 书名 --source sudugu --id {aid} --out d:/yousen/

# 我书阁（API 全自动，zip 直链）
py scripts/novel_download.py 书名 --source woshuge --id {id} --out d:/yousen/

# 平板电子书网（有 CF，requests 可能 403）
py scripts/novel_download.py 书名 --source qiqixs --id {id} --out d:/yousen/

# TXT图书下载网
py scripts/novel_download.py 书名 --source bookshuku --id {id} --out d:/yousen/
```

**遇 Cloudflare 防护（返回 403 + "Just a moment..."）时的处理**：
1. 改用 agent-browser 真实浏览器（默认有头模式）打开下载链接，CF 自动放行并触发下载到浏览器下载目录
2. 若 CF 弹"请验证您是真人"，请用户手动勾选，通过后继续
3. 从浏览器下载目录找到文件，复制到目标位置
4. 贴吧同理：滑块验证需用户手动配合

**百度网盘分享**（分享页含 `pan.baidu.com/s/xxx`）：用脚本内置的免登录 API 流程（分享页抓 shareid/uk/sign/timestamp → wlist 列文件 → sharedownload 拿 dlink → 下载）。链接失效（errno -7）则换源。

### 爬虫模式：在线阅读站拼 txt（无打包接口时）

当数据源清单中没有该书的打包下载，但某站提供**在线阅读**时，用章节爬虫：

```bash
# 先爬 5 章测试解析是否正常（目录数/正文质量）
py scripts/novel_crawler.py "目录页URL" --out d:/yousen/ --limit 5

# 确认正常后爬全本（--start 支持断点续传；进度存 progress.json，中断后重跑自动续）
py scripts/novel_crawler.py "目录页URL" --out d:/yousen/ --delay 0.5
```

爬虫特性（`scripts/novel_crawler.py`）：
- 自动识别多种目录结构：`<dd><a>`（qiqixs/老笔趣阁）、`id="list"`、`<dl>` 等
- 自动识别多种正文容器：`id="content*"`、`class="content"`、`htmlContent`、`chaptercontent`、`nr`、`showtxt`、`<article>` 等
- **平衡 div 解析**：正文容器内有嵌套 div 也能完整截取
- 编码自动检测（UTF-8/GBK），`<br>` 转段落，清理脚本残留与广告词
- 断点续传（progress.json）+ 失败重试 3 次 + 请求限速（`--delay` 默认 0.5s，礼貌爬取防封）
- 请求优先用 requests（本机已验证对 qiqixs 等站兼容性最好），urllib 兜底

已实测可用：qiqixs.info（平板电子书网在线阅读，2530 章目录解析 + 正文提取正常）。
已实测不可用：biquge365.net（正文 JS 动态加载，静态 HTML 无正文）、xbiquge.la→xbiqugu.la（壳站）、shenpinwu/qubook/ranwen.la（反爬壳站）、天骄无双（CF 522 不稳定）。
**注意**：正文 JS 加载的站（页面 HTML 里找不到正文文本）无法静态爬取，需 agent-browser 或放弃。

### 第四步：转码 + 完整性验证（下载后必做）

```bash
py scripts/novel_download.py 文件路径 --convert --verify
```

脚本自动：
- 检测编码（UTF-8/GBK/GB18030），转成 UTF-8 输出
- 统计章节数、最大章节号（检查是否连续）
- 打印开头 300 字 + 结尾 600 字（验证内容真实、是否完本/断更点）

**汇报格式**（向用户展示）：
| 项目 | 详情 |
|---|---|
| 文件位置 | 绝对路径 |
| 章节范围 | 第 N ~ 第 M 章 |
| 大小/字数 | xx MB / xx 万字符 |
| 编码 | UTF-8 |
| 状态 | 完本 / 连载至最新（含作者公告则说明） |

### 第五步：按需整理

用户可能要求：
- **合并指定章节**：`py scripts/novel_download.py 原文件 --merge "193,374-375,644-645" --out 合集.txt`
- 按卷拆分、生成章节目录等

## 已知问题与处理

| 问题 | 处理 |
|---|---|
| 下载 403 / "Just a moment..." | Cloudflare 防护 → agent-browser 有头模式 + 用户手动勾选验证 |
| 百度网盘 errno -7 | 分享已失效，换源 |
| 贴吧滑块验证 | 用户手动拖一下，之后继续抓 |
| 控制台中文乱码（Windows GBK） | 脚本输出用文件落盘而非 print，或设置 `PYTHONIOENCODING=utf-8` |
| 搜索结果匹配到同人/续写 | 检查作者名，明确标注"原著/同人"，问用户是否接受 |
| 超长小说（>1000 章） | 速读谷分卷下载（start/end 参数），或接受连载到最新 |
| 书中包含作者感言/公告 | 保留（是连载状态的证据），汇报时说明 |

## 脚本依赖

- Python 3.8+，**仅标准库**（requests 可选，缺失时用 urllib 兜底）
- 网络代理：本机常见代理端口 7897 可能影响直连，超时时重试或提示用户
- 浏览器自动化（仅 CF/验证码场景）：agent-browser

## 文件结构

```
novel-downloader/
├── SKILL.md                  # 本文件
└── scripts/
    ├── novel_download.py     # 核心脚本：搜索/下载/转码/验证/合并
    └── novel_crawler.py      # 在线阅读站章节爬虫：目录解析/正文提取/断点续传
```
