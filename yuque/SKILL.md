---
name: yuque
description: |
  语雀(Yuque)知识库操作技能。自动获取和管理用户语雀空间的文档、知识库信息，支持搜索、创建、编辑、删除文档等操作。
  当用户提到"语雀"、"yuque"、"知识库文档"、"查看我的语雀"、"语雀文档"、"语雀知识库"、"yuque文档"、"语雀笔记"、"编辑语雀"、"更新语雀文档"时触发此技能。
  也适用于用户想查看、搜索、创建、编辑、删除语雀文档的任何场景，即使用户没有明确提到"语雀"但上下文暗示在操作语雀平台。
---

# 语雀知识库操作技能

通过语雀 Web API 实现知识库和文档的自动化操作，包括查看、搜索、创建、编辑、删除等功能。

> 目标：让 Agent 能稳定区分“用户自己的文档”和“语雀公开搜索”，并在读写大文档、局部编辑、Windows 环境下可靠执行。

## 前置条件

使用前需要配置语雀凭证。脚本读取顺序为：**环境变量优先**，其次读取本文档所在目录下的 `credentials.json`。

需要包含以下信息：

1. **Cookie** - 登录语雀后浏览器的完整 Cookie 字符串
2. **CSRF Token** - 即 Cookie 中 `yuque_ctoken` 的值
3. **用户 Login** - 语雀用户名（如 `your-login`）

### 凭证配置方式

配置方式由用户决定，脚本同时支持以下两种方式；如果两者都存在，**环境变量优先**。

**方式一：环境变量**（适合临时会话、CI/CD 或不想把凭证落盘的场景）

- `YUQUE_COOKIE`
- `YUQUE_CSRF_TOKEN`
- `YUQUE_X_LOGIN`

**方式二：credentials.json 文件**（适合本地长期使用）

在 skill 目录下创建 `credentials.json`：

```json
{
  "cookie": "完整cookie字符串",
  "csrf_token": "yuque_ctoken值",
  "x_login": "用户login"
}
```

**获取凭证步骤**：

1. 浏览器登录 yuque.com
2. F12 → Network → 刷新页面
3. 找任意请求 → 复制 Request Headers 中的 Cookie 值
4. 从 Cookie 中提取 `yuque_ctoken` 的值作为 CSRF Token
5. 用户 login 在请求头的 `x-login` 字段中

---

## Agent 执行规范

1. **先验证凭证**：首次操作或遇到异常时，先执行 `whoami`。
2. **拿到文档 URL 先用 `resolve-url`**：当用户给出语雀文档链接（形如 `https://www.yuque.com/<user>/<book>/<doc>`）时，**第一步**就用 `resolve-url <url>` 一次性拿到 `book_id`、`doc_id`、`format`，不要再反复 `list-books` / `list-docs` 试探定位。
3. **找用户自己的文档**：没有 URL 时，优先用 `find-docs <keyword>` 在用户自己的知识库中查找；不要用 `search`，它是全站公开搜索。
4. **搜索公开内容**：只有用户明确要搜语雀公开资料时，才使用 `search`。
5. **读取正文**：`get-doc` 必须使用 `mode=edit`，否则拿不到 `body`。
6. **大文档读取**：优先使用 `--body-only --output-file`，避免 Windows 管道或 JSON 输出过大失败。
7. **整篇更新**：长内容先写入 HTML 文件，再用 `update-doc --body-file`。
8. **局部更新**：优先用 `get-doc-outline` 定位标题，再用 `replace-section` 只替换目标 section。
9. **删除文档**：属于破坏性操作，必须先向用户确认目标文档标题、`doc_id` 和 `book_id`。
10. **凭证失效**：返回 `401/403` 时，提示用户重新获取 Cookie 和 `yuque_ctoken`。
11. **表格/画板文档限制**：`format` 为 `lakesheet`（表格）或 `lakeboard`（画板）的文档，`body` 通过本 API 返回为空，无法用 `get-doc` / `get-doc-outline` / `replace-section` 读写正文。遇到此类文档应直接告知用户该限制，`resolve-url` 会用 `is_sheet` / `is_board` 标记出来。

