# 番茄小说作者后台 (fanqienovel.com) 分析报告

> 来源：DevTools 导出 curl 集合（112 条请求，27 个唯一接口）
> 分析时间：2026-08-05
> 凭证实测：Cookie + msToken + a_bogus 重放有效，书籍列表/统计接口均返回 200

## ⚠️ 修改书籍信息接口实测结论（2026-08-11 补充）

- **有效接口**：`POST /app/book/modify_book/v0/`（改完立即生效，book_detail 可验证）
- **❌ 无效接口**：`POST /api/author/book/modify_book/v0/` → 返回 `code=0` 但**静默假成功**（数据不变）
- **请求体字段**（逆向自前端 `main.e63907e3.js` 的 `ModifyBook` 方法）：
  `book_id / book_name / gender / category / thumb_uri / summary / gift_word / roles / is_self_pic / activity_id / special_judge / group_category_id`
- **🔴 简介字段名是 `summary`，不是 `abstract`**（传 abstract 会被忽略）
- **🔴 签约书不可修改分类**：传 `category` 报 `code=-2020"已签约作品不可修改分类"`；签约书改简介/书名时**不要传 category**
- **🔴 简介有字数校验**：过短报 `code=-2003"简介字数不符合要求"`（约 150~300 字）
- **支持部分更新**：只传 `book_id` + 需要改的字段即可
- 工具：`scripts/modify_book.py`（CLI，含 --show/--summary/--name/--gift-word）

## 一、基本信息

| 项 | 值 |
|----|----|
| 站点 | 番茄小说作者后台（番茄作家助手 Web 版） |
| 域名 | https://fanqienovel.com |
| 前端版本 | `release: 1.0.0.9871`，`commit_hash: 465d28db` |
| 应用标识 | `aid=2503`、`app_name=muye_novel` |
| 技术栈 | Vue + Arco Design，字节跳动系标准接口体系 |
| 核心功能 | 书籍管理、章节管理、发布章节、数据统计、写作助手 |

## 二、鉴权流程

### 1. Cookie 鉴权（必需）

| Cookie | 作用 |
|--------|------|
| `sid_guard` / `sid_tt` / `sessionid` | 登录会话，约 60 天有效 |
| `uid_tt` / `uid_tt_ss` | 用户 ID |
| `passport_csrf_token` / `csrf_session_id` | CSRF 令牌 |
| `odin_tt` / `n_mh` | 设备指纹（风控） |
| `ttwid` | 设备唯一标识 |
| `s_v_web_id` | 滑块验证标识 |

### 2. 签名参数（两套并存）

**A. `msToken` + `a_bogus`（查询参数）** — `/api/author/*` 和 `/api/node/*` 接口：
- `msToken`：会话内固定，URL-encoded
- `a_bogus`：每请求变化的风控签名，与 UA/时间戳/路径相关，一次性复用有效

**B. `x-secsdk-csrf-token`（请求头）** — 写操作接口（correction / pre_audit_article / publish_article / get_speak_popup）。

### 3. 请求头规范

```
accept: application/json, text/plain, */*
content-type: application/x-www-form-urlencoded;charset=UTF-8  (POST)
origin: https://fanqienovel.com
referer: https://fanqienovel.com/main/writer/...
user-agent: Mozilla/5.0 ... Chrome/150.0.0.0
```

## 三、API 接口清单

> 统一前缀 `https://fanqienovel.com`；公共参数 `aid=2503&app_name=muye_novel`

### 账号与状态
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/author/verify/check_user_status/v0` | 校验登录状态 |
| GET | `/api/author/account/info/v0/` | 账号信息 |
| GET | `/app/node/data/server/time` | 服务器时间 |
| GET | `/app/node/config/author/level_config/v2/` | 作家等级配置 |
| GET | `/reading/msgapi/getnewmsgcount/v0/` | 新消息数 |

### 书籍管理
| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/author/book/book_list/v0` | `page_count, page_index, image_fmt_list` | 书籍列表 |
| GET | `/api/author/book/book_detail/v0/` | `book_id, image_fmt_list` | 书籍详情 |
| GET | `/api/author/homepage/book_list/v0/` | `page_count, page_index` | 首页书籍列表 |
| GET | `/api/author/volume/volume_list/v1` | `book_id` | 卷列表 |
| GET | `/api/author/banned/info/v0/` | `book_id, type` | 封禁/违规信息 |

### 章节管理
| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/author/chapter/chapter_list/v1` | `book_id, page_index, page_count, status, volume_id, ...` | 章节列表 |

### 写作 / 发布（POST，需 x-secsdk-csrf-token）
| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/app/book/pre_audit_article/v0/` | `item_id, content(HTML), pre_audit_type` | 发布前预审 |
| POST | `/api/author/article/get_speak_popup/v0/` | `item_id, content` | 章节弹窗信息 |
| POST | `/app/node/editor/correction/v0/` | `text, item_id` | 错别字/语病纠错 |
| POST | `/api/author/publish_article/v0/` | 见发布章节 | 发布/更新章节 |
| POST | `/api/node/editor/typo_backflow` | - | 错别字反馈回流 |
| POST | `/app/home/message/book_problem_mark_info_read_mark/v0` | - | 问题标记已读 |

