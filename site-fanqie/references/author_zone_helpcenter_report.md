# 番茄小说作者后台（创作中心）操作手册

> 分析时间：2026-08-25
> 分析页面：
> - 帮助中心文章：`https://fanqienovel.com/writer/zone/help/article?rank1=10000&rank2=10091&rank3=0`
> - 作家课堂教程：`https://fanqienovel.com/writer/zone/tutorial?enter_tutorial=class_zone`
> 文档用途：**直接按本手册调用接口，无需重新分析**

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 站点 | 番茄小说作者后台（serial-author-zone，创作中心） |
| 前端框架 | React + Webpack 5（代码分割）+ React Router loader（SSR） |
| UI 库 | Arco Design |
| API 基础域名 | `https://fanqienovel.com`（相对路径直接拼接主站） |
| 数据流 | SSR 注入 `window._ROUTER_DATA`（首屏数据）+ 前端异步调 API |
| 反爬 | argus 反调试上报（`mon.zijieapi.com`），不影响 API 调用 |

**页面数据流**：
- 首屏数据由服务端渲染直接注入 HTML：`window._ROUTER_DATA.loaderData["help.(type$)/page"]` / `["tutorial/page"]`
- 前端交互（切分类、翻页、搜索）再调 API

---

## 二、核心接口（帮助中心 / 作家课堂，无需登录）

### 1. 帮助中心分类树
```
GET https://fanqienovel.com/api/author/hfc/all_category/v0/
```
响应：`{"code":0,"data":[{category_id, title, icon_url, index, parent_id, rank, child_category:[...]}]}`
- 三级分类结构：rank1（如 10000）→ rank2（如 10091）→ rank3（如 10119）
- URL 参数 `rank1/rank2/rank3` 即各级 `category_id`，`0` 表示无下级

### 2. 帮助中心文章详情
```
GET https://fanqienovel.com/api/author/hfc/article_info/v0/?category_id={category_id}
```
参数：
- `category_id`：必填，分类 id（三级叶子分类才有文章）

响应：`{"code":0,"data":{category_id, item_id, title, content, modify_time}}`
- `content` 为 HTML 富文本（含 h2/h3 标题、列表、图片等），`modify_time` 为秒级时间戳

### 3. 帮助中心文章搜索
```
GET https://fanqienovel.com/api/author/hfc/search_article/v0/?query={关键词}&page_index=1&page_count=10
```
参数：
- `query`：搜索关键词
- `page_index`：页码，从 1 开始
- `page_count`：每页条数（前端用 10）

响应：`{"code":0,"data":{"search_list":[{category_id, item_id, title_highlight, content_highlight, parent_category:{"1":"10189","2":"10192","3":"10198"}, status}]}}`
- `parent_category` 的 1/2/3 即 rank1/rank2/rank3 分类 id，可拼 URL：`/help/article?rank1={1}&rank2={2}&rank3={3}`

### 4. 作家课堂教程列表
```
GET https://fanqienovel.com/api/node/tutorial/list?type={type}&page_index=0&page_count=15
```
参数：
- `type`：tab 类型（枚举见下）
- `page_index`：页码，**从 0 开始**（超出返回 `code:-1 超出列表最大值`）
- `page_count`：每页条数（前端用 15）

响应：`{"data":{"total_count":28,"tutorial_list":[{title, detail:[...], cover_uri, link, time, type, is_video}]}}`
- `link` 指向 `https://fanqienovel.com/writer/zone/article/{item_id}`（文章详情页）

**type 枚举**（来自前端模块 16046 `_2`）：

| type | 名称 | 说明 |
|------|------|------|
| 1 | Beginner | 新手专区 |
| 2 | AuthorInterview | 大神专访 |
| 3 | WriteSkill | 写作技巧 |
| 4 | ClassifyAdvance | 品类指南 |
| 5 | LivePreview | 平台宝典（默认 tab） |

---

## 三、周边接口

| 方法 | 路径 | 说明 | 登录要求 |
|------|------|------|----------|
| GET | `/api/author/hfc/get_feedback_stat/v0/` | 反馈状态统计 | ❌ 需登录（code:-3 登录信息有误） |
| POST | `/api/author/hfc/set_feedback_stat/v0/` | 设置反馈状态（body: `status=1/2`） | ❌ 需登录 |
| POST | `/api/author/growth_task/scene/v0` | 场景上报（body: `scene_type=10001`，进课堂页时调用） | 无需登录 |
| GET | `/api/node/notice/list` | 公告列表（需 `page_index` + `location` 参数） | 未测出完整参数 |
| GET | `/api/writer/stats` | 作家数据统计 | 需登录 |
| GET | `/api/node/banner/list` | Banner 列表 | 未验证 |
| GET | `/api/node/hot_course/list` | 热门课程 | 未验证 |
| GET | `/api/node/changelog/list` | 更新日志 | 未验证 |

**登录态接口通用响应**：`{"code":-3,"message":"登录信息有误"}` 表示未登录

---

## 四、页面路由与参数