---

## 核心操作

### 0. 由文档 URL 直接定位（强烈推荐的入口）

```bash
python {skill_dir}/scripts/yuque_client.py resolve-url <url>
```

输入语雀文档链接（`https://www.yuque.com/<user>/<book>/<doc>`），一步返回：

- `book_id` / `book_name` — 所在知识库
- `doc_id` / `doc_title` — 文档 ID 和标题
- `format` — 文档格式（`lake` 普通文档 / `lakesheet` 表格 / `lakeboard` 画板）
- `is_sheet` / `is_board` / `has_body` — 便于判断能否读写正文
- `word_count` — 字数

**当用户给出文档网址时，先调用它拿到 `doc_id` 和 `book_id`，再执行后续读写操作，避免反复 `list-books` / `list-docs` 试探。**

### 1. 获取用户信息

先用脚本确认凭证有效：

```bash
python {skill_dir}/scripts/yuque_client.py whoami
```

返回用户名、ID、知识库数量等基本信息。

### 2. 获取知识库列表

```bash
python {skill_dir}/scripts/yuque_client.py list-books
```

返回所有知识库的 id, name, slug, type 等。**记录目标知识库的 id 用于后续操作。**

### 3. 获取知识库文档列表

```bash
python {skill_dir}/scripts/yuque_client.py list-docs <book_id> [offset] [limit]
```

- `book_id` - 知识库ID（数字）
- `offset` - 偏移量，默认0
- `limit` - 每页数量，默认20

### 快捷：在用户自己的所有知识库中查找文档

```bash
python {skill_dir}/scripts/yuque_client.py find-docs <keyword> [page_limit] [max_pages]
```

内部会自动遍历用户自己的所有知识库并分页匹配文档 `title` / `slug` / `description`，返回匹配文档的 `doc_id`、`book_id`、知识库名称等信息。

- `keyword` - 标题、slug 或描述中的关键词
- `page_limit` - 每页拉取数量，默认100，最大100
- `max_pages` - 每个知识库最多分页次数，默认50

### 4. 获取知识库目录结构

```bash
python {skill_dir}/scripts/yuque_client.py get-toc <book_id>
```

返回 TOC 树形结构和文档列表，可展示知识库的完整目录。

### 5. 获取文档详情（含内容）

```bash
python {skill_dir}/scripts/yuque_client.py get-doc <doc_id_or_slug> <book_id> edit
```

**关键**: 必须传 `mode=edit` 才能获取文档 body 内容。`mode=read` 不返回 body。

文档 body 格式为 HTML，包裹在 `<div class="lake-content">` 中。

### 6. 搜索文档

```bash
python {skill_dir}/scripts/yuque_client.py search <keyword> [type]
```

- `keyword` - 搜索关键词
- `type` - `doc`(文档, 默认) 或 `book`(知识库)

⚠️ **注意：`search` 是语雀全站公开搜索，会返回所有用户的公开文档。当用户要找自己的文档时，不要用 `search`，应使用 `find-docs`。**

### 7. 创建文档

```bash
python {skill_dir}/scripts/yuque_client.py create-doc <book_id> <title> [slug] [body]
```

- `book_id` - 知识库ID
- `title` - 文档标题
- `slug` - 可选，URL友好标识
- `body` - 可选，文档内容（HTML格式）

### 8. 更新文档

```bash
python {skill_dir}/scripts/yuque_client.py update-doc <doc_id> <book_id> [title] [body]
```

**长内容推荐用 `--body-file` 从文件读取**（避免命令行长度限制）：

```bash
python {skill_dir}/scripts/yuque_client.py update-doc <doc_id> <book_id> "新标题" --body-file /path/to/body.html
```

