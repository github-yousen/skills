---
name: boss-zhipin
description: 通过 API 调用操作 Boss直聘（zhipin.com）的专用技能。当用户提到在Boss直聘上"搜索职位"、"看岗位"、"筛简历"、"投递职位"、"发消息"、"操作岗位"等与Boss直聘求职相关的指令时触发。
---

# Boss直聘 操作技能

## 概述

基于逆向分析 `www.zhipin.com` 网站源码（511KB HTML + 791KB main.js），提取 88 个 API 接口。
本技能封装了常见求职操作的 API 调用，填入 Cookie 后即可直接用 Python 脚本操作。

## 凭证获取

1. 浏览器打开 `https://www.zhipin.com` 并登录
2. F12 → Application → Cookies → 复制 `www.zhipin.com` 域下所有 Cookie
3. 将 Cookie 字符串填入 `scripts/api_client.py` 的 `_COOKIES` 变量

### 鉴权体系

Boss直聘使用三层鉴权：

| 层级 | 机制 | 关键字段 |
|------|------|----------|
| Gateway Token | 安全网关 | `__zp_stoken__`, `__zp_sseed__`, `__zp_sname__`, `__zp_sts__` |
| Session Token | 会话 | `bst` Cookie + `token` Header |
| CSRF | 防跨站 | Cookie 中的 csrf 字段 |

## 可直接调用的操作

### 职位搜索

```python
from scripts.api_client import search_jobs

# 搜索"产品经理"职位（全国）
jobs = search_jobs(keyword="产品经理", page=1)

# 搜索北京的Java职位
jobs = search_jobs(keyword="Java", city_code="101010100", page=1)

# 筛选：15-20K、3-5年经验、本科学历
jobs = search_jobs(
    keyword="前端",
    city_code="101020100",  # 上海
    salary="1006",          # 15-20K
    experience="104",       # 3-5年
    degree="203",           # 本科
)
```

### 获取城市列表

```python
from scripts.api_client import get_cities, get_city_hot_areas

# 全国城市列表
cities = get_cities()

# 北京热门区域
areas = get_city_hot_areas("101010100")
```

### 职位详情

```python
from scripts.api_client import get_job_detail

# 获取职位详情
detail = get_job_detail(item_id="xxx")
```

### 推荐职位

```python
from scripts.api_client import get_recommend_jobs

# 获取推荐职位
jobs = get_recommend_jobs()
```

### 公司/品牌搜索

```python
from scripts.api_client import search_brand

# 搜索公司品牌
brands = search_brand("腾讯")
```

## 城市编码参考

| 城市 | 编码 |
|------|------|
| 全国 | (留空) |
| 北京 | 101010100 |
| 上海 | 101020100 |
| 广州 | 101280100 |
| 深圳 | 101280600 |
| 杭州 | 101210100 |
| 成都 | 101270100 |
| 南京 | 101190100 |
| 武汉 | 101200100 |
| 西安 | 101110100 |

## 薪资编码参考

| 编码 | 薪资范围 |
|------|----------|
| 1001 | 3K以下 |
| 1002 | 3-5K |
| 1003 | 5-10K |
| 1004 | 10-15K |
| 1005 | 15-20K |
| 1006 | 20-30K |
| 1007 | 30-50K |
| 1008 | 50K以上 |

## 经验编码参考

| 编码 | 含义 |
|------|------|
| 101 | 应届生 |
| 102 | 1年以内 |
| 103 | 1-3年 |
| 104 | 3-5年 |
| 105 | 5-10年 |
| 106 | 10年以上 |

## 学历编码参考

| 编码 | 含义 |
|------|------|
| 201 | 不限 |
| 202 | 大专 |
| 203 | 本科 |
| 204 | 硕士 |
| 205 | 博士 |

## 注意事项

- 频繁请求可能触发风控，建议每次请求间隔 1-3 秒
- Cookie 有效期有限，过期后需重新从浏览器获取
- 部分写操作（投递、发消息）可能需要额外的 CSRF Token
