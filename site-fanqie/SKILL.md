---
name: site-fanqie
description: >
  番茄系站点统一操作技能（作者后台 + 短剧榜单 + 帮助中心/作家课堂三合一）。
  当用户提到以下任一类指令时触发：
  ① 作者后台操作——"操作番茄作者后台"、"查书籍"、"查章节"、"发章节"、"发布章节"、"查数据"、
  "查统计"、"查收益"、"查收入"、"看作品数据"、"回复评论"、"签到"、"请假"、"诊断作品"；
  ② 短剧榜单——"番茄短剧"、"红果短剧"、"短剧排行榜"、"短剧榜单"、"短剧热播榜/新剧榜/推荐榜"、
  "漫剧榜"、"查短剧热度"、"短剧今日上新"；
  ③ 帮助中心/教程——"查帮助中心"、"平台规则"、"签约规则"、"帮助文章"、"作家课堂"、
  "写作教程"、"新手教程"、"查教程列表"。
  模块②③免登录直接调用；模块①需先在 fanqienovel_auth.json 填入凭证。
---

# 番茄系站点统一技能（作者后台 + 短剧榜单 + 帮助中心）

一个技能覆盖番茄生态三类数据通道，与 `.codebuddy` 小说创作工作流（novel-write / novel-disassemble / novel-design 等）闭环配合：**选题参考（短剧风向）→ 写作（工作流）→ 发布（作者后台）→ 数据诊断（作者后台）→ 规则答疑（帮助中心）**。

## 模块路由（按用户意图选择）

| 意图关键词 | 模块 | 登录 | 核心入口 |
|-----------|------|------|---------|
| 查书籍/章节/数据/收益、发章节、评论、签到 | **A. 作者后台** | ✅ 需凭证 | `scripts/api_client.py` + 独立 CLI 脚本 |
| 短剧/红果/漫剧 榜单、今日上新 | **B. 短剧榜单** | ❌ 免登录 | `scripts/fanqie_drama_rank.py` |
| 帮助中心、平台规则、签约问题、写作教程 | **C. 帮助中心/课堂** | ❌ 免登录 | `scripts/helpcenter_query.py` |

> `{skill_dir}` 指本技能目录。作者后台凭证目录可用环境变量 `FANQIENOVEL_DATA_DIR` 覆盖。

---

## 模块 A：作者后台（fanqienovel.com，需凭证）

### 核心文件

| 文件 | 说明 |
|------|------|
| `{skill_dir}/fanqienovel_auth.json` | 凭证文件（Cookie / msToken / a_bogus / secsdk，**过期后只需更新这一个文件**） |
| `{skill_dir}/scripts/api_client.py` | 底层 API 客户端（运行时自动读凭证，含 `md_to_html` / `chapter_md_to_html` / `publish_chapter_from_md`） |
| `{skill_dir}/scripts/query_chapters.py` | 查书籍/章节状态（含隐藏/断更识别） |
| `{skill_dir}/scripts/fanqie_book_overview.py` | 全书发布状态一览 |
| `{skill_dir}/scripts/query_stats.py` | 查书籍数据统计汇总 |
| `{skill_dir}/scripts/query_chapter_stats.py` | 查每章完读/追读/流失数据表格 |
| `{skill_dir}/scripts/diagnose_book.py` | **数据诊断**：按合格标准逐项评价，指出短板 |
| `{skill_dir}/scripts/analyze_trends.py` | 全史多维趋势分析 |
| `{skill_dir}/scripts/publish_chapter.py` | 发布/更新章节（创建→预审→发布，支持 `--timer` 定时） |
| `{skill_dir}/scripts/query_income.py` | 查收益（汇总/每日/月度/礼物/互动，VM 加密） |
| `{skill_dir}/scripts/manage_comments.py` | 查看/回复读者评论、粉丝互动 |
| `{skill_dir}/scripts/attend.py` | 每日签到/请假/签到券（保障全勤奖） |
| `{skill_dir}/scripts/modify_book.py` | 修改书籍信息 |
| `{skill_dir}/scripts/fanqie_encrypt.js` | 收益接口 VM 加密模块（Node，依赖 crypto-js + bignumber.js） |

