---
name: company-interview-search
description: >
  当用户需要搜索公司面试经验、查找面经、了解面试流程、查询薪资待遇、准备求职面试时触发。
  支持从牛客网、脉脉网、知乎、CSDN等多个平台快速获取公司相关的面经信息。
  触发词包括但不限于：面经、面试经验、面试题、笔经、求职经验、公司面试、薪资待遇、offer、
  牛客网、脉脉、找工作、面试准备、面经搜索、公司面经、阿里面经、字节面经、腾讯面经等。
  当用户询问"XX公司怎么样"、"XX公司面试难吗"、"XX公司薪资如何"等需要获取公司面试相关信息的请求时，也应触发此技能。
---

# company-interview-search

公司面经搜索技能 - 从牛客网、脉脉网、知乎、CSDN等平台快速获取公司面试经验

## 功能特性

- **多平台支持**: 牛客网、脉脉、知乎、CSDN
- **多搜索引擎聚合**: 搜狗、必应、百度，自动选择可用引擎
- **时间筛选**: 支持按天数筛选近期面经（`--days`）
- **岗位筛选**: 支持后端/前端/算法/测试/产品/运营/设计/数据等岗位过滤（`--position`）
- **正文抓取**: 自动抓取面经正文并转换为 Markdown（`--fetch`）
- **多格式输出**: text、markdown、json 三种输出格式
- **配置文件**: 支持自定义默认参数（`config/config.json`）
- **插件化平台配置**: 易于扩展新平台（`config/platforms.json`）
- **智能去重**: URL去重 + 标题去重，避免重复结果
- **相关性排序**: 智能计算搜索结果相关性，优先展示高质量内容
- **并发搜索**: 多线程并发搜索，提升搜索效率
- **User-Agent 轮换**: 随机选择 User-Agent，应对反爬机制
- **友好错误提示**: emoji 图标 + 错误信息 + 解决建议

## 快速开始

### 基础搜索

```bash
python scripts/interview_search.py "阿里巴巴"
```

### 常用组合

```bash
# 近30天的面经
python scripts/interview_search.py "字节跳动" --days 30

# 后端岗位面经
python scripts/interview_search.py "腾讯" --position backend

# 指定平台
python scripts/interview_search.py "百度" --platforms nowcoder,maimai

# 抓取前3条正文并输出Markdown
python scripts/interview_search.py "美团" --fetch 3 --format markdown

# 查看所有支持的平台
python scripts/interview_search.py --list-platforms

# 查看所有支持的岗位类型
python scripts/interview_search.py --list-positions
```

## 详细用法

### 命令行参数

```
usage: interview_search.py [-h] [--platforms PLATFORMS] [--engines ENGINES]
                           [--limit LIMIT] [--format {text,markdown,json}]
                           [--fetch FETCH] [--max-body-chars MAX_BODY_CHARS]
                           [--days DAYS]
                           [--position {,backend,frontend,algorithm,test,product,operation,design,data}]
                           [--timeout TIMEOUT] [--max-retries MAX_RETRIES]
                           [--quiet] [--list-platforms] [--list-positions]
                           company
```

### 参数说明

| 参数 | 短参数 | 说明 | 默认值 |
|------|--------|------|--------|
| `company` | - | 公司名称（必填） | - |
| `--platforms` | `-p` | 搜索平台，逗号分隔 | `nowcoder,maimai` |
| `--engines` | `-e` | 搜索引擎，逗号分隔 | `sogou,bing` |
| `--limit` | `-l` | 每个引擎每个查询返回的最大结果数 | `10` |
| `--format` | `-f` | 输出格式：text/markdown/json | `text` |
| `--fetch` | - | 抓取前 N 条结果的正文内容 | `0`（不抓取） |
| `--max-body-chars` | - | 抓取正文时的最大字符数 | `5000` |
| `--days` | `-d` | 只显示近 N 天的面经，0 表示不限制 | `0` |
| `--position` | - | 按岗位筛选 | 空（不筛选） |
| `--timeout` | - | 单个请求超时时间（秒） | `15` |
| `--max-retries` | - | 失败重试次数 | `2` |
| `--quiet` | `-q` | 静默模式，不输出进度日志 | `false` |
| `--list-platforms` | - | 列出所有支持的平台并退出 | - |
| `--list-positions` | - | 列出所有支持的岗位类型并退出 | - |

### 支持的平台

| 平台标识 | 平台名称 | 说明 |
|----------|----------|------|
| `nowcoder` | 牛客网 | 国内最大的IT求职面试平台 |
| `maimai` | 脉脉 | 职场社交平台，真实员工面经分享 |
| `zhihu` | 知乎 | 高质量面经分享社区 |
| `csdn` | CSDN | 技术博客平台，大量面试经验分享 |

