# 语雀 API 参考文档

> 基于 web-reverse-engineer 技能逆向分析生成

## 鉴权方式

语雀 Web API 使用 **Cookie + CSRF Token** 方式鉴权。

### 必需凭证

| 凭证 | 来源 | 用途 |
|------|------|------|
| `Cookie` | 登录后浏览器 Cookie 全部内容 | 身份认证，需包含 `_yuque_session` |
| `x-csrf-token` | Cookie 中的 `yuque_ctoken` 值 | CSRF 防护，写操作必带 |
| `x-login` | 用户 login 名（如 `your-login`） | 标识当前用户 |

### 标准请求头

```
Cookie: {完整cookie}
x-csrf-token: {yuque_ctoken值}
x-login: {用户login}
X-Requested-With: XMLHttpRequest
Content-Type: application/json
```

---

## 一、用户信息

### GET /api/mine
获取当前登录用户信息。

**响应字段**: id, login, name, avatar_url, email, description, books_count, topics_count, followers_count, following_count, member_level 等

### GET /api/mine/books
获取我的知识库列表。

**响应**: `data` 为数组，每项含 id, name, slug, type, public, description, user

### GET /api/mine/groups
获取我的组列表。

### GET /api/mine/personal_books
获取个人知识库（不含协作）。

### GET /api/mine/collaborate_books
获取协作知识库。

### GET /api/mine/book_stacks
获取知识库栈。

### GET /api/mine/collaborations
获取协作列表。

### GET /api/mine/common_used
获取常用内容。返回 `{groups: [], books: []}`

### GET /api/mine/recycles
获取回收站。返回 `{data: [], total: number}`

### GET /api/mine/user_settings
获取用户设置。

### GET /api/mine/organizations
获取组织列表。

---

## 二、知识库操作

### GET /api/books/{book_id}/docs
获取知识库的文档列表（分页）。

**参数**: `offset` (默认0), `limit` (默认20, 最大?)

**响应字段**: id, title, slug, book_id, format, word_count, status, public, description, created_at, updated_at, published_at, user, last_editor

**注意**: 返回的文档**不包含 body 字段**，需单独获取。

### GET /api/books/{book_id}/toc
获取知识库的目录结构。

**响应**: `{toc: [...], docs: [...]}`

**TOC节点字段**: type(TITLE/DOC), title, uuid, url, level, doc_id, parent_uuid, child_uuid, sibling_uuid, visible, open_window

### GET /api/catalog_nodes?book_id={book_id}
获取目录节点列表。

---

## 三、文档操作

### GET /api/docs/{doc_id_or_slug}?book_id={book_id}
获取文档详情。

**关键参数**:
- `book_id` - **必需**，知识库ID
- `mode` - `edit` 返回 body，`read` 不返回 body

**mode=read 返回字段**: id, title, slug, book_id, format, word_count, status, public, description, body_asl, abilities, meta 等（**不含body**）

**mode=edit 返回字段**: 上述所有 + `body`, `body_draft`, `body_draft_asl`, `collab`, `locker`, `contributors` 等

**body格式**: HTML格式，包裹在 `<div class="lake-content">` 中

### POST /api/docs
创建新文档。

**请求体**: `{book_id, title, slug?, format:"lake", body?}`

**响应**: 返回创建的文档信息(id, title, slug等)

### PUT /api/docs/{doc_id}
更新文档。

**请求体**: `{book_id, title?, body?, ...}`

**注意**: 更新时只传需要修改的字段，但 book_id 必传。

**重要**: 此接口只更新 `body`（已发布内容），不更新 `body_draft`（编辑器草稿）。语雀前端渲染优先使用 `body_draft`，所以仅用此接口更新后，网页端可能看不到新内容。需配合 content 接口使用。

### PUT /api/docs/{doc_id}/content
更新文档内容（含草稿），这是语雀编辑器保存时使用的接口。

**请求体**:
```json
{
  "format": "lake",
  "body_asl": "<ASL内容>",
  "body_draft_asl": "<ASL内容>",
  "save_type": "user",
  "draft_version": <number>
}
```