- 传入需要修改的字段，未传的字段保持不变
- `book_id` 必传
- `--body-file` 可以放在 title 之前或之后，脚本会自动识别
- **内部机制**：脚本会通过 `/api/docs/:id/content` 接口同步更新 `body_draft`（语雀前端渲染依赖此字段），再通过 `/api/docs/:id` 更新已发布的 `body`，确保网页端立即可见

### 9. 删除文档

```bash
python {skill_dir}/scripts/yuque_client.py delete-doc <doc_id> <book_id>
```

**谨慎操作**，删除后文档进入回收站。

### 10. 获取文档版本历史

```bash
python {skill_dir}/scripts/yuque_client.py get-doc-versions <doc_id>
```

---

## 推荐工作流

### 工作流1：浏览知识库内容

```
1. whoami → 确认凭证有效
2. list-books → 找到目标知识库 id
3. get-toc <book_id> → 查看目录结构
4. list-docs <book_id> [offset] [limit] → 获取文档列表，必要时分页
5. get-doc <doc_id> <book_id> edit → 读取具体文档内容
```

### 工作流2：查找用户自己的文档

**当用户说“找我的文档”“看我的 XX 文档”“我的语雀里有篇……”等表达时，优先用 `find-docs`，不要用 `search`。**

```
1. find-docs <keyword> → 在用户自己的所有知识库中查找匹配文档
2. 从 matches 中确认目标文档的 doc_id 和 book_id
3. get-doc <doc_id> <book_id> edit → 读取具体文档内容
```

### 工作流3：局部编辑文档某一节（推荐）

**最常用的安全编辑方式：只替换目标 section，不触碰其它内容。**

```
1. get-doc-outline <doc_id> <book_id> → 查看文档标题层级
2. 准备新内容（Markdown 或 Lake HTML）
3a. Markdown：md2lake --input-file content.md --output-file section.html
3b. HTML：直接准备 section.html
4. replace-section <doc_id> <book_id> --heading "目标标题" --body-file section.html
```

### 工作流4：创建并更新整篇文档

```
1. list-books → 确认目标知识库 id
2. get-toc <book_id> → 查看当前目录，确定放置位置
3. create-doc <book_id> "文档标题" → 创建文档
4. md2lake --input-file content.md --output-file body.html → 将 Markdown 转为 Lake HTML
5. update-doc <doc_id> <book_id> "文档标题" --body-file body.html → 更新整篇内容
```

### 工作流5：搜索语雀公开文档

**仅当用户明确要搜索语雀平台上的公开内容（非自己知识库）时才使用 `search` 命令。**

```
1. search <keyword> → 全站搜索公开文档
2. 根据搜索结果判断是否需要继续读取详情
```

---

## 重要注意事项

1. **body 只在 mode=edit 时返回** - 这是语雀的设计，read 模式不返回文档内容
2. **book_id 必传** - 几乎所有文档 API 都需要 book_id 参数
3. **Cookie 会过期** - 如果返回 401/403，需要用户重新获取 Cookie
4. **文档内容是 HTML 格式** - 语雀的 lake 编辑器使用 HTML 格式，更新时需要保持格式一致
5. **分页** - 文档列表默认每页20条，知识库文档多时需要分页获取
6. **v2 API 不可用** - `/api/v2/` 路径需要 OAuth Token，Cookie 方式只能用 v1 API
7. **写操作需 CSRF Token** - POST/PUT/DELETE 操作必须携带有效的 x-csrf-token
8. **body vs body_draft** - 语雀有两套存储：`body`（已发布内容）和 `body_draft`（编辑器草稿）。前端渲染优先用 `body_draft`。本脚本的 `update-doc` 和 `replace-section` 已自动同步两者
9. **长内容用 --body-file** - 命令行参数有长度限制（Windows ~8000字节），长文档内容应先写入临时文件，用 `--body-file /path/to/file.html` 传入
10. **优先局部编辑** - 修改长文档时优先使用 `get-doc-outline` + `replace-section`，降低误覆盖整篇文档的风险