### 支持的岗位类型

| 岗位标识 | 岗位名称 | 关键词示例 |
|----------|----------|------------|
| `backend` | 后端开发 | 后端、后台、Java、Go、Python、服务端 |
| `frontend` | 前端开发 | 前端、Web前端、Vue、React |
| `algorithm` | 算法 | 算法、机器学习、深度学习、AI、NLP、CV |
| `test` | 测试/测开 | 测试、测试开发、测开、QA、质量 |
| `product` | 产品经理 | 产品、产品经理、PM |
| `operation` | 运营 | 运营、产品运营、用户运营、内容运营 |
| `design` | 设计 | 设计、UI、UX、交互、视觉设计 |
| `data` | 数据 | 数据、数据分析、数据挖掘、大数据、数仓 |

## 配置文件

### 默认配置（config/config.json）

```json
{
  "default_platforms": ["nowcoder", "maimai"],
  "default_engines": ["sogou", "bing"],
  "default_limit": 10,
  "default_timeout": 15,
  "default_max_retries": 2,
  "default_max_body_chars": 5000,
  "default_fetch_count": 0,
  "default_format": "text",
  "concurrency": {
    "search_workers": 8,
    "fetch_workers": 5
  },
  "user_agents": [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  ],
  "position_keywords": {
    "backend": ["后端", "后台", "Java", "Go", "Python", "服务端", "后端开发"],
    "frontend": ["前端", "前端开发", "Web前端", "Vue", "React", "前端工程师"],
    "algorithm": ["算法", "算法工程师", "机器学习", "深度学习", "AI", "NLP", "CV"],
    "test": ["测试", "测试开发", "测开", "QA", "质量", "测试工程师"],
    "product": ["产品", "产品经理", "PM", "产品运营"],
    "operation": ["运营", "产品运营", "用户运营", "内容运营"],
    "design": ["设计", "UI", "UX", "交互", "视觉设计"],
    "data": ["数据", "数据分析", "数据挖掘", "大数据", "数仓"]
  }
}
```

### 平台配置（config/platforms.json）

```json
{
  "nowcoder": {
    "name": "牛客网",
    "domain": "nowcoder.com",
    "keywords": ["面经", "面试经验", "笔经面经", "面试题"],
    "description": "牛客网 - 国内最大的IT求职面试平台",
    "priority": 1,
    "url_patterns": [
      "nowcoder.com/discuss",
      "nowcoder.com/experience"
    ]
  },
  "maimai": {
    "name": "脉脉",
    "domain": "maimai.cn",
    "keywords": ["面经", "面试", "薪资", "offer", "求职"],
    "description": "脉脉 - 职场社交平台，真实员工面经分享",
    "priority": 2,
    "url_patterns": [
      "maimai.cn/article",
      "maimai.cn/topic"
    ]
  },
  "zhihu": {
    "name": "知乎",
    "domain": "zhihu.com",
    "keywords": ["面经", "面试经验", "求职经验", "面试题"],
    "description": "知乎 - 高质量面经分享社区",
    "priority": 3,
    "url_patterns": [
      "zhihu.com/question",
      "zhihu.com/answer",
      "zhuanlan.zhihu.com"
    ]
  },
  "csdn": {
    "name": "CSDN",
    "domain": "csdn.net",
    "keywords": ["面经", "面试题", "面试经验", "笔试"],
    "description": "CSDN - 技术博客平台，大量面试经验分享",
    "priority": 4,
    "url_patterns": [
      "blog.csdn.net",
      "csdn.net/article"
    ]
  }
}
```

### 添加新平台

1. 在 `config/platforms.json` 中添加新平台配置
2. 配置域名、关键词、优先级等信息
3. 无需修改代码，即可自动支持新平台

## 输出格式

### Text 格式（默认）

```
=== 阿里巴巴 面经搜索结果 ===
共找到 27 条结果

【牛客网】(19条)
--------------------------------------------------
1. 【阿里巴巴已offer】【附解答】Java实习五面详细面经_牛客网
   链接: https://www.sogou.com/link?url=...
   岗位: 后端
   摘要: Java集合几乎是面试
```

### Markdown 格式

```markdown
# 阿里巴巴 面经搜索结果

共找到 **27** 条面经结果

## 牛客网 (19条)

### 1. [【阿里巴巴已offer】【附解答】Java实习五面详细面经_牛客网](https://...)

*💼 后端 | 🔍 来源: sogou*

> Java集合几乎是面试

---
```

### JSON 格式

```json
[
  {
    "title": "【阿里巴巴已offer】【附解答】Java实习五面详细面经_牛客网",
    "url": "https://www.sogou.com/link?url=...",
    "snippet": "Java集合几乎是面试",
    "platform": "nowcoder",
    "platform_name": "牛客网",
    "engine": "sogou",
    "body": "",
    "body_status": "",
    "publish_time": "",
    "publish_date": null,
    "positions": ["backend"],
    "relevance_score": 5.5
  }
]
```