### CLI 快捷用法

```bash
# 查询类
python query_chapters.py [book_id]          # 书籍+章节状态
python query_stats.py [book_id]             # 数据汇总
python query_chapter_stats.py <book_id> [N] # 每章数据表格
python query_income.py [book_id]            # 收益（需 npm install）
python manage_comments.py <book_id>         # 书评列表（--reply/--fans/--like/--delete）

# 发布类（写操作）
python publish_chapter.py <book_id> <content.md路径> [volume_id] [volume_name] [item_id]
python publish_chapter.py <book_id> <content.md路径> --timer "2026-08-10 18:00"  # 定时发布

# 诊断/签到
python diagnose_book.py [book_id]           # 数据诊断
python attend.py <book_id>                  # 每日签到（--leave 请假 / --ticket 补签）
```

### 凭证说明（模块 A 使用前必填）

1. 打开 `https://fanqienovel.com` 登录作者账号
2. F12 → Network → 任选一条 `/api/author/` 请求
3. 复制请求头 **Cookie**、URL 中的 `msToken` / `a_bogus`、写操作请求头 `x-secsdk-csrf-token`
4. 更新 `fanqienovel_auth.json` 的 `cookie` / `ms_token` / `a_bogus` / `secsdk_token`

> 凭证有效期：`sid_guard` 约 60 天；`a_bogus` / `msToken` 失效后需重新抓取。请求报凭证错误时提示用户更新 `fanqienovel_auth.json`。

### 模块 A 关键规则（实测沉淀，勿丢）

- **通用参数**：`aid=2503`、`app_name=muye_novel`；GET 需 `msToken`+`a_bogus`；写操作需 `x-secsdk-csrf-token`
- **收益接口**：带 `book_id` 的收益接口必须带 `X-Muye-Encrypt-Key` 头并解密响应（`api_client.py` 自动走 Node 子进程）；`sec_time` 毫秒级、`start_date/end_date` 秒级；短篇用 `sa_income/book_monthly`、长篇用 `income/book_monthly_v3`
- **发布流程**：必须**先查已发布章节再发布**（防重复/漏发）；`volume_name` 必填；新章节需先 `new_article` 拿 `item_id`；推荐 `publish_chapter_from_md()` 一条龙
- **今日字数达上限**：🔴 禁止擅自定时到明天，必须告知用户并询问处理方式
- **章节状态**：`article_status` 1=已发布、2=断更/隐藏（非审核中）、0=草稿；`has_hide`/`set_top` 不可靠
- **书籍阶段**：`book_intro.status` 是权威字段（`book_auth_not_safe`=未签约不可搜属正常阶段，≠封禁；`cold_start_init/ing`=签约推流阶段）；勿把 `risk_rate` 高误判为违规
- **数据口径**：在读人数(前台14天累计) ≠ 阅读人数(后台单日)；章节跟读率直接用官方 `follow_read_rate` 勿推算；X万字读完率不能用章节读完率替代；断更>3天追更归零
- **npm 依赖**（收益查询专用）：`cd {skill_dir} && npm install crypto-js bignumber.js`

完整接口清单（530+ 端点）与字段释义见 `references/analysis_report.md`、`references/writer_backend_api_report.md`。

---

## 模块 B：短剧榜单（红果短剧，免登录免签名）

### 核心文件

| 文件 | 说明 |
|------|------|
| `{skill_dir}/scripts/fanqie_drama_rank.py` | 榜单查询脚本（推荐优先使用） |
| `{skill_dir}/scripts/verify_domains.py` | 多域名连通性验证 |
| `{skill_dir}/references/fanqie_drama_api_report.md` | 完整 API 报告（参数表/响应结构/54+ 抓包域名） |

### CLI 用法

```bash
py {skill_dir}/scripts/fanqie_drama_rank.py                # 全部 5 个榜单各前 15 条
py {skill_dir}/scripts/fanqie_drama_rank.py hot            # 短剧热播榜
py {skill_dir}/scripts/fanqie_drama_rank.py new 50         # 新剧榜 50 条
py {skill_dir}/scripts/fanqie_drama_rank.py recommend 100  # 推荐榜 100 条（自动翻页）
py {skill_dir}/scripts/fanqie_drama_rank.py --list         # 列出所有榜单
py {skill_dir}/scripts/verify_domains.py                   # 验证 API 域名连通性
```

