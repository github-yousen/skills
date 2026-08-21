# AI 模型排行榜聚合技能 - 数据源分析报告

> 分析时间：2026-08-21（补充一：OpenCompass/SuperCLUE/MMLU-Pro；补充二：GPQA/Terminal-Bench/SWE-bench Pro/BrowseComp）
> 用途：记录各排行榜数据源的获取方式、数据结构、可操作性，供技能维护参考

---

## 一、背景

用户需求：获取各个模型在不同榜单上的排序，将多个排行榜数据揉合成一个可复用技能。
本报告记录 12 个数据源的逆向分析结果（含权威性评估）。

---

## 二、数据源详表

### 1. LMArena Chatbot Arena（arena.ai）

| 项目 | 内容 |
|------|------|
| 官网 | https://arena.ai/（原 lmarena.ai，2026.1 更名） |
| 运营方 | UC Berkeley SkyLab + LMSYS Org |
| 数据获取 | **HuggingFace 官方数据集** `lmarena-ai/leaderboard-dataset` |
| 数据格式 | Parquet（CC-BY-4.0），每日更新 |
| 下载 URL | `https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/resolve/main/{config}/latest-00000-of-00001.parquet` |
| 可用 config | 22 个（text/vision/text_to_image/agent/search/document/video 等），本项目使用 `text`（含 29 个分类） |
| 列结构 | `model_name, organization, license, rating, rating_lower, rating_upper, variance, vote_count, rank, category, leaderboard_publish_date` |
| 数据量 | text config latest：10359 行，393 模型 × 29 分类 |
| 分类 | overall/chinese/coding/creative_writing/math/industry_* 等 |
| 反爬 | **官网 Cloudflare IP 级封禁**（Ray ID a2e65d5edb0b7a73），但 **HF 数据集完全公开免封** |

> ⚠️ 重要发现：主页/API 全被 Cloudflare 封禁，**唯一可靠通道是官方 HF 数据集**。
> 原站推理 API（`PUT /api/stream/retry-evaluation-session-message/{sid}/messages/{mid}`）依赖浏览器 Cookie + sessionId/messageId，纯脚本不可行。

### 2. LiveBench

| 项目 | 内容 |
|------|------|
| 官网 | https://livebench.ai/ |
| 维护方 | Abacus.AI（ICLR 2025 Spotlight） |
| 数据获取 | **官方公开 CSV/JSON**（无需凭证，可直接 curl） |
| 数据 URL | `https://livebench.ai/table_{YYYY_MM_DD}.csv` |
| | `https://livebench.ai/categories_{YYYY_MM_DD}.json` |
| | `https://livebench.ai/cost_{YYYY_MM_DD}.csv` |
| 版本机制 | 版本号 = 日期（如 2026_06_25），页面 UI 展示 11 个 release |
| 表格结构 | `model, AMPS_Hard, code_completion, ..., theory_of_mind`（23 个子任务列） |
| categories | JSON 映射：子任务 → 大类（Reasoning/Coding/Agentic Coding/Math/Data Analysis/Language/IF） |
| 数据量 | 44 模型 × 23 子任务 |

> 技能中将子任务按 categories 映射聚合为 7 大类 + Overall 均值。

### 3. SWE-bench

| 项目 | 内容 |
|------|------|
| 官网 | https://swebench.com/ |
| 运营方 | Princeton（SweBench） |
| 数据获取 | **官网 HTML 内嵌 `<script type="application/json">`** |
| 数据结构 | `[{name: "bash-only", results: [{agent, model_display, model_org, cost, date, ...}]}]` |
| 分类 | Lite / Multilingual / Multimodal / Test / Verified / bash-only（6 类） |
| 数据量 | 4MB HTML，内嵌全量结果（含 per_instance_details 明细） |

### 4. EQ-Bench v4

| 项目 | 内容 |
|------|------|
| 官网 | https://eqbench.com/ |
| 数据获取 | **官方 JS 数据文件** `https://eqbench.com/eqbench4/eqbench4_data.js` |
| 结构 | `const EQBENCH4_DATA = {generated_at, dimensions, models: [{model, display, elo, ci_low, ci_high, sigma, n_scenarios, dims}]}` |
| 数据量 | 28 模型 × 8 维度（Analytical/Validating/Challenging/Interpretive/Directive/Containment/Yielding/Naturalness） |
| 更新 | 约每月更新（generated_at 标注） |