**必需字段**:
- `format` - 固定为 `"lake"`
- `body_asl` - 文档内容，**必须是 ASL 格式**（不是 HTML！见下方说明）
- `save_type` - `"user"`（手动保存）或 `"auto"`（自动保存）
- `draft_version` - 当前草稿版本号，需先通过 `GET /api/docs/:id?mode=edit` 获取

**可选字段**:
- `body_draft_asl` - 草稿内容（通常与 body_asl 一致）

> ⚠️ **body_asl ≠ HTML（踩坑记录）**
>
> 语雀文档有两套内容字段，格式完全不同：
>
> | 字段 | 格式 | 特征 |
> |------|------|------|
> | `body` / `body_draft` | HTML | `class="ne-p"`、`class="ne-text"` |
> | `body_asl` / `body_draft_asl` | **ASL** | 每个元素带 `data-lake-id="uXXXX"` |
>
> 如果把 `body`（HTML）直接塞进 `body_asl` 提交，语雀会按 ASL 语法容错解析，导致：
> - 折叠块 `<details class="lake-collapse"><summary></summary><p>内容</p></details>` 被改写成 `<details><summary>内容</summary></details>` —— **summary 被填满，视觉上从「折叠」变「展开」**
> - 其他复杂结构（画板、PlantUML 等）也可能变形
>
> **正确做法**：用 `md2asl` 生成 ASL，或取 `body_asl` 原样做局部替换后再提交。

**注意**: 此接口更新 `body_asl` / `body_draft_asl`，语雀会据此同步前端与已发布内容。

### DELETE /api/docs/{doc_id}
删除文档。

**请求体**: `{book_id}`

### POST /api/docs/{doc_id}/export
触发文档导出任务（导出弹窗点「导出」时调用）。

**请求体**:
```json
{
  "type": "markdown",
  "force": 0,
  "options": "{\"latexType\":2,\"enableAnchor\":1,\"enableBreak\":1,\"useMdai\":1}"
}
```

**说明**: `type` 支持 `markdown` / `pdf` / `docx` 等；`force:0` 表示有缓存则复用。

### GET /{user}/{book_slug}/{doc_slug}/markdown
**下载原生 Markdown**（导出后点「下载」时调用），返回完整 Markdown 纯文本。

**参数**:
- `attachment=true` - 附件以链接形式导出
- `latexcode=true` - LaTeX 公式保留为代码
- `anchor=true` - 保留锚点
- `linebreak=true` - 保留换行
- `useMdai=true` - 启用 MdAI

**注意**:
- URL 中的 doc 段用的是 **slug**（不是 doc_id），需先通过 `GET /api/docs/{doc_id}?mode=edit` 取 `slug`
- 私有文档需携带 Cookie
- 返回为纯文本（非 JSON），可直接保存为 `.md`
- 导出结果保留 `<font style="...">` 等样式标签与图片 OCR 注释

---

## 四、搜索

### GET /api/zsearch?q={keyword}&type={type}
全局搜索。

**参数**:
- `q` - 搜索关键词
- `type` - **必需**，搜索类型: `doc`(文档) 或 `book`(知识库)
- `bookId` - 可选，限定知识库范围

**响应**: `{type, hits: [...], totalHits, numHits}`

**hit字段**: id, title, slug, type, url, abstract, book_name, group_name, privacy

---

## 五、文档版本

### GET /api/doc_versions?doc_id={doc_id}&doc_type=Doc&offset={n}&limit={n}
获取文档版本历史（按时间倒序，最新版本在最前）。

**参数**:
- `doc_id` - 文档 ID（数字，必传）
- `doc_type` - 固定 `Doc`
- `offset` / `limit` - 分页，`limit=200` 可一次取全（实测某文档 30 个版本全量返回）

**响应字段**: id, doc_id, title, user_id, user{login,name,avatar}, draft, created_at, name, origin, isReleased, publication_status

**实测**（2026-09）：未带分页参数时同样返回全部版本；`user.login` 即作者登录名。