---

## API 详细参考

完整 API 文档在 `references/api_reference.md`，包含所有已验证的接口、请求格式、响应字段和已知限制。

## 脚本工具

| 脚本            | 路径                        | 用途                                |
| --------------- | --------------------------- | ----------------------------------- |
| yuque_client.py | `scripts/yuque_client.py` | 语雀 API 命令行客户端，支持所有操作 |

---

## 高级功能

### 11. 获取文档标题层级结构

```bash
python {skill_dir}/scripts/yuque_client.py get-doc-outline <doc_id> <book_id>
```

快速查看文档骨架，无需下载完整 body。输出纯文本层级结构。

### 12. 局部替换文档 section

```bash
python {skill_dir}/scripts/yuque_client.py replace-section <doc_id> <book_id> --heading "Questions" --body-file /path/to/new_section.html
```

按 heading 文本定位 section 边界（从该 heading 到下一个同级或更高级 heading），替换该区间内容。适合只改一节而不触碰其他内容。

### 13. Markdown 转 lake HTML

```bash
python {skill_dir}/scripts/yuque_client.py md2lake --input-file content.md
python {skill_dir}/scripts/yuque_client.py md2lake "## 标题\n正文"
```

将 Markdown 转为语雀 lake HTML 格式。支持：标题、加粗/斜体/删除线、行内代码、链接、图片、引用块、有序/无序列表、代码块、表格、分割线。所有纯文本与代码均自动做 HTML 转义（`< > &`），不会破坏结构。

**推荐搭配 update-doc 使用**：先 md2lake 转格式，再 update-doc --body-file 上传。

### 全局参数

任何命令均可附加以下参数：

| 参数 | 说明 |
|------|------|
| `--output-file <path>` | 结果输出到文件而非 stdout（解决 Windows 管道大 JSON 失败问题） |
| `--body-only` | 仅用于 `get-doc`，输出纯 body HTML 而非 JSON 包装 |

示例：
```bash
python {skill_dir}/scripts/yuque_client.py get-doc 12345 67890 edit --body-only --output-file body.html
```

---

## Lake HTML 格式速查

| Markdown | Lake HTML |
|----------|-----------|
| `# 标题` | `<h1><span class="ne-text">标题</span></h1>` |
| `普通段落` | `<p class="ne-p"><span class="ne-text">普通段落</span></p>` |
| `**加粗**` | `<strong><span class="ne-text">加粗</span></strong>` |
| `*斜体*` | `<em><span class="ne-text">斜体</span></em>` |
| `` `code` `` | `<code class="ne-code"><span class="ne-text">code</span></code>` |
| `> 引用` | `<div class="ne-quote"><p class="ne-p"><span class="ne-text">引用</span></p></div>` |
| `- 列表项` | `<ul class="ne-ul"><li data-lake-index-type="0"><span class="ne-text">列表项</span></li></ul>` |
| `1. 有序` | `<ol class="ne-ol"><li data-lake-index-type="0"><span class="ne-text">有序</span></li></ol>` |
| `---` | `<hr class="ne-hr" />` |
| 空行 | `<p class="ne-p"><br></p>` |

---

## Windows 环境注意事项

1. **管道输出大 JSON 失败**：Windows 下 `cmd | python -c "..."` 对大文档（>50KB）经常因编码或 buffer 问题报 JSONDecodeError。**解决方案**：使用 `--output-file` 参数直接写文件。
2. **命令行长度限制**：Windows cmd 参数上限约 8000 字节。长内容必须用 `--body-file` 从文件读取。
3. **避免复杂内联命令**：正文、Markdown、HTML 等长内容不要直接塞进命令参数，先写入文件再传路径。
4. **编码**：脚本已自动设置 stdout 为 utf-8，但建议在 PowerShell 或 Git Bash 中运行（比 cmd.exe 编码支持好）。
