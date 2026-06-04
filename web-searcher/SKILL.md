---
name: web-searcher
description: >
  多搜索引擎并行网络检索技能。包含可复用的终端脚本（search.sh / search.ps1），通过 curl / Invoke-WebRequest 抓取 Bing、Google、DuckDuckGo、Baidu、Sogou 搜索结果页，解析 HTML 提取标题+链接+摘要，汇总去重后输出。
  当用户需要搜索网络信息、查找资料、检索新闻、搜索技术文档、查找教程、搜索任何网上内容时触发。
  触发词包括但不限于：搜索、搜一下、帮我搜、帮我查、查一下、网上搜、谷歌搜索、百度搜索、bing搜索、搜搜、找一下、检索、search、google、look up、find online。
  即使用户只是随口说"帮我查查XXX"、"搜一下XXX"、"XXX是什么"这类需要联网获取信息的请求，也应触发此技能。
  重要：当前环境 WebSearch 工具不可用，本技能是唯一的网络检索手段。优先使用脚本，脚本不可用时回退到 WebFetch。
---

# Web Searcher — 多搜索引擎并行检索

## 技能文件

```
web-searcher/
├── SKILL.md          # 本文件
├── search.sh         # Bash 脚本（Linux/macOS/Git Bash）
└── search.ps1        # PowerShell 脚本（Windows）
```

## 使用方式

### 方式一：终端脚本（推荐，可复用）

**Bash（Linux / macOS / Git Bash）：**
```bash
bash search.sh "搜索词" [--engines bing,google] [--limit 10] [--json] [--lang zh]
```

**PowerShell（Windows）：**
```powershell
powershell -ExecutionPolicy Bypass -File search.ps1 "搜索词" [-Engines "bing,google"] [-Limit 10] [-Json] [-Lang zh]
```

参数说明：
- `--engines / -Engines`：逗号分隔的引擎列表，可选 `bing,google,duckduckgo,baidu,sogou`，默认 `bing,google,duckduckgo,sogou`
- `--limit / -Limit`：每个引擎返回的最大结果数，默认 10
- `--json / -Json`：输出 JSON 数组格式
- `--lang / -Lang`：`en` 或 `zh`，设为 `zh` 时自动添加百度

### 方式二：WebFetch 回退

当脚本不可用（无 curl、权限不足等）时，使用 WebFetch 工具直接抓取搜索引擎页面：

1. 构造搜索 URL：`https://www.bing.com/search?q={URL编码的搜索词}`
2. 并行调用 WebFetch（多个引擎放在同一消息中）
3. 从返回的 markdown 中提取结果

## 执行流程

### 第一步：确定搜索词和引擎

从用户请求中提取关键词。根据内容语言选择引擎：
- 英文内容：Bing + Google + DuckDuckGo
- 中文内容：Bing + Baidu + Google
- 用户指定：使用用户指定的引擎

### 第二步：运行脚本

将脚本路径设为技能目录下的 `search.sh` 或 `search.ps1`。

```bash
# 示例：搜索英文内容
bash "<skill-path>/search.sh" "Claude API documentation 2026" --limit 10

# 示例：搜索中文内容
bash "<skill-path>/search.sh" "Vue3 组合式API教程" --lang zh --limit 10

# 示例：JSON 输出（方便程序处理）
bash "<skill-path>/search.sh" "React Server Components" --json --limit 5
```

PowerShell 同理：
```powershell
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "Claude API" -Limit 10
```

### 第三步：展示结果

脚本输出格式化的搜索结果，直接展示给用户即可。如果脚本执行失败，回退到 WebFetch 方式。

### 第四步：深入查看（可选）

用户可能要求查看某条结果的详细内容。此时用 WebFetch 抓取该结果的 URL，提取页面主要内容。

## 技术细节

### 脚本工作原理

1. **URL 构造**：将搜索词 URL 编码，拼接到各搜索引擎的 URL 模板
2. **并行抓取**：使用 `curl`（bash）/ `WebClient`（PS1）并行请求各引擎
3. **HTML 解析**：
   - Bing：提取 `<h2 class="">` + `<div class="b_caption">` 块，解码 base64 重定向 URL
   - Google：提取 `/url?q=REAL_URL` 格式的链接
   - DuckDuckGo：提取 `class="result__a"` 的链接
   - Baidu：提取 `<h3 class="t">` 块
4. **去重合并**：按域名+路径去重，合并结果
5. **格式化输出**：支持人类可读格式和 JSON 格式

### 编码处理

- Bash 脚本：使用 `grep -oP`（PCRE）进行非贪婪匹配
- PS1 脚本：Bing 返回 GBK 编码（尽管声明 UTF-8），脚本自动检测并使用正确编码
- 两个脚本都使用短 User-Agent 以获取完整的搜索结果页面

### 依赖

- **Bash 脚本**：curl, grep -P (PCRE), sed, base64（标准 Unix 工具）
- **PS1 脚本**：.NET WebClient（PowerShell 内置）
- 两个脚本均为零外部依赖，可直接在任何 Unix/Windows 系统运行

## 特殊情况处理

### 搜索结果为空
- 如果所有引擎都返回空结果，告知用户并建议换关键词或换语言

### 脚本执行失败
- 某个引擎超时或返回错误是正常的，忽略失败引擎继续
- 如果所有引擎都失败，回退到 WebFetch 方式

### 用户要求深入查看
- 搜索完成后用 WebFetch 抓取具体 URL
- 可配合 `web-reverse-engineer` 技能深入分析

## 注意事项

- 脚本有 15 秒超时，单个引擎超时不影响其他引擎
- 搜索引擎可能返回广告结果，脚本已尽量过滤
- 搜索结果依赖搜索引擎的 HTML 结构，如果引擎改版可能需要更新解析逻辑