### 5. Artificial Analysis

| 项目 | 内容 |
|------|------|
| 官网 | https://artificialanalysis.ai/ |
| 数据获取 A | **官方 Data API** `GET /api/v2/language/models/free`（需 `x-api-key` 头，免费 100 次/天） |
| 数据获取 B | **首页 HTML 内嵌 JSON-LD**（无需凭证，但仅 Top 11 模型） |
| 指标 | Intelligence Index v4.1（9 项评估：GDPval/τ³-Banking/Terminal-Bench/SciCode/HLE/GPQA Diamond 等） |
| 附加指标 | Coding Index / Agentic Index / 输入输出价格 / 性能（tokens/s, TTFT） |
| API 端点 | `https://artificialanalysis.ai/api/v2/language/models/free` + `x-api-key` |

> API key 在 https://artificialanalysis.ai/api-key-management-redirect 创建。Free tier 含：公开语言模型端点（headline 指数、中位性能、价格）+ 免费媒体端点。

---

## 三、抓取方案汇总

| 榜单 | 方案 | 需凭证 | 反爬 |
|------|------|--------|------|
| LMArena | 下载 HF parquet + pyarrow 解析 | 否 | 无（HF 公开） |
| LiveBench | 直接下载官方 CSV/JSON | 否 | 无 |
| SWE-bench | 抓 HTML + 提取内嵌 JSON | 否 | 无 |
| EQ-Bench | 直接下载 JS 数据文件 | 否 | 无 |
| Artificial Analysis | API（首选）/ HTML JSON-LD（降级） | 可选 | 无 |

---

## 四、补充数据源（2026-08-21 第二轮分析）

### 6. OpenCompass 司南（上海AI实验室）

| 项目 | 内容 |
|------|------|
| 官网 | https://rank.opencompass.org.cn/ |
| 权威性 | 上海AI实验室官方，国产模型评测最权威体系之一 |
| 数据获取 | **OSS 静态 JSON**（无需凭证） |
| 数据 URL | `https://opencompass.oss-cn-shanghai.aliyuncs.com/assets/llm/data-llm-ability_official.json` |
| 结构 | 7 能力表：Overall/Language/Knowledge/Reason/Math/Code/Agent（各 23 行） |
| 字段 | `model, org, open_source, para_num, date, update_date, Average, 分能力指标, rank_change` |
| 反爬 | 无 |

### 7. SuperCLUE（中文大模型权威榜）

| 项目 | 内容 |
|------|------|
| 官网 | https://www.superclueai.com/ |
| 权威性 | 中文通用大模型综合评测基准，国内权威 |
| 数据获取 | **官网公开 XLSX**（无需凭证） |
| 数据 URL | `https://www.superclueai.com/data/generalboard/{YYYY年M月}.xlsx` |
| 结构 | 4 个 sheet：总排行榜/推理模型总排行榜/推理任务总排行榜/开源排行榜 |
| 字段 | 模型名称/机构/开闭源/总分/数学推理/幻觉控制/科学推理/精确指令遵循/智能体编程/智能体任务规划 |
| 更新 | 约每月（自动探测前 6 个月，取最新可用） |
| 反爬 | 无（静态 xlsx） |

### 8. MMLU-Pro（UIUC TIGER-Lab）

| 项目 | 内容 |
|------|------|
| 官网 | https://huggingface.co/spaces/TIGER-Lab/MMLU-Pro |
| 权威性 | 伊利诺伊大学 TIGER-Lab 发布的多学科难题基准，被广泛引用 |
| 数据获取 | **HF Space gradio config**（无需凭证） |
| 数据 URL | `https://tiger-lab-mmlu-pro.hf.space/config` |
| 结构 | dataframe 组件：262 模型 × 14 学科（Biology/Business/Chemistry/CS/Economics/Engineering/Health/History/Law/Math/Philosophy/Physics/Psychology/Other） |
| 字段 | Models, Model Size(B), Data Source, Overall, 学科分数 |
| 反爬 | 无 |