### 榜单枚举

| board key | 榜单名 | 判定特征 |
|-----------|--------|----------|
| `recommend` | 短剧推荐榜 | `rec_text` 为 "X万推荐" |
| `hot` | 短剧热播榜 | 真人短剧 |
| `new` | 短剧新剧榜 | 真人短剧 |
| `comic_hot` | 漫剧热播榜 | `rec_text` 为 "X万热度"，出品方多为 "XX动漫" |
| `comic_new` | 漫剧新剧榜 | 同上 |

### API 要点

- 榜单：`GET https://<任一可用域名>/reading/bookapi/bookmall/cell/change/v`，公共参数 `aid=8662`、`app_name=novelread`、`version_code=72232`、`device_platform=android` 等；`cell_id=7470092475068071998`、`tab_type=26`
- 可用域名（2026-08-23 真机验证）：`api5-normal-sinfonlineb.fqnovel.com`（主）、`api5-normal-hl.fqnovel.com`（备）等 6 个，见报告
- 上新/筛选：`POST /reading/distribution/category/landpage/v`，`genre` 可选 `short_play`/`comic_series`/`ai_series`，`online_time=["days_7"]` 为 7 天内上新
- 搜索/剧集详情/视频直链需 X-Argus/X-Gorgon 签名，**勿裸调**（返回空体）；如需参考报告 §6 的 Frida 方案
- 榜单 30 分钟级更新，与 App 略有出入属正常

---

## 模块 C：帮助中心 / 作家课堂（免登录）

### 核心文件

| 文件 | 说明 |
|------|------|
| `{skill_dir}/scripts/helpcenter_query.py` | 帮助中心/教程统一查询 CLI |
| `{skill_dir}/references/author_zone_helpcenter_report.md` | 页面逆向分析报告（接口/数据结构/SSR 数据流） |

### CLI 用法

```bash
py {skill_dir}/scripts/helpcenter_query.py tree                        # 帮助中心三级分类树（7大类108篇）
py {skill_dir}/scripts/helpcenter_query.py article <category_id>       # 文章详情（默认打印纯文本正文，不落盘）
py {skill_dir}/scripts/helpcenter_query.py article <category_id> --save [路径]  # 可选：额外保存 HTML 源
py {skill_dir}/scripts/helpcenter_query.py search "签约" [页码=1]       # 搜索帮助文章
py {skill_dir}/scripts/helpcenter_query.py tutorials [tab] [页码=0]    # 作家课堂教程列表
py {skill_dir}/scripts/helpcenter_query.py list-help                   # 遍历全部帮助文章清单
```

**教程 tab 枚举**：`1`=新手专区（49篇）、`2`=大神专访（68篇）、`3`=写作技巧（60篇）、`4`=品类指南（67篇）、`5`=平台宝典（28篇，默认）。也支持中文 tab 名。

### 接口要点（2026-08-25 实测免登录）

| 接口 | 功能 | 关键参数 |
|------|------|---------|
| `GET /api/author/hfc/all_category/v0/` | 三级分类树 | 无 |
| `GET /api/author/hfc/article_info/v0/` | 文章详情（HTML 富文本） | `category_id` |
| `GET /api/author/hfc/search_article/v0/` | 搜索文章 | `query`、`page_index`(从1起)、`page_count` |
| `GET /api/node/tutorial/list` | 教程列表 | `type`(1-5)、`page_index`(**从0起**)、`page_count`(15) |
| `POST /api/author/growth_task/scene/v0` | 场景上报（进课堂页触发，可忽略） | `scene_type=10001` |

- 帮助中心 URL 规则：`/writer/zone/help/article?rank1={一级id}&rank2={二级id}&rank3={三级id}`，`0` 补位
- 教程文章正文页：`/writer/zone/article/{item_id}`
- 反馈类接口（`get/set_feedback_stat`）需登录；首屏数据也可直接抓页面 HTML 解析 `window._ROUTER_DATA`

---