## 搜索策略

每个平台使用多种搜索策略组合，提高召回率：

1. **site: 语法**：`site:nowcoder.com 公司名 面经`
2. **平台名搜索**：`公司名 面经 牛客网`
3. **泛搜索**：`公司名 面经`（后续过滤域名）

每种策略会根据岗位筛选和时间筛选自动添加相应关键词。

## 相关性评分

搜索结果根据以下维度计算相关性得分，按得分排序：

| 维度 | 权重 | 说明 |
|------|------|------|
| 标题包含完整公司名 | +3.0 | 核心权重 |
| 摘要包含公司名 | +1.5 | 次要权重 |
| 标题包含面经关键词 | +2.0 | 核心权重 |
| 摘要包含面经关键词 | +1.0 | 次要权重 |
| 标题包含平台名 | +1.0 | 辅助权重 |
| 有发布时间 | +0.5 | 信息完整度 |
| 有摘要 | +0.5 | 信息完整度 |

## 常见问题

### Q: 为什么搜索结果很少？

A: 可能的原因：
- 搜索引擎反爬限制，可尝试更换搜索引擎（`--engines baidu`）
- 公司名太特殊或太小众
- 时间筛选太严格，可尝试放宽 `--days` 参数
- 岗位筛选太严格，可尝试去掉 `--position` 参数

### Q: 为什么有些结果不是目标平台的？

A: 对于搜索引擎的重定向链接（如搜狗的 /link、百度的 /link），无法直接通过域名判断平台，会根据标题和摘要中的平台名称、面经关键词进行智能判断。极少数情况下可能会有误判。

### Q: 如何提高搜索结果质量？

A: 建议：
- 使用 `--fetch` 参数抓取正文，获取更完整的面经内容
- 使用 `--days` 参数筛选近期面经
- 使用 `--position` 参数筛选目标岗位
- 输出为 Markdown 格式，便于阅读和整理

### Q: 支持哪些搜索引擎？

A: 目前支持搜狗（sogou）、必应（bing）、百度（baidu）三个搜索引擎。
- 搜狗：结果质量高，但容易触发反爬
- 必应：稳定性好，反爬宽松
- 百度：结果丰富，但有安全验证

默认使用搜狗 + 必应组合，可根据实际情况调整。

### Q: 如何添加新的平台支持？

A: 在 `config/platforms.json` 中添加新平台的配置即可，无需修改代码。配置项包括：
- `name`: 平台名称
- `domain`: 平台域名
- `keywords`: 面经相关关键词
- `description`: 平台描述
- `priority`: 优先级（数字越小越靠前）

## 项目结构

```
company-interview-search/
├── SKILL.md                    # 技能说明文档
├── config/
│   ├── config.json             # 默认配置文件
│   └── platforms.json          # 平台配置文件
└── scripts/
    ├── http_client.py          # HTTP 客户端（自动解压、编码检测、反爬检测、重试）
    ├── html_to_markdown.py     # HTML 转 Markdown 工具
    └── interview_search.py     # 面经搜索主脚本
```

## 依赖

- Python 3.7+
- 标准库（无需额外安装依赖）

## 示例

### 示例1：基础搜索

```bash
$ python scripts/interview_search.py "字节跳动"
🔍 正在搜索 字节跳动 的面经...
📱 平台: 牛客网, 脉脉
🌐 引擎: sogou, bing

=== 字节跳动 面经搜索结果 ===
共找到 26 条结果

【牛客网】(14条)
--------------------------------------------------
1. 字节跳动 产品运营 面经分享_牛客网
   链接: https://www.sogou.com/link?url=...
   岗位: 产品、运营
   摘要: 字节跳动...
...
```

### 示例2：带筛选条件的搜索

```bash
$ python scripts/interview_search.py "腾讯" --days 90 --position backend --format markdown
```

输出为 Markdown 格式，只包含近90天的后端岗位面经。

### 示例3：抓取正文

```bash
$ python scripts/interview_search.py "美团" --fetch 3 --format markdown
```

抓取前3条结果的正文内容，输出为 Markdown 格式，便于阅读和整理。

## 注意事项

1. **反爬机制**：搜索引擎有反爬机制，频繁请求可能会被限制。建议合理控制请求频率。
2. **结果准确性**：搜索结果基于搜索引擎返回的内容，可能存在不相关或过时的内容。
3. **正文抓取**：正文抓取功能可能会遇到网站登录验证、反爬等限制，不一定能成功抓取所有页面。
4. **使用场景**：本工具仅供学习和研究使用，请遵守各网站的使用条款和 robots 协议。
