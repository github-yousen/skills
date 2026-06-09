---
name: web-searcher
description: >
  当用户需要搜索网络信息、查找资料、检索新闻、搜索技术文档、查找教程、搜索任何网上内容时触发。
  触发词包括但不限于：搜索、搜一下、帮我搜、帮我查、查一下、网上搜、谷歌搜索、百度搜索、bing搜索、搜搜、找一下、检索、search、google、look up、find online。
  即使用户只是随口说"帮我查查XXX"、"搜一下XXX"、"XXX是什么"这类需要联网获取信息的请求，也应触发此技能。
---

# Web Searcher — 多搜索引擎并行检索

## 技能文件

```
web-searcher/
├── SKILL.md                # 本文件
├── search.ps1              # PowerShell 脚本（Windows 零依赖回退）
└── scripts/
    ├── http_client.py      # 鲁棒 HTTP 抓取层（自动解压/反爬检测/重试）
    └── web_search.py       # Python 主入口（推荐，支持并行+多格式输出）
```

## 使用方式

### 方式一：Python 脚本（推荐，更鲁棒）

依赖 Python 3.8+（**仅标准库，零外部依赖**）：

```bash
# Windows PowerShell
py scripts/web_search.py "搜索词" --limit 10

# Linux/macOS
python3 scripts/web_search.py "搜索词" --limit 10
```

参数：
- `--engines`：逗号分隔的引擎列表，可选 `bing,google,duckduckgo,baidu,sogou`，默认按 `--lang` 自动选
- `--limit / -l`：每引擎返回的最大结果数，默认 10
- `--lang {en,zh,auto}`：`zh` 强制加 baidu；`auto` 按 query 是否含中文自动选（默认 auto）
- `--format / -f {text,markdown,json}`：输出格式（默认 text）
- `--allowed-domains`：仅显示的域名（逗号分隔）
- `--blocked-domains`：排除的域名（逗号分隔）
- `--timeout`：单引擎超时秒数，默认 15
- `--max-retries`：单引擎重试次数，默认 2
- `--no-verbose`：静默模式（不打反爬/重试日志到 stderr）

**优势相比 PS 脚本**：自动解压 gzip（避免乱码）、反爬页检测（CF/百度安全验证等给出明确提示）、SSL 跳过、并行抓取（5 引擎并发）、JSON/Markdown 输出、snippet 提取更完整（PS 脚本只有 Bing 有 snippet）。

### 方式二：PowerShell 脚本（零外部依赖，Windows 必选）

无 Python 环境时的回退方案。

```powershell
powershell -ExecutionPolicy Bypass -File search.ps1 "搜索词" [-Engines "bing,google"] [-Limit 10] [-Json] [-Lang zh]
```

参数说明：
- `--engines / -Engines`：逗号分隔的引擎列表，可选 `bing,google,duckduckgo,baidu,sogou`，默认 `bing,google,duckduckgo,sogou`
- `--limit / -Limit`：每个引擎返回的最大结果数，默认 10
- `--json / -Json`：输出 JSON 数组格式
- `--lang / -Lang`：`en` 或 `zh`，设为 `zh` 时自动添加百度
- `--allowed-domains / -AllowedDomains`：仅显示指定域名的结果（逗号分隔）
- `--blocked-domains / -BlockedDomains`：排除指定域名的结果（逗号分隔）
- `--max-retries / -MaxRetries`：失败重试次数，默认 2
- `--timeout / -TimeoutSeconds`：单个引擎超时时间（秒），默认 15

## 执行流程

### 第一步：确定搜索词和引擎

从用户请求中提取关键词。根据内容语言选择引擎：
- 英文内容：Bing + Google + DuckDuckGo
- 中文内容：Bing + Baidu + Google
- 用户指定：使用用户指定的引擎

### 第二步：运行脚本

将脚本路径设为技能目录下的 `search.ps1`。