| 路由 | 参数 | 功能 |
|------|------|------|
| `/writer/zone/help/article` | `rank1` `rank2` `rank3`（分类 id，0=无） | 帮助中心文章页 |
| `/writer/zone/help` | - | 帮助中心（分类列表） |
| `/writer/zone/help/search?key=xxx` | `key` | 帮助中心搜索结果页 |
| `/writer/zone/tutorial` | `tab`（1-5，可选）、`enter_tutorial`（来源） | 作家课堂 |
| `/writer/zone/article/{item_id}` | - | 文章详情（教程/公告正文） |

帮助中心 URL 生成规则：`/help/article?rank1={一级}&rank2={二级}&rank3={三级}`，点击左侧菜单时前端自动填充，不足三位用 `0` 补齐。

---

## 五、鉴权说明

- **只读接口（分类树/文章详情/搜索/教程列表）无需任何凭证**，直接 GET 即可
- 需要登录态的接口：携带浏览器 Cookie（`sessionid` 等）即可，请求头无需额外 token
- 前端请求会自动附带公共参数（`device_platform`、`version_code` 等，来自公共参数函数），**实测不传也能正常返回**
- 建议请求头带完整 UA 和 `Referer: https://fanqienovel.com/writer/zone/help`，规避风控

---

## 六、可直接调用的操作清单

| 操作 | 调用 |
|------|------|
| 获取帮助中心全部分类 | `GET /api/author/hfc/all_category/v0/` |
| 获取某分类文章 | `GET /api/author/hfc/article_info/v0/?category_id={id}` |
| 搜索帮助文章 | `GET /api/author/hfc/search_article/v0/?query={kw}&page_index=1&page_count=10` |
| 获取新手专区教程 | `GET /api/node/tutorial/list?type=1&page_index=0&page_count=15` |
| 获取大神专访 | `GET /api/node/tutorial/list?type=2&page_index=0&page_count=15` |
| 获取写作技巧 | `GET /api/node/tutorial/list?type=3&page_index=0&page_count=15` |
| 获取品类指南 | `GET /api/node/tutorial/list?type=4&page_index=0&page_count=15` |
| 获取平台宝典（默认） | `GET /api/node/tutorial/list?type=5&page_index=0&page_count=15` |
| 免 API 抓首屏数据 | 直接抓页面 HTML，解析 `window._ROUTER_DATA` |

---

## 七、关键数据结构

### 分类树节点
```json
{
  "category_id": "10000",
  "title": "创作问题",
  "icon_url": "",
  "index": 1,
  "parent_id": "0",
  "rank": 1,
  "child_category": []
}
```

### 教程条目
```json
{
  "title": "平台规则｜广场涨量实战！让读者讨论变成作品新增流量",
  "detail": ["适用对象：所有品类"],
  "cover_uri": "https://p3-novel.byteimg.com/origin/novel-static/xxx",
  "link": "https://fanqienovel.com/writer/zone/article/7672323371945689150",
  "time": "2026-08-10",
  "type": 5,
  "is_video": 0
}
```

### 帮助文章
```json
{
  "code": 0,
  "data": {
    "category_id": "10091",
    "item_id": "7143064273269293070",
    "title": "平台作家福利",
    "content": "<blockquote>...HTML富文本...</blockquote>",
    "modify_time": 1724371200
  }
}
```

---

## 八、附录

### JS 文件清单（帮助中心页）
| 文件 | 大小 | 说明 |
|------|------|------|
| `main.3930c815.js` | 130KB | 主入口，含模块 39706（全部业务 API） |
| `page.e6402a97.js` | 28KB | help 页面 chunk（分类树/文章/搜索/反馈逻辑） |
| `page.a911d826.js` | 15KB | tutorial 页面 chunk（tab 切换/教程列表逻辑） |
| `434.72c71700.js` | 2.3MB | passport 登录/账号库（业务无关） |
| `lib-axios.5a75a5df.js` | 39KB | axios 封装 |

### 模块映射（main.3930c815.js 模块 39706）
| 导出名 | 内部变量 | 接口 |
|--------|----------|------|
| `nI` | F | `/api/author/hfc/all_category/v0/` |
| `B2` | W | `/api/author/hfc/article_info/v0/` |
| `xA` | K | `/api/author/hfc/search_article/v0/` |
| `ER` | $ | `/api/author/hfc/set_feedback_stat/v0/` |
| `vl` | I | `/api/node/tutorial/list` |
| `n7` | X | `/api/author/growth_task/scene/v0` |

### 教程 tab 配置（模块 19566 `M_`）
```js
[
  {key: 5, name: "平台宝典"},
  {key: 1, name: "新手专区"},
  {key: 4, name: "品类指南"},
  {key: 3, name: "写作技巧"},
  {key: 2, name: "大神专访"}
]
```

### 测试记录
- 2026-08-25 实测：分类树/文章详情/搜索/教程列表接口全部 200 无凭证可用
- `article_info/v0/` 用 `item_id` 参数返回 `-100 无文章`（教程正文页走其他数据通道，未展开）
- `get_feedback_stat` / `set_feedback_stat` 需登录 Cookie