### GET /api/doc_versions/{version_id}?doc_id={doc_id}
获取单个历史版本的完整内容。

**响应 `data` 字段**:
- `id` / `doc_id` / `doc_type` / `format` / `originFormat` / `slug` / `title` / `user_id` / `user`
- **`content`** - 语雀 ASL 原文（`<!doctype lake><meta name="doc-version" ...>` 开头）
- **`content_html`** - 渲染后的 HTML（`<div class="lake-content">` 包裹）
- `created_at` / `word_count` / `draft` / `marked` / `origin` / `doc_dynamic_data`

**关键结论（已实测验证）**：版本 `content` 与文档 `GET /api/docs/:id?mode=edit` 返回的 `body_asl` **完全同构**（同一文档同一版本两者字符串相等）。
因此 **回滚 = 取版本 `content` → 经 `PUT /api/docs/:id/content` 写回 `body_asl` / `body_draft_asl`**，无需额外的还原接口，且回滚本身会生成新版本（可逆）。

**限制**: 表格（`lakesheet`）/ 画板（`lakeboard`）文档无正文，`content` 为空。

### PUT /api/docs/{doc_id}/lock  body: {"uuid":"..."}
前端进入「历史版本 / diff」视图时锁定文档，防止他人并发编辑。

**说明**: 这是 UI 行为，**本 skill 的版本读写不需要调用它**（`restore-version` 直接走 content 接口，与 `update-doc` 同一条已验证链路）。如需锁定，`uuid` 取自编辑器当前会话。

---

## 六、目录节点操作

### POST /api/catalog_nodes
创建目录节点。

### PUT /api/catalog_nodes/{id}
更新目录节点。

### DELETE /api/catalog_nodes/{id}
删除目录节点。

### PUT /api/catalog_nodes/move
移动目录节点。

### PUT /api/catalog_nodes/publish_doc
发布文档到目录。

---

## 七、收藏

### GET /api/mine/marks/{target_id}?target_type=Book
获取收藏状态。

**响应**: `{markAction, marked}`

---

## 八、其他API

### 文档操作
- `POST /api/docs/copy` - 复制文档
- `POST /api/docs/move` - 移动文档
- `POST /api/docs/convert` - 转换文档格式
- `POST /api/docs/restore` - 恢复已删除文档
- `POST /api/docs/batch_private` - 批量设为私有
- `POST /api/docs/add_to_catalog` - 添加到目录
- `POST /api/docs/share_to_personal_feed` - 分享到动态

### 资源操作
- `GET /api/resources?book_id={id}` - 获取资源列表
- `POST /api/resources` - 创建资源
- `POST /api/resources/store` - 上传资源
- `POST /api/resources/copy` - 复制资源
- `POST /api/resources/move` - 移动资源

### 编辑器
- `GET /api/editor/search` - 编辑器内搜索
- `GET /api/editor/recent` - 最近编辑
- `GET /api/editor/link_detail` - 链接详情

### 评论
- `GET /api/comments?target_type=Book&target_id={id}` - 获取评论

---

## 九、已知限制

1. **v2 API** (`/api/v2/...`) 需要 OAuth Token，Cookie 方式无法访问
2. **文档内容** 只有 `mode=edit` 才返回 body，`mode=read` 不返回
3. **知识库详情** 没有独立的 API 获取知识库元信息（如 name/description），需从 mine/books 获取
4. **namespace** 格式为 `{user_login}/{book_slug}`，但 API 主要用 `book_id`（数字）
5. **分页** 文档列表默认每页20条，需用 offset+limit 翻页
6. **body vs body_draft** 语雀有两套存储：`PUT /api/docs/:id` 只更新 `body`（已发布），`PUT /api/docs/:id/content` 更新 `body_draft`（编辑器草稿）。前端渲染优先用 `body_draft`，更新文档必须两个接口配合使用
7. **content 接口需要 draft_version** `PUT /api/docs/:id/content` 需要传 `draft_version` 字段（从 `GET /api/docs/:id?mode=edit` 获取），否则返回 400