### 数据统计
| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/author/stats/book_list/v0/` | `page_count, page_index` | 统计书籍列表 |
| GET | `/api/author/stats/book_common_v1/v0/` | `book_id, stats_type` | 书籍通用统计 |
| GET | `/api/author/stats/book_increase_v2/v0/` | `book_id, start_date, end_date, stats_types` | 趋势增长统计 |
| GET | `/api/author/stats/chapter_list_v1/v0/` | `book_id, latest_count, ...` | 章节维度统计 |
| GET | `/api/author/hot_word/word_list/v0` | `gender, type, set_read_time` | 热门关键词 |
| GET | `/api/author/short_article/list/v0/` | `pack_type, ...` | 短篇作品列表 |

### 统计参数说明
- `start_date`/`end_date`：**秒级时间戳**
- `stats_types`：逗号分隔数字 ID（示例 `24,27,26,25,28,29`）

## 四、核心写操作：发布章节

### `POST /api/author/publish_article/v0/`

请求体字段：
```
aid=2503  app_name=muye_novel
item_id=章节ID  book_id=书籍ID  volume_id=卷ID  volume_name=卷名
title=章节标题  content=<p>HTML正文</p>  publish_status=1
need_pay=0  timer_status=0  timer_time=  timer_chapter_preview=[]
speak_type=0  use_ai=2  has_chapter_ad=false  chapter_ad_types=  device_platform=pc
```

### 发布流程
```
① GET /api/author/book/book_list/v0       → book_id
② GET /api/author/volume/volume_list/v1   → volume_id
③ POST /app/node/editor/correction/v0     → 纠错（可选）
④ POST /app/book/pre_audit_article/v0/    → 预审
⑤ POST /api/author/publish_article/v0/    → 发布
```

## 五、页面路由

| 路由 | 功能 |
|------|------|
| `/main/writer/book-manage` | 作品管理 |
| `/main/writer/chapter-manage/{book_id}&{title}?type=1` | 章节管理 |
| `/main/writer/{book_id}/publish/{item_id}` | 章节编辑器/发布页 |
| `/main/writer/data?bookId={book_id}` | 数据统计页 |

## 六、第三方域名（非业务）

| 域名 | 用途 |
|------|------|
| `mcs.zijieapi.com/list` | 埋点上报 |
| `mon.zijieapi.com/monitor_browser/collect/batch/` | 性能监控 |
| `security.zijieapi.com/api/metrics/emit` | 风控 SDK 指标 |

## 七、实测验证记录

| 接口 | 结果 |
|------|------|
| GET `/api/author/book/book_list/v0` | 200，返回 7 本书 |
| GET `/api/author/stats/book_increase_v2/v0/` | 200，返回 7 维度 × 7 天 `data_list` |

### 书籍可见/签约阶段实测（2026-08-06）

`book_list` 返回的 `book_intro.status` 是判断书籍可见阶段的关键字段，各阶段实测值：

| book_intro.status | tag | 出现条件 | 实测书 |
|-------------------|-----|---------|--------|
| `book_initial_without_audit` | 发布章节 | 未发章节的空书 | 魂穿西游、令红辰第6本（0字） |
| `book_auth_not_safe` | 不可搜 | **已发章节但 <2万字 未签约** | 末世七日灰潮（8802字，verify_status=4） |
| `cold_start_init` | 加油写作 | 已签约未到推流字数（message 提示还差X万） | 直播显圣（3.3万字） |
| `cold_start_ing` | 推荐中 | 签约且正常推荐 | 女帝、伊朗、学霸 |

**平台规则（官方作家专区确认）**：字数达到 2万/5万/8万字各有 1 次签约申请机会；签约后作品可被搜索但不推流；8万字开启首次推流。

**关键结论（避免误判）**：
- `book_auth_not_safe` = 未签约新书正常阶段，**≠ 内容违规**（其 `security_status=1` 正常）；
- 未签约新书 `can_recommend=0`、`origin_level=C`、`risk_rate=6` 属初始档位，**勿当成数据问题**；
- `get_banned_info` 返回 `book_permission.can_modify=0` 只是不可修改的通用限制，需结合 `book_intro` 综合判断，不能单独判定封禁。

## 八、注意事项

1. `a_bogus` 与请求参数、时间戳、UA 强绑定，一次性复用有效
2. 写操作必须带 `x-secsdk-csrf-token`，否则 CSRF 校验失败
3. 统计接口时间用秒级时间戳
4. `content` 为 HTML 格式，需 URL 编码
5. Cookie 过期（`sid_guard` 含有效期）后需重新抓取
