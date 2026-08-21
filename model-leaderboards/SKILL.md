---
name: model-leaderboards
description: 跨榜单 AI 模型排行榜聚合查询技能。聚合 LMArena(Chatbot Arena)、LiveBench、SWE-bench、EQ-Bench、Artificial Analysis、OpenCompass 司南、SuperCLUE、MMLU-Pro、GPQA Diamond、Terminal-Bench 2.1、SWE-bench Pro、BrowseComp-Plus 十二大排行榜数据，支持查询任意模型在多个榜单上的排名/评分/成本，以及查看各榜单 Top N。当用户提到"查排行榜"、"模型排名"、"哪个模型最强"、"AI 模型榜单"、"榜单对比"、"模型排名对比"、"哪些模型在某某榜单排第几"等指令时触发。更新数据使用 fetch_all.py，查询使用 query_model.py。
---

# AI 模型排行榜聚合技能

聚合 12 大权威 AI 模型排行榜，一键查询任意模型跨榜单表现，无需登录、无需浏览器。

## 核心文件路径

| 文件 | 说明 |
|------|------|
| `{skill_dir}/model_leaderboards_auth.json` | 可选凭证（Artificial Analysis API key，**其余榜单公开免凭证**） |
| `{skill_dir}/scripts/fetch_all.py` | 数据抓取脚本（抓取全部 12 个榜单到 `data/`） |
| `{skill_dir}/scripts/query_model.py` | 查询工具（跨榜单搜索 / Top N / 榜单列表） |
| `{skill_dir}/data/*.json` | 榜单缓存数据（12h 过期，可用 --force 强制刷新） |

> `{skill_dir}` 指本技能目录。

## 数据源一览

| 榜单 | 数据获取 | 指标 | 覆盖 |
|------|---------|------|------|
| **LMArena** (arena.ai) | HF 官方数据集 | Elo rating | 393 模型 × 29 分类 |
| **LiveBench** | 官方公开 CSV | 平均准确率 % | 44 模型 × 8 类别 |
| **SWE-bench** | 官网 HTML | 代码能力（agent+成本） | 6 类榜单 |
| **EQ-Bench v4** | 官方 JS 数据 | 情感智能 Elo | 28 模型 |
| **Artificial Analysis** | 官方 API 或 HTML | Intelligence Index | 11~全量 |
| **OpenCompass 司南** | 上海AI实验室 OSS | 综合分 0-100 | 23 模型 × 7 能力 |
| **SuperCLUE** | 官方公开 XLSX | 总分 0-100 | 13 模型 × 4 榜 |
| **MMLU-Pro** | HF Space gradio | 准确率 0-1 | 262 模型 × 14 学科 |
| **GPQA Diamond** | evals.report 验证榜 | 准确率 % | 83 模型 |
| **Terminal-Bench 2.1** | evals.report 验证榜 | 成功率 % | 40 模型 |
| **SWE-bench Pro** | evals.report 验证榜 | resolved % | 52 模型 |
| **BrowseComp-Plus** | HF Space leaderboard.json | Accuracy % | 84 模型组合 |

## 使用方法

所有脚本在 `{skill_dir}/scripts/` 下，需先进入该目录或用绝对路径调用。

### 1. 更新榜单数据（首次使用 / 数据过期）

```bash
python fetch_all.py                # 抓取全部 12 个榜单
python fetch_all.py lmarena        # 只抓 LMArena
python fetch_all.py --force        # 强制刷新（忽略 12h 缓存）
```

### 2. 查询模型跨榜单表现（核心功能）

```bash
python query_model.py "claude opus"          # 模糊搜索（token 级包含匹配）
python query_model.py "gpt-5" --limit 5      # 每个榜单限显示 5 条
python query_model.py "qwen3.8" --exact      # 精确匹配
python query_model.py "gpt" --board coding   # 指定 LMArena 分类（默认 overall）
```

### 3. 查看榜单 Top N

