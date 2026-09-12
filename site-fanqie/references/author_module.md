# 模块 A：作者后台操作手册（fanqienovel.com）

> 由 SKILL.md 路由到本文件：**意图 = 查书籍/章节/数据/收益、发章节、评论、签到、诊断**
> 最后更新：2026-08-25

## 核心文件

| 文件 | 说明 |
|------|------|
| `{skill_dir}/fanqienovel_auth.json` | 凭证（Cookie / msToken / a_bogus / secsdk，过期只改这一个文件） |
| `{skill_dir}/scripts/api_client.py` | 底层 API 客户端（自动读凭证，含 `md_to_html`/`chapter_md_to_html`/`publish_chapter_from_md`） |
| `{skill_dir}/scripts/fanqie_encrypt.js` | 收益接口 VM 加密模块（Node，依赖 crypto-js + bignumber.js） |

独立 CLI 脚本（均在 `scripts/` 下）：

| 脚本 | 功能 |
|------|------|
| `query_chapters.py` | 查书籍/章节状态（含隐藏/断更识别） |
| `fanqie_book_overview.py` | 全书发布状态一览 |
| `query_stats.py` | 查书籍数据统计汇总 |
| `query_chapter_stats.py` | 查每章完读/追读/流失数据表格 |
| `query_income.py` | 查收益（汇总/每日/月度/礼物/互动，VM 加密） |
| `manage_comments.py` | 查看/回复读者评论、粉丝互动 |
| `publish_chapter.py` | 发布/更新章节（创建→预审→发布，支持 `--timer` 定时） |
| `attend.py` | 每日签到/请假/签到券（保障全勤奖） |
| `modify_book.py` | 修改书籍信息 |
| `diagnose_book.py` | 数据诊断：按合格标准逐项评价，指出短板 |
| `analyze_trends.py` | 全史多维趋势分析 |

## CLI 用法

```bash
# 查询类
python query_chapters.py [book_id]          # 书籍+章节状态
python query_stats.py [book_id]             # 数据汇总
python query_chapter_stats.py <book_id> [N] # 每章数据表格
python query_income.py [book_id]            # 收益（需 npm install）
python manage_comments.py <book_id>         # 书评（--reply/--fans/--like/--delete）

# 发布类（写操作）
python publish_chapter.py <book_id> <content.md路径> [volume_id] [volume_name] [item_id]
python publish_chapter.py <book_id> <content.md路径> --timer "2026-08-10 18:00"  # 定时发布

# 诊断/签到
python diagnose_book.py [book_id]           # 数据诊断
python analyze_trends.py [book_id] [days]   # 全史多维趋势
python attend.py <book_id>                  # 签到（--leave 请假 / --ticket 补签）
python modify_book.py <book_id>             # 修改书籍信息
```

## 凭证说明（使用前必填）

1. 打开 `https://fanqienovel.com` 登录作者账号
2. F12 → Network → 任选一条 `/api/author/` 请求
3. 复制请求头 **Cookie**、URL 中的 `msToken` / `a_bogus`、写操作请求头 `x-secsdk-csrf-token`
4. 更新 `fanqienovel_auth.json` 的 `cookie` / `ms_token` / `a_bogus` / `secsdk_token`

> 凭证有效期：`sid_guard` 约 60 天；`a_bogus` / `msToken` 失效后需重新抓取。请求报凭证错误时提示用户更新 `fanqienovel_auth.json`。

## 关键规则（实测沉淀）

- **通用参数**：`aid=2503`、`app_name=muye_novel`；GET 需 `msToken`+`a_bogus`；写操作需 `x-secsdk-csrf-token`
- **收益接口**：带 `book_id` 的收益接口必须带 `X-Muye-Encrypt-Key` 头并解密响应（`api_client.py` 自动走 Node 子进程）；`sec_time` 毫秒级、`start_date/end_date` 秒级；短篇用 `sa_income/book_monthly`、长篇用 `income/book_monthly_v3`。依赖：`cd {skill_dir} && npm install crypto-js bignumber.js`
- **发布流程**：必须**先查已发布章节再发布**（防重复/漏发）；`volume_name` 必填；新章节需先 `new_article` 拿 `item_id`；推荐 `publish_chapter_from_md()` 一条龙（创建→预审→发布）
- **今日字数达上限**：🔴 禁止擅自定时到明天，必须告知用户并询问处理方式
- **章节状态**：`article_status` 1=已发布、2=断更/隐藏（非审核中）、0=草稿；`has_hide`/`set_top` 不可靠
- **书籍阶段**：`book_intro.status` 是权威字段（`book_auth_not_safe`=未签约不可搜属正常阶段≠封禁；`cold_start_init/ing`=签约推流阶段）；勿把 `risk_rate` 高误判为违规
- **数据口径**：在读人数(前台14天累计) ≠ 阅读人数(后台单日)；章节跟读率直接用官方 `follow_read_rate` 勿推算；X万字读完率不能用章节读完率替代；断更>3天追更归零
- **趋势接口**：`stats_types` 组合见 `analysis_report.md`；`start_date/end_date` 秒级时间戳，支持任意天数，按创建日期自动算天数可拉全史

## 常见问题

- **接口报凭证错误**：更新 `fanqienovel_auth.json`（F12 → Network 重新复制）
- **收益接口报 -2 参数有误**：未走加密通道，确认 `npm install` 已执行且用 `api_client.py` 的封装函数
- **发布报"缺少书籍卷相关参数"**：`volume_name` 必填

## 参考资料

- `references/analysis_report.md` — 接口分析报告
- `references/writer_backend_api_report.md` — 作者后台前端逆向报告（530+ 端点）
- `references/writer_backend_api_report.json` — 机器可读版本