```powershell
# 基础搜索
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "Claude API" -Limit 10

# 中文搜索
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "Vue3 组合式API教程" -Lang zh -Limit 10

# 域过滤：仅显示指定域名结果
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "React hooks" -AllowedDomains "reactjs.org,github.com"

# 域过滤：排除特定域名
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "Python教程" -BlockedDomains "csdn.net,baidu.com"

# 自定义重试和超时
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "AI最新进展" -MaxRetries 3 -TimeoutSeconds 20

# JSON 输出（便于程序处理）
powershell -ExecutionPolicy Bypass -File "<skill-path>/search.ps1" "机器学习" -Json -Limit 5
```

### 第三步：展示结果

脚本输出格式化的搜索结果，直接展示给用户即可。如果脚本执行失败，回退到 WebFetch 方式。

### 第四步：深入查看（可选）

用户可能要求查看某条结果的详细内容。此时用 WebFetch 抓取该结果的 URL，提取页面主要内容。

## 技术细节

### 脚本工作原理

1. **URL 构造**：将搜索词 URL 编码，拼接到各搜索引擎的 URL 模板
2. **并行抓取**：使用 `HttpWebRequest` 并行请求各引擎
3. **HTML 解析**：
   - Bing：提取 `<h2 class="">` + `<div class="b_caption">` 块，解码 base64 重定向 URL
   - Google：提取 `/url?q=REAL_URL` 格式的链接
   - DuckDuckGo：提取 `class="result__a"` 的链接
   - Baidu：提取 `<h3 class="t">` 块
   - Sogou：提取 `<h3 class="vr-title">` 块
4. **域过滤**：支持允许/排除特定域名，使用正则表达式匹配
5. **去重合并**：按域名+路径去重，合并结果
6. **格式化输出**：支持人类可读格式和 JSON 格式

### 编码检测

- **PS1 脚本**：
  1. 优先从 HTTP 响应头 `Content-Type` 检测 charset
  2. 检查 BOM（字节顺序标记）自动识别编码
  3. 根据域名猜测编码（Bing/Baidu/Sogou 使用 GBK）
  4. 使用 `HttpWebRequest` 读取所有字节到内存流，避免流寻址问题

### 重试与超时

- **重试机制**：默认 2 次重试，可通过 `--max-retries` 参数调整
- **超时控制**：默认 15 秒超时，可通过 `--timeout` 参数调整
- **错误隔离**：单个引擎失败不影响其他引擎

### 依赖

- **PS1 脚本**：.NET HttpWebRequest（PowerShell 内置）
- 脚本为零外部依赖，可直接在任何 Windows 系统运行

## 特殊情况处理

### 搜索结果为空
- 如果所有引擎都返回空结果，告知用户并建议换关键词或换语言
- 检查域过滤是否过于严格，尝试放宽限制

### 脚本执行失败
- 某个引擎超时或返回错误是正常的，忽略失败引擎继续
- 如果所有引擎都失败，回退到 WebFetch 方式
- 重试机制会自动处理临时网络问题

### 域过滤问题
- 如果域过滤没有生效，检查域名拼写是否正确
- 子域名会自动匹配（如 `example.com` 匹配 `www.example.com`）
- 多个域名用逗号分隔，不要有空格

### 编码问题
- 中文搜索结果出现乱码时，检查终端编码设置
- PowerShell 脚本会自动检测编码，通常无需手动调整

### 用户要求深入查看
- 搜索完成后用 WebFetch 抓取具体 URL
- 可配合 `web-reverse-engineer` 技能深入分析

## 注意事项

- **超时控制**：默认 15 秒超时，可通过 `--timeout` 参数调整，单个引擎超时不影响其他引擎
- **重试机制**：默认 2 次重试，可通过 `--max-retries` 参数调整，提高网络不稳定时的成功率
- **域过滤**：支持允许/排除特定域名，提高结果相关性
- **编码检测**：PowerShell 脚本自动检测编码，解决中文乱码问题
- **广告过滤**：搜索引擎可能返回广告结果，脚本已尽量过滤
- **HTML 依赖**：搜索结果依赖搜索引擎的 HTML 结构，如果引擎改版可能需要更新解析逻辑
- **零依赖**：脚本为零外部依赖，可直接在任何 Windows 系统运行
- **JSON 输出**：支持 JSON 格式输出，便于程序处理和集成