## 模块间协作与 `.codebuddy` 工作流配合

本技能是 `.codebuddy` 小说创作工作流的**外部数据/发布枢纽**，三者共享同一套项目上下文（`novel/` 目录）：

### 创作发布闭环（核心链路）

```
novel-design / novel-outline（工作流设计大纲）
        │
        ▼
novel-write / novel-batch（写章节，产出 novel/chapters/[NNN]/content.md）
        │  （AI 味检查阶段调用 Humanizer-zh 技能）
        ▼
模块A publish_chapter.py  ← 发布章节到番茄（先 query_chapters 查重再发，支持定时）
        │
        ▼
模块A query_stats / diagnose_book / analyze_trends（数据诊断 → 发现断崖/毒点章）
        │
        ▼
反馈到 novel-design 调整后续剧情 ──► 循环
```

### 三模块横向配合场景

| 场景 | 组合 | 说明 |
|------|------|------|
| **选题风向** | 模块B（短剧榜单）+ `novel-disassemble` | 查爆款短剧/漫剧榜 → 热门题材、人设、改编风向 → 反哺 `novel-design` 选题（短剧改编是番茄重要变现路径，品类指南 tab 也有月度改编风向标文章） |
| **写作学习** | 模块C（tutorials）+ `novel-downloader` | 作家课堂 272 篇教程（新手专区/写作技巧）指导写作；下载对标小说配合 `novel-disassemble` 拆书学习 |
| **规则答疑** | 模块C（helpcenter） | 签约/审核/稿费/断更规则即查即用；`diagnose_book` 发现问题后到帮助中心查对应规则（如断更影响、申诉指引） |
| **收益复盘** | 模块A（query_income） | 收益汇总/每日/月度/礼物明细，评估作品商业表现 |
| **日常运营** | 模块A（attend + manage_comments） | 每日签到保全勤、回复评论维护粉丝 |

---

## 常见问题

- **作者后台接口报凭证错误**：更新 `fanqienovel_auth.json`（F12 → Network → 复制 Cookie/msToken/a_bogus/secsdk_token）
- **短剧接口返回空**：检查域名是否为报告所列 6 个之一；检查公共参数齐全
- **帮助中心 article 接口返回 -100**：该分类无文章（用 `tree` 找叶子分类再查）
- **教程列表报"超出列表最大值"**：`page_index` 从 0 开始且不能超过 `total_count/page_count - 1`
- **收益接口报 -2 参数有误**：未走加密通道，确认 `npm install` 已执行且用 `api_client.py` 的封装函数

---

## 附录：目录结构

```
site-fanqie/
├── SKILL.md                              # 本文件（统一入口+模块路由）
├── fanqienovel_auth.json                 # 模块A凭证（独立文件，过期只改这里）
├── package.json / package-lock.json      # Node 依赖（收益加密）
├── node_modules/                         # crypto-js + bignumber.js
├── publish_result.json                   # 最近一次发布结果
├── scripts/                              # 三模块脚本平铺（路径依赖：scripts/上一级=技能根）
│   ├── [模块A] api_client.py, query_chapters.py, query_stats.py,
│   │   query_chapter_stats.py, query_income.py, publish_chapter.py,
│   │   manage_comments.py, attend.py, modify_book.py, diagnose_book.py,
│   │   analyze_trends.py, fanqie_book_overview.py, fanqie_encrypt.js
│   ├── [模块B] fanqie_drama_rank.py, verify_domains.py
│   └── [模块C] helpcenter_query.py
└── references/
    ├── [模块A] analysis_report.md, writer_backend_api_report.md/.json,
    │          vm_code.js（⚠️ 勿移动，fanqie_encrypt.js 按相对路径引用）, main.e63907e3.js
    ├── [模块B] fanqie_drama_api_report.md
    └── [模块C] author_zone_helpcenter_report.md
```

> ⚠️ 目录结构约定：`fanqie_encrypt.js` 通过 `../references/vm_code.js` 相对路径引用 VM 代码；`api_client.py` 以 `scripts/` 上一级为技能根定位 `fanqienovel_auth.json` 与 `node_modules`。**新增脚本必须平铺在 `scripts/` 下，不要建子目录**。
