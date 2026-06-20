---
name: qzone-personality
description: |
  QQ空间人格分析技能：爬取用户QQ空间说说和资料，进行MBTI和九型人格深度分析。
  当用户提到"分析我的QQ空间"、"QQ空间MBTI"、"QQ空间人格分析"、"分析说说"、"空间性格分析"、"九型人格QQ空间"时触发。
  需要用户提供QQ空间Cookie（登录态）。
---

# QQ空间人格分析技能

## 功能概述

1. **凭证管理**：保存用户QQ空间Cookie
2. **数据爬取**：爬取用户所有说说（JSON存储）+ 空间资料
3. **人格分析**：基于内容进行MBTI和九型人格深度分析

## 完整工作流程

### 步骤一：获取Cookie

用户需要在浏览器中登录QQ空间，然后从DevTools复制Cookie：

1. 打开 https://user.qzone.qq.com/ 并登录
2. 按 F12 打开DevTools
3. 切换到 Network 标签
4. 刷新页面
5. 找到任意请求，复制完整的Cookie字符串

### 步骤二：保存凭证

用户提供Cookie后，运行保存脚本：

```bash
python scripts/save_credentials.py --cookie "用户的完整cookie字符串"
```

脚本会：
- 提取关键字段（uin, skey, p_skey等）
- 计算g_tk鉴权参数
- 保存到 `~/.hermes/qzone/config.json`

### 步骤三：爬取说说

```bash
python scripts/crawl_emotions.py --output ~/.hermes/qzone/data/
```

产出：`emotions.json` - 包含所有说说内容、时间、评论、点赞等

### 步骤四：获取资料

```bash
python scripts/crawl_profile.py --output ~/.hermes/qzone/data/
```

产出：`profile.json` - 包含主页信息、访客记录、好友列表

### 步骤五：生成分析Prompt

```bash
# MBTI分析prompt
python scripts/analyze_mbti.py --data ~/.hermes/qzone/data/ --output ~/.hermes/qzone/analysis/

# 九型人格分析prompt
python scripts/analyze_enneagram.py --data ~/.hermes/qzone/data/ --output ~/.hermes/qzone/analysis/
```

### 步骤六：执行分析

将生成的prompt发送给LLM进行分析：

```bash
# 方法1: 直接发送prompt
hermes chat < ~/.hermes/qzone/analysis/mbti_prompt.txt
hermes chat < ~/.hermes/qzone/analysis/enneagram_prompt.txt

# 方法2: 让马莎分析
# 直接说"帮我分析MBTI"或"帮我分析九型人格"
```

### 步骤七：保存报告

分析完成后，报告会自动保存到：
- `~/.hermes/qzone/analysis/mbti_report.md`
- `~/.hermes/qzone/analysis/enneagram_report.md`

## 输出报告格式

分析报告包含：
1. **MBTI类型判定**：4个维度得分 + 详细解释
2. **九型人格判定**：主型 + 翼型 + 三元组分析
3. **内容证据**：引用具体说说作为分析依据
4. **人格画像**：综合描述用户性格特点
5. **成长建议**：基于人格类型的发展建议

## 文件结构

```
~/.hermes/qzone/
├── config.json          # 凭证配置
├── data/
│   ├── emotions.json    # 说说数据
│   └── profile.json     # 用户资料
└── analysis/
    ├── mbti_report.md   # MBTI分析报告
    └── enneagram_report.md  # 九型人格报告
```

## 注意事项

- Cookie会过期，需定期更新（通常几天到一周）
- 说说数量多时爬取需要时间（每20条约1秒）
- 分析基于LLM，结果仅供参考
- 首次使用需要安装依赖：无额外依赖，纯Python标准库

## 快速使用示例

用户说："帮我分析我的QQ空间MBTI"

1. 询问用户提供Cookie
2. 运行 `save_credentials.py` 保存
3. 运行 `crawl_emotions.py` 爬取说说
4. 运行 `analyze_mbti.py` 生成prompt
5. 将prompt发送给LLM分析
6. 保存报告并返回给用户

## 输出示例

### MBTI报告包含：
- 4个维度得分和判定
- 每个维度的详细分析
- 引用具体说说作为证据
- 综合人格画像
- 成长建议

### 九型人格报告包含：
- 主型判定（1-9号）
- 翼型分析（如4w5）
- 三元组归属
- 健康层级评估
- 发展方向建议