### 9-12. 新增国际基准榜（2026-08-21 第三轮分析）

#### 9. GPQA Diamond

| 项目 | 内容 |
|------|------|
| 权威性 | NYU/Scalable AI，博士级多学科科学推理，国际公认难度标杆 |
| 数据获取 | evals.report 官方验证榜（带 Source/Status/Date 凭证） |
| URL | `https://evals.report/benchmarks/gpqa-diamond` |
| 结构 | 83 模型：Model/Lab/Score/Status/Date |
| 说明 | 无官方持续 leaderboard，evals.report 聚合 Verified/Official/Unverified 分数 |

#### 10. Terminal-Bench 2.1

| 项目 | 内容 |
|------|------|
| 权威性 | JHU HarborFramework，命令行/终端智能体任务基准 |
| 数据获取 | evals.report 官方验证榜（同步自官方 tbench.ai） |
| URL | `https://evals.report/benchmarks/terminal-bench` |
| 结构 | 40 模型：成功率 % |
| 说明 | 官方另有 HF 数据集 `harborframework/terminal-bench-2-leaderboard`（submissions 目录） |

#### 11. SWE-bench Pro

| 项目 | 内容 |
|------|------|
| 权威性 | Scale AI 2025.9 发布，企业级软件工程任务（1865 题/41 仓库） |
| 数据获取 | evals.report 官方验证榜 |
| URL | `https://evals.report/benchmarks/swe-bench-pro` |
| 结构 | 52 模型：resolved % |
| 说明 | 注意：OpenAI 2026.7 指出约 30% 公开任务存在评测缺陷；官方在 scale.com/leaderboard/swe_bench_pro_public |

#### 12. BrowseComp-Plus

| 项目 | 内容 |
|------|------|
| 权威性 | Tevatron，OpenAI BrowseComp 升级版，网页浏览智能体基准 |
| 数据获取 | HF Space 官方 `data/leaderboard.json` |
| URL | `https://tevatron-browsecomp-plus.hf.space/data/leaderboard.json` |
| 结构 | 84 行：LLM+Retriever+Scaffold 组合的 Accuracy/Recall/Search Calls |
| 说明 | 数据以 LLM+Retriever 组合为单位，非单模型 |

### 13. 评估过但未纳入的候选

| 榜单 | 原因 |
|------|------|
| HF Open LLM Leaderboard v2 | 数据分散在逐模型 JSON 文件，且只覆盖开源模型 |
| Aider Polyglot | 官方更新慢（2024年底），多由第三方聚合站更新 |
| Vellum LLM Leaderboard | 关注度下降，非主流引用了 |
| HLE (Scale) | 是单点基准，数据通道在 scale.com SPA，非持续排行榜 |
| SuperCLUE 竞品 llm-stats/llm-leaderboard.com | 第三方聚合站，非一手权威数据源 |
| BenchLM.ai | 第三方聚合站（437 benchmark），数据来自官方/自报，非一手源 |

---

## 五、索引与缓存设计

- 缓存：`data/{name}.json`，12h 过期（`fetch_all.py` 中 `_cache_fresh`）
- 归一化：LMArena 按 category 分组成 `boards`；LiveBench 聚合成 7 大类 + Overall
- 模型名匹配：token 级包含匹配（按 `-/_/./()/空格` 切分，查询 token 是模型 token 子串即命中），兼容各榜单命名差异

---

## 六、已知限制

1. **LMArena 官网**被 Cloudflare 封禁（IP 级），无法直接抓官网排行榜页面，只能用 HF 官方数据集
2. **Artificial Analysis 无 API key** 时只有 Top 11 模型（HTML 内嵌），全量需免费注册 key
3. SWE-bench 无统一"总分"，只有各 agent+模型组合的成本与 resolved 明细
4. 各榜单指标体系不同（Elo/准确率/指数），不可直接横向比较
5. SuperCLUE 只覆盖中文生态模型（Qwen/Kimi/DeepSeek/GLM 等），OpenCompass 覆盖全球模型但只 23 个
6. OpenCompass 的 open_source 字段以各能力表为准（同一模型不同表可能不一致）