```bash
python query_model.py --top lmarena overall 10     # LMArena overall 榜 Top10
python query_model.py --top lmarena coding 10      # LMArena 代码榜 Top10
python query_model.py --top lmarena chinese 10     # LMArena 中文榜 Top10
python query_model.py --top livebench Overall 10   # LiveBench Top10
python query_model.py --top eqbench 0 8            # EQ-Bench Top8
python query_model.py --top swebench Verified 10   # SWE-bench Verified Top10
python query_model.py --top artificialanalysis 0 10  # AA 指数 Top10
python query_model.py --top opencompass Overall 10  # 司南综合榜 Top10
python query_model.py --top opencompass Coding 10   # 司南代码榜 Top10
python query_model.py --top superclue 总排行榜 10    # SuperCLUE 总榜 Top10
python query_model.py --top superclue 开源排行榜 10  # SuperCLUE 开源榜 Top10
python query_model.py --top mmlupro 0 10            # MMLU-Pro Top10
python query_model.py --top gpqa 0 10               # GPQA Diamond Top10
python query_model.py --top terminalbench 0 10      # Terminal-Bench Top10
python query_model.py --top swebenchpro 0 10        # SWE-bench Pro Top10
python query_model.py --top browsecomp 0 10         # BrowseComp-Plus Top10
```

### 4. 列出所有榜单及分类

```bash
python query_model.py --list
```

## 输出示例

```
$ python query_model.py "claude opus"
▶ LMArena Chatbot Arena — [overall] (Elo rating, 更新 2026-08-19)
  #1 claude-opus-5-high (anthropic) | Elo 1505.1 (CI 1500.2-1510.0) | 25628 votes
▶ LiveBench (release 2026_06_25)
  #4 claude-opus-5-max-effort | Overall 80.5 | Reasoning 91.2 | Coding 81.4 | ...
▶ EQ-Bench v4 (Elo 情感智能)
  #1 claude-opus-5 | Elo 1385.0 (CI 1362.4-1412.0) | n=120
▶ OpenCompass 司南
  [Overall] #3 Claude Opus 4.7 (high) (Anthropic) | 64.0 | 闭源
▶ MMLU-Pro
  #4 Claude-4.6-Opus(Thinking) | Overall 0.891
```

## 匹配规则

- 查询词自动拆成 token（按 `-` `_` `/` `.` `()` 空格切分）
- **包含匹配**：查询词的每个 token 只需在模型 token 中找到子串即可
- 例：`"claude opus"` 可同时匹配 LMArena 的 `claude-opus-5-high`、SWE-bench 的 `Claude 4.5 Opus (high)`、EQ-Bench 的 `claude-opus-5`
- 例：`"qwen"` 匹配 `qwen3.8-max`、`Qwen3.5-397B`（qwen 是 qwen3.8 的子串）
- 例：`"gpt"` 匹配所有含 gpt 的模型

## LMArena 可用分类（--board 参数）

`overall`（默认）、`chinese`、`coding`、`creative_writing`、`english`、`expert`、
`french`、`german`、`hard_prompts`、`instruction_following`、`japanese`、`korean`、
`longer_query`、`math`、`multi_turn`、`non_english`、`russian`、`spanish` 及 10 个行业分类。

## OpenCompass 司南能力表

`Overall`（默认）、`Language`、`Knowledge`、`Reasoning`、`Math`、`Coding`、`Agentic`

## SuperCLUE 榜单（--top superclue 参数）

`总排行榜`（默认）、`推理模型总排行榜`、`推理任务总排行榜`、`开源排行榜`

## 注意事项

1. **LMArena 数据**：官方 HF 数据集（cc-by-4.0），每日更新，`updated` 字段显示发布时间
2. **LiveBench**：自动探测最新 release 版本，`release` 字段标注
3. **Artificial Analysis**：未配 API key 时降级为首页 HTML 数据（仅 Top 11 模型）；配置 key 后获得全量模型 + 定价信息
4. **SuperCLUE**：自动探测最新月份 XLSX（往前推 6 个月），`month` 字段标注
5. **OpenCompass 司南**：OSS 静态 JSON，`update_date` 标注，能力表 open_source 字段以各表为准
6. 数据缓存 12 小时，超过自动重新抓取；需要立即最新数据用 `--force`
7. 所有数据为各榜单官方发布，不同榜单指标不可直接横向比较（Elo vs 准确率 vs 指数）

## 扩展新榜单

在 `fetch_all.py` 中按现有函数模式添加抓取函数，注册到 `FETCHERS` dict，然后在 `query_model.py` 的 `list_all()` 和 `search_model()` 中添加对应展示逻辑即可。
