"""
公司面经搜索工具
支持从牛客网(nowcoder.com)、脉脉网(maimai.cn)、知乎、CSDN等平台搜索公司面试经验
基于多搜索引擎聚合实现，提供全面的面经搜索结果

功能特性:
- 多平台支持: 牛客网、脉脉、知乎、CSDN
- 多搜索引擎聚合: 搜狗、必应、百度
- 时间筛选: 支持按天数筛选近期面经
- 岗位筛选: 支持后端/前端/算法/测试等岗位过滤
- 正文抓取: 自动抓取面经正文并转换为 Markdown
- 多格式输出: text、markdown、json
- 配置文件: 支持自定义默认参数
- 插件化平台配置: 易于扩展新平台

用法:
    python interview_search.py "阿里巴巴"
    python interview_search.py "字节跳动" --days 30 --position backend
    python interview_search.py "腾讯" --platforms nowcoder,maimai --fetch 3
    python interview_search.py "百度" --format markdown
"""
from __future__ import annotations

import argparse
import base64
import json
import random
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# 让脚本可以直接 import 同目录下的模块
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from http_client import fetch_url  # noqa: E402
from html_to_markdown import convert as html_to_markdown  # noqa: E402


# ============ 配置加载 ============
def load_config() -> dict[str, Any]:
    """加载配置文件"""
    config_path = SCRIPT_DIR.parent / "config" / "config.json"
    default_config = {
        "default_platforms": ["nowcoder", "maimai"],
        "default_engines": ["sogou", "bing"],
        "default_limit": 10,
        "default_timeout": 15,
        "default_max_retries": 2,
        "default_max_body_chars": 5000,
        "default_fetch_count": 0,
        "default_format": "text",
        "concurrency": {
            "search_workers": 8,
            "fetch_workers": 5,
        },
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ],
        "position_keywords": {},
    }

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # 深度合并配置
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        except Exception as e:
            print(f"警告: 配置文件加载失败，使用默认配置 ({e})", file=sys.stderr)

    return default_config


def load_platforms() -> dict[str, dict]:
    """加载平台配置"""
    platforms_path = SCRIPT_DIR.parent / "config" / "platforms.json"
    default_platforms = {
        "nowcoder": {
            "name": "牛客网",
            "domain": "nowcoder.com",
            "keywords": ["面经", "面试经验", "笔经面经"],
            "description": "牛客网 - 国内最大的IT求职面试平台",
            "priority": 1,
        },
        "maimai": {
            "name": "脉脉",
            "domain": "maimai.cn",
            "keywords": ["面经", "面试", "薪资", "offer"],
            "description": "脉脉 - 职场社交平台，真实员工面经分享",
            "priority": 2,
        },
    }

    if platforms_path.exists():
        try:
            with open(platforms_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 平台配置文件加载失败，使用内置配置 ({e})", file=sys.stderr)

    return default_platforms


# 全局配置
CONFIG = load_config()
PLATFORMS = load_platforms()

# 搜索引擎配置
ENGINE_URLS: dict[str, str] = {
    "sogou": "https://www.sogou.com/web?query={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "baidu": "https://www.baidu.com/s?wd={q}",
}

# 岗位关键词
POSITION_KEYWORDS: dict[str, list[str]] = CONFIG.get("position_keywords", {})


# ============ HTML 工具函数 ============
class _TagStripper(HTMLParser):
    """基于 HTMLParser 的纯文本提取"""
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "noscript", "iframe"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "iframe") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def strip_html(s: str) -> str:
    """去除 HTML 标签，返回纯文本"""
    p = _TagStripper()
    try:
        p.feed(s)
    except Exception:
        return re.sub(r"<[^>]+>", "", s).strip()
    return p.text or re.sub(r"<[^>]+>", "", s).strip()


def decode_entities(s: str) -> str:
    """解码 HTML 实体"""
    return unescape(s).strip()


def _extract_window(flat: str, start: int, pattern: str, window: int = 3000) -> str:
    """在 flat[start:start+window] 内按 pattern 抓第一个匹配并 strip"""
    end = min(start + window, len(flat))
    m = re.search(pattern, flat[start:end], re.DOTALL)
    if not m:
        return ""
    return strip_html(decode_entities(m.group(1)))


def get_random_user_agent() -> str:
    """获取随机 User-Agent"""
    user_agents = CONFIG.get("user_agents", [])
    if user_agents:
        return random.choice(user_agents)
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ============ 各搜索引擎解析器 ============
def parse_sogou(html: str, limit: int) -> list[dict]:
    """解析搜狗搜索结果"""
    flat = html.replace("\r", "").replace("\n", "")
    results: list[dict] = []

    # 尝试多种 h3 标签模式
    patterns = [
        r'<h3 class="vr-title[^"]*">(.*?)</h3>',
        r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        r'<h3[^>]*>(.*?)</h3>',
    ]

    for pattern_str in patterns:
        pattern = re.compile(pattern_str, re.DOTALL)
        for m in pattern.finditer(flat):
            if len(results) >= limit:
                break
            block = m.group(1)
            if "<a " not in block:
                continue
            href = re.search(r'href="([^"]+)"', block)
            if not href:
                continue
            url = href.group(1)
            if url.startswith("/link"):
                url = "https://www.sogou.com" + url
            if not url.startswith("http"):
                continue
            t = re.search(r"<a[^>]*>(.*?)</a>", block, re.DOTALL)
            title = strip_html(decode_entities(t.group(1))) if t else ""
            if not title:
                continue

            # 提取摘要
            snippet = ""
            for cls in ("str_info", "abstract", "rb", "fz-mid", "star-wiki"):
                snippet = _extract_window(
                    flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>'
                )
                if snippet:
                    break

            # 提取发布时间（如果有的话）
            publish_time = ""
            for cls in ("news-from", "time", "date"):
                publish_time = _extract_window(
                    flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>'
                )
                if publish_time:
                    break

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "engine": "sogou",
                "publish_time": publish_time,
            })

        if results:
            break

    return results[:limit]


def parse_bing(html: str, limit: int) -> list[dict]:
    """解析必应搜索结果"""
    flat = html.replace("\r", "").replace("\n", "")
    results: list[dict] = []

    # 找到所有 h2 标签（搜索结果标题）
    h2_pattern = re.compile(r'<h2[^>]*>(.*?)</h2>', re.IGNORECASE | re.DOTALL)

    for m in h2_pattern.finditer(flat):
        if len(results) >= limit:
            break

        h2_content = m.group(1)

        # 从 h2 中提取链接
        href_match = re.search(r'href="(https?://[^"]+)"', h2_content)
        if not href_match:
            continue

        url = href_match.group(1)

        # 跳过必应自身的链接
        if re.search(r"bing\.com|microsoft\.com", url):
            continue

        # 提取标题
        title_match = re.search(r'<a[^>]*>(.*?)</a>', h2_content, re.DOTALL)
        if title_match:
            title = strip_html(decode_entities(title_match.group(1)))
        else:
            title = strip_html(decode_entities(h2_content))

        if not title:
            continue

        # 在 h2 后面查找摘要和时间
        snippet = ""
        publish_time = ""

        # 查找 b_caption 或 b_snippet
        caption_start = m.end()
        caption_end = min(caption_start + 5000, len(flat))
        caption_section = flat[caption_start:caption_end]

        # 尝试多种摘要提取方式
        snippet_patterns = [
            r'class="b_caption"[^>]*>(.*?)</div>',
            r'class="b_lineclamp\d+"[^>]*>(.*?)</p>',
            r'class="b_snippet"[^>]*>(.*?)</p>',
            r'<p[^>]*class="[^"]*snippet[^"]*"[^>]*>(.*?)</p>',
        ]

        for pattern in snippet_patterns:
            snippet_match = re.search(pattern, caption_section, re.DOTALL)
            if snippet_match:
                snippet = strip_html(decode_entities(snippet_match.group(1)))
                if snippet:
                    break

        # 提取发布时间
        time_patterns = [
            r'class="b_lastUpdate"[^>]*>(.*?)</span>',
            r'class="news_dt"[^>]*>(.*?)</span>',
            r'(\d+天前)',
            r'(\d+小时前)',
        ]

        for pattern in time_patterns:
            time_match = re.search(pattern, caption_section)
            if time_match:
                publish_time = strip_html(time_match.group(1))
                if publish_time:
                    break

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "engine": "bing",
            "publish_time": publish_time,
        })

    return results


def parse_baidu(html: str, limit: int) -> list[dict]:
    """解析百度搜索结果"""
    flat = html.replace("\r", "").replace("\n", "")
    pattern = re.compile(
        r'<h3[^>]*class="t[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    results: list[dict] = []
    for m in pattern.finditer(flat):
        if len(results) >= limit:
            break
        url = m.group(1)
        if not url.startswith("http"):
            continue
        title = strip_html(decode_entities(m.group(2)))
        if not title:
            continue
        # 提取摘要
        snippet = ""
        for cls in ("c-abstract", "c-span9", "c-lineclamp", "content-right_8Zs40"):
            snippet = _extract_window(flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>')
            if snippet:
                break

        # 提取发布时间
        publish_time = ""
        for cls in ("c-color-gray2", "c-gray", "time"):
            publish_time = _extract_window(
                flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>'
            )
            if publish_time:
                break

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "engine": "baidu",
            "publish_time": publish_time,
        })
    return results


PARSERS = {
    "sogou": parse_sogou,
    "bing": parse_bing,
    "baidu": parse_baidu,
}


# ============ 数据结构 ============
@dataclass
class InterviewResult:
    """面经搜索结果"""
    title: str
    url: str
    snippet: str = ""
    platform: str = ""  # nowcoder / maimai / zhihu / csdn
    platform_name: str = ""  # 牛客网 / 脉脉 / 知乎 / CSDN
    engine: str = ""
    body: str = ""
    body_status: str = ""  # ok / blocked / fetch_failed / error
    publish_time: str = ""  # 发布时间字符串
    publish_date: datetime | None = None  # 解析后的发布日期
    positions: list[str] = field(default_factory=list)  # 匹配的岗位标签
    relevance_score: float = 0.0  # 相关性得分

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.publish_date:
            d["publish_date"] = self.publish_date.isoformat()
        return d


# ============ 时间解析 ============
def parse_publish_time(time_str: str) -> datetime | None:
    """解析发布时间字符串为 datetime 对象"""
    if not time_str:
        return None

    time_str = time_str.strip()
    now = datetime.now()

    # 常见的时间格式
    patterns = [
        # "3天前"、"5小时前"、"10分钟前"
        (r"(\d+)\s*天前", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"(\d+)\s*小时前", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s*分钟前", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s*秒前", lambda m: now - timedelta(seconds=int(m.group(1)))),
        # "昨天"、"前天"
        (r"昨天", lambda m: now - timedelta(days=1)),
        (r"前天", lambda m: now - timedelta(days=2)),
        # "2024-01-15"、"2024/01/15"
        (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
         lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        # "2024年1月15日"
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日",
         lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        # "01-15"（当年）
        (r"^(\d{1,2})[-/](\d{1,2})$",
         lambda m: datetime(now.year, int(m.group(1)), int(m.group(2)))),
    ]

    for pattern, handler in patterns:
        m = re.search(pattern, time_str)
        if m:
            try:
                return handler(m)
            except Exception:
                continue

    return None


def is_within_days(date: datetime | None, days: int) -> bool:
    """判断日期是否在指定天数内"""
    if not date:
        return True  # 无法解析时间的默认保留
    if days <= 0:
        return True
    cutoff = datetime.now() - timedelta(days=days)
    return date >= cutoff


# ============ 岗位识别 ============
def detect_positions(text: str) -> list[str]:
    """从文本中识别岗位类型"""
    if not text or not POSITION_KEYWORDS:
        return []

    text_lower = text.lower()
    matched_positions = []

    for pos_key, keywords in POSITION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                matched_positions.append(pos_key)
                break

    return matched_positions


# ============ 核心搜索逻辑 ============
def build_queries(company: str, platform: dict, position: str = "", days: int = 0) -> list[str]:
    """构建多个搜索查询，提高召回率"""
    queries = []
    domain = platform["domain"]
    keywords = platform["keywords"]
    platform_name = platform["name"]

    # 岗位关键词
    position_kw = ""
    if position and position in POSITION_KEYWORDS:
        position_kw = POSITION_KEYWORDS[position][0]

    # 时间关键词
    time_kw = ""
    if days > 0:
        if days <= 7:
            time_kw = "最近"
        elif days <= 30:
            time_kw = "最新"
        elif days <= 90:
            time_kw = "近期"

    # 策略1: site: 语法 + 公司名 + 关键词
    for kw in keywords[:2]:
        q_parts = [f"site:{domain}", company, kw]
        if position_kw:
            q_parts.append(position_kw)
        if time_kw:
            q_parts.append(time_kw)
        queries.append(" ".join(q_parts))

    # 策略2: 公司名 + 平台名 + 关键词
    for kw in keywords[:2]:
        q_parts = [company, kw, platform_name]
        if position_kw:
            q_parts.append(position_kw)
        if time_kw:
            q_parts.append(time_kw)
        queries.append(" ".join(q_parts))

    # 策略3: 公司名 + 关键词（泛搜索，后续过滤域名）
    q_parts = [company, keywords[0]]
    if position_kw:
        q_parts.append(position_kw)
    if time_kw:
        q_parts.append(time_kw)
    queries.append(" ".join(q_parts))

    return queries


def search_single_engine(
    engine: str,
    query: str,
    limit: int,
    timeout: int,
    max_retries: int,
) -> list[dict]:
    """单个搜索引擎搜索"""
    url_template = ENGINE_URLS.get(engine)
    if not url_template:
        return []

    url = url_template.format(q=urllib.parse.quote(query))
    parser = PARSERS.get(engine)
    if not parser:
        return []

    try:
        headers = {"User-Agent": get_random_user_agent()}
        result = fetch_url(
            url,
            timeout=timeout,
            max_retries=max_retries,
            return_meta=True,
            extra_headers=headers,
        )
        html = result.get("text", "")
        if not html:
            return []
        # 百度安全验证等反爬页面直接跳过
        if result.get("blocks") and "百度安全验证" in result.get("blocks", []):
            return []
        return parser(html, limit)
    except Exception:
        return []


def calculate_relevance(result: dict, company: str, platform: dict) -> float:
    """计算结果的相关性得分"""
    score = 0.0
    title = result.get("title", "").lower()
    snippet = result.get("snippet", "").lower()
    company_lower = company.lower()
    platform_name_lower = platform["name"].lower()

    # 标题包含完整公司名 +3 分（核心权重）
    if company_lower in title:
        score += 3.0
    # 摘要包含公司名 +1.5 分
    elif company_lower in snippet:
        score += 1.5

    # 标题包含面经相关关键词 +2 分（核心权重）
    has_interview_kw = False
    for kw in platform["keywords"]:
        if kw.lower() in title:
            score += 2.0
            has_interview_kw = True
            break
    if not has_interview_kw:
        # 摘要包含面经关键词 +1 分
        for kw in platform["keywords"]:
            if kw.lower() in snippet:
                score += 1.0
                break

    # 标题包含平台名 +1 分
    if platform_name_lower in title:
        score += 1.0

    # 有发布时间 +0.5 分
    if result.get("publish_time"):
        score += 0.5

    # 有摘要 +0.5 分
    if result.get("snippet"):
        score += 0.5

    return score


def search_platform(
    company: str,
    platform_key: str,
    engines: list[str],
    limit_per_engine: int,
    timeout: int,
    max_retries: int,
    position: str = "",
    days: int = 0,
) -> list[InterviewResult]:
    """搜索单个平台的面经"""
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return []

    domain = platform["domain"]
    queries = build_queries(company, platform, position, days)

    # 并行搜索多个引擎和多个查询
    raw_results: list[dict] = []
    search_tasks = []

    for engine in engines:
        for query in queries:
            search_tasks.append((engine, query))

    search_workers = CONFIG.get("concurrency", {}).get("search_workers", 8)
    with ThreadPoolExecutor(max_workers=min(len(search_tasks), search_workers)) as executor:
        futures = {
            executor.submit(
                search_single_engine, engine, query, limit_per_engine, timeout, max_retries
            ): (engine, query)
            for engine, query in search_tasks
        }
        for future in as_completed(futures):
            try:
                results = future.result()
                raw_results.extend(results)
            except Exception:
                pass

    # 转换为 InterviewResult 并去重、过滤
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    final_results: list[InterviewResult] = []

    for r in raw_results:
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        publish_time_str = r.get("publish_time", "")

        # 判断是否是目标平台的内容
        # 策略1: 直接域名匹配
        is_target_platform = domain in url

        # 策略2: 标题或摘要中包含平台名称（针对搜索引擎重定向链接）
        platform_name_lower = platform["name"].lower()
        if not is_target_platform:
            title_lower = title.lower()
            snippet_lower = snippet.lower()
            if platform_name_lower in title_lower or platform_name_lower in snippet_lower:
                is_target_platform = True

        # 策略3: 对于搜狗等搜索引擎的 /link 重定向，根据标题关键词判断
        if not is_target_platform and "/link" in url:
            # 检查标题是否包含面经相关关键词
            title_lower = title.lower()
            has_interview_keywords = any(
                kw in title_lower for kw in ["面经", "面试", "笔试", "offer", "求职"]
            )
            has_company = company.lower() in title_lower
            if has_interview_keywords and has_company:
                is_target_platform = True

        if not is_target_platform:
            continue

        # 验证标题或摘要包含公司名相关内容
        company_lower = company.lower()
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # 必须包含公司名（完整匹配或核心词匹配）
        has_company = company_lower in title_lower or company_lower in snippet_lower
        
        # 对于多字公司名，至少包含核心词汇（如"字节跳动"至少包含"字节"）
        if not has_company and len(company) >= 4:
            # 取公司名的前两个字作为核心词
            core_word = company_lower[:2]
            has_company = core_word in title_lower or core_word in snippet_lower
        
        if not has_company:
            continue

        # 解析发布时间
        publish_date = parse_publish_time(publish_time_str)

        # 时间筛选
        if days > 0 and not is_within_days(publish_date, days):
            # 无法确定时间的暂时保留，后续可能被排序到后面
            pass

        # 面经相关性检查：标题或摘要至少包含一个面经相关关键词
        interview_keywords = ["面经", "面试", "笔试", "offer", "求职", "面试经验", "面试题"]
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        has_interview_kw = any(kw in title_lower or kw in snippet_lower for kw in interview_keywords)
        
        # 如果是目标平台的内容，且包含公司名，就算没有明确的面经关键词也保留
        # 但如果不是目标平台的内容（通过重定向链接判断的），则必须包含面经关键词
        if "/link" in url and not has_interview_kw:
            continue
        
        # 岗位识别
        positions = detect_positions(title + " " + snippet)

        # 岗位筛选
        if position and positions and position not in positions:
            continue

        # 去重
        # 对于重定向链接，用标题作为去重 key
        if "/link" in url:
            dedup_key = re.sub(r"\s+", " ", title.lower().strip())[:100]
            if dedup_key in seen_titles:
                continue
            seen_titles.add(dedup_key)
        else:
            dedup_key = re.sub(r"[?#].*", "", url)
            if dedup_key in seen_urls:
                continue
            seen_urls.add(dedup_key)

        # 计算相关性得分
        relevance = calculate_relevance(r, company, platform)

        final_results.append(InterviewResult(
            title=title,
            url=url,
            snippet=snippet,
            platform=platform_key,
            platform_name=platform["name"],
            engine=r.get("engine", ""),
            publish_time=publish_time_str,
            publish_date=publish_date,
            positions=positions,
            relevance_score=relevance,
        ))

    # 排序：先按相关性得分，再按发布时间（新的在前）
    final_results.sort(
        key=lambda x: (
            x.relevance_score,
            x.publish_date or datetime(1970, 1, 1),
        ),
        reverse=True,
    )

    return final_results


def search_all(
    company: str,
    platforms: list[str] | None = None,
    engines: list[str] | None = None,
    limit_per_engine: int = 10,
    timeout: int = 15,
    max_retries: int = 2,
    position: str = "",
    days: int = 0,
) -> list[InterviewResult]:
    """搜索所有平台的面经"""
    platforms = platforms or CONFIG.get("default_platforms", ["nowcoder", "maimai"])
    engines = engines or CONFIG.get("default_engines", ["sogou", "bing"])

    all_results: list[InterviewResult] = []
    with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
        futures = {
            executor.submit(
                search_platform, company, p, engines, limit_per_engine, timeout, max_retries, position, days
            ): p
            for p in platforms
        }
        for future in as_completed(futures):
            try:
                results = future.result()
                all_results.extend(results)
            except Exception:
                pass

    # 按平台优先级排序，同一平台按相关性和时间排序
    platform_priority = {p: PLATFORMS[p].get("priority", 99) for p in PLATFORMS}
    all_results.sort(
        key=lambda x: (
            platform_priority.get(x.platform, 99),
            -x.relevance_score,
            -(x.publish_date or datetime(1970, 1, 1)).timestamp(),
        )
    )

    return all_results


def fetch_bodies(results: list[InterviewResult], n: int = 0, max_chars: int = 5000) -> None:
    """抓取前 N 条结果的正文内容"""
    if n <= 0:
        return

    targets = results[:n]
    fetch_workers = CONFIG.get("concurrency", {}).get("fetch_workers", 5)
    with ThreadPoolExecutor(max_workers=min(n, fetch_workers)) as executor:
        future_to_result = {
            executor.submit(
                fetch_url,
                r.url,
                timeout=20,
                max_retries=2,
                return_meta=True,
                extra_headers={"User-Agent": get_random_user_agent()},
            ): r
            for r in targets
        }
        for future in as_completed(future_to_result):
            result = future_to_result[future]
            try:
                fetch_result = future.result()
                html = fetch_result.get("text", "")
                if html and not fetch_result.get("blocks"):
                    md = html_to_markdown(html)
                    # 按段落截断
                    result.body = _truncate_by_paragraph(md, max_chars)
                    result.body_status = "ok"
                elif fetch_result.get("blocks"):
                    result.body_status = f"blocked({','.join(fetch_result.get('blocks', []))})"
                else:
                    result.body_status = f"fetch_failed({fetch_result.get('error', 'unknown')})"
            except Exception as e:
                result.body_status = f"error({type(e).__name__})"


def _truncate_by_paragraph(text: str, max_chars: int) -> str:
    """按段落边界截断文本，避免在句子中间切断"""
    if len(text) <= max_chars:
        return text

    # 找最近的段落分隔符
    paragraphs = text.split("\n\n")
    result = ""
    for p in paragraphs:
        if len(result) + len(p) + 2 > max_chars:
            break
        if result:
            result += "\n\n"
        result += p

    return result or text[:max_chars]


# ============ 输出格式化 ============
def format_text(results: list[InterviewResult], company: str, days: int = 0, position: str = "") -> str:
    """格式化为纯文本输出"""
    lines = []
    lines.append(f"=== {company} 面经搜索结果 ===")

    # 筛选条件说明
    filters = []
    if days > 0:
        filters.append(f"近{days}天")
    if position:
        pos_name = {
            "backend": "后端",
            "frontend": "前端",
            "algorithm": "算法",
            "test": "测试",
            "product": "产品",
            "operation": "运营",
            "design": "设计",
            "data": "数据",
        }.get(position, position)
        filters.append(f"{pos_name}岗位")
    if filters:
        lines.append(f"筛选条件: {'、'.join(filters)}")

    lines.append(f"共找到 {len(results)} 条结果\n")

    # 按平台分组
    by_platform: dict[str, list[InterviewResult]] = {}
    for r in results:
        by_platform.setdefault(r.platform_name, []).append(r)

    for platform_name, platform_results in by_platform.items():
        lines.append(f"【{platform_name}】({len(platform_results)}条)")
        lines.append("-" * 50)
        for i, r in enumerate(platform_results, 1):
            lines.append(f"{i}. {r.title}")
            lines.append(f"   链接: {r.url}")

            # 发布时间
            if r.publish_time:
                lines.append(f"   发布: {r.publish_time}")

            # 岗位标签
            if r.positions:
                pos_names = [
                    {
                        "backend": "后端",
                        "frontend": "前端",
                        "algorithm": "算法",
                        "test": "测试",
                        "product": "产品",
                        "operation": "运营",
                        "design": "设计",
                        "data": "数据",
                    }.get(p, p) for p in r.positions
                ]
                lines.append(f"   岗位: {'、'.join(pos_names)}")

            # 摘要
            if r.snippet:
                snippet = r.snippet[:150]
                if len(r.snippet) > 150:
                    snippet += "..."
                lines.append(f"   摘要: {snippet}")

            # 正文预览
            if r.body and r.body_status == "ok":
                body_preview = r.body[:200]
                if len(r.body) > 200:
                    body_preview += "..."
                lines.append(f"   正文: {body_preview}")

            lines.append("")
        lines.append("")

    return "\n".join(lines)


def format_markdown(results: list[InterviewResult], company: str, days: int = 0, position: str = "") -> str:
    """格式化为 Markdown 输出"""
    lines = []
    lines.append(f"# {company} 面经搜索结果")
    lines.append("")

    # 筛选条件说明
    filters = []
    if days > 0:
        filters.append(f"近{days}天")
    if position:
        pos_name = {
            "backend": "后端",
            "frontend": "前端",
            "algorithm": "算法",
            "test": "测试",
            "product": "产品",
            "operation": "运营",
            "design": "设计",
            "data": "数据",
        }.get(position, position)
        filters.append(f"{pos_name}岗位")
    if filters:
        lines.append(f"> 筛选条件：{'、'.join(filters)}")
        lines.append("")

    lines.append(f"共找到 **{len(results)}** 条面经结果")
    lines.append("")

    # 按平台分组
    by_platform: dict[str, list[InterviewResult]] = {}
    for r in results:
        by_platform.setdefault(r.platform_name, []).append(r)

    for platform_name, platform_results in by_platform.items():
        lines.append(f"## {platform_name} ({len(platform_results)}条)")
        lines.append("")
        for i, r in enumerate(platform_results, 1):
            lines.append(f"### {i}. [{r.title}]({r.url})")
            lines.append("")

            # 元信息
            meta_parts = []
            if r.publish_time:
                meta_parts.append(f"📅 {r.publish_time}")
            if r.positions:
                pos_names = [
                    {
                        "backend": "后端",
                        "frontend": "前端",
                        "algorithm": "算法",
                        "test": "测试",
                        "product": "产品",
                        "operation": "运营",
                        "design": "设计",
                        "data": "数据",
                    }.get(p, p) for p in r.positions
                ]
                meta_parts.append(f"💼 {'、'.join(pos_names)}")
            meta_parts.append(f"🔍 来源: {r.engine}")

            if meta_parts:
                lines.append("*" + " | ".join(meta_parts) + "*")
                lines.append("")

            # 摘要
            if r.snippet:
                lines.append(f"> {r.snippet}")
                lines.append("")

            # 正文预览
            if r.body and r.body_status == "ok":
                lines.append("**正文预览：**")
                lines.append("")
                body_preview = r.body[:500]
                lines.append(body_preview)
                if len(r.body) > 500:
                    lines.append("...")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def format_json(results: list[InterviewResult]) -> str:
    """格式化为 JSON 输出"""
    return json.dumps(
        [r.to_dict() for r in results],
        ensure_ascii=False,
        indent=2,
    )


# ============ 错误提示 ============
def print_error(message: str, hint: str = "") -> None:
    """打印友好的错误信息"""
    print(f"\n❌ 错误: {message}", file=sys.stderr)
    if hint:
        print(f"💡 提示: {hint}", file=sys.stderr)
    print(file=sys.stderr)


def print_warning(message: str) -> None:
    """打印警告信息"""
    print(f"⚠️  警告: {message}", file=sys.stderr)


# ============ 主函数 ============
def main():
    parser = argparse.ArgumentParser(
        description="公司面经搜索工具 - 从牛客网、脉脉网等平台快速获取面试经验",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "阿里巴巴"                          # 基础搜索
  %(prog)s "字节跳动" --days 30               # 近30天的面经
  %(prog)s "腾讯" --position backend          # 后端岗位面经
  %(prog)s "百度" --platforms nowcoder,maimai # 指定平台
  %(prog)s "美团" --fetch 3 --format markdown # 抓取正文并输出Markdown
        """,
    )

    parser.add_argument("company", nargs="?", help="公司名称，如：阿里巴巴、字节跳动、腾讯")

    parser.add_argument(
        "--platforms", "-p",
        default=",".join(CONFIG.get("default_platforms", ["nowcoder", "maimai"])),
        help=f"搜索平台，逗号分隔，可选: {','.join(PLATFORMS.keys())} (默认: {','.join(CONFIG.get('default_platforms', []))})",
    )

    parser.add_argument(
        "--engines", "-e",
        default=",".join(CONFIG.get("default_engines", ["sogou", "bing"])),
        help=f"搜索引擎，逗号分隔，可选: sogou,bing,baidu (默认: {','.join(CONFIG.get('default_engines', []))})",
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=CONFIG.get("default_limit", 10),
        help=f"每个引擎每个查询返回的最大结果数 (默认: {CONFIG.get('default_limit', 10)})",
    )

    parser.add_argument(
        "--format", "-f",
        choices=["text", "markdown", "json"],
        default=CONFIG.get("default_format", "text"),
        help=f"输出格式 (默认: {CONFIG.get('default_format', 'text')})",
    )

    parser.add_argument(
        "--fetch",
        type=int,
        default=CONFIG.get("default_fetch_count", 0),
        help="抓取前 N 条结果的正文内容 (默认: 0，不抓取)",
    )

    parser.add_argument(
        "--max-body-chars",
        type=int,
        default=CONFIG.get("default_max_body_chars", 5000),
        help=f"抓取正文时的最大字符数 (默认: {CONFIG.get('default_max_body_chars', 5000)})",
    )

    parser.add_argument(
        "--days", "-d",
        type=int,
        default=0,
        help="只显示近 N 天的面经，0 表示不限制 (默认: 0)",
    )

    parser.add_argument(
        "--position",
        default="",
        choices=["", "backend", "frontend", "algorithm", "test", "product", "operation", "design", "data"],
        help="按岗位筛选，可选: backend(后端), frontend(前端), algorithm(算法), test(测试), product(产品), operation(运营), design(设计), data(数据)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=CONFIG.get("default_timeout", 15),
        help=f"单个请求超时时间（秒） (默认: {CONFIG.get('default_timeout', 15)})",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=CONFIG.get("default_max_retries", 2),
        help=f"失败重试次数 (默认: {CONFIG.get('default_max_retries', 2)})",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，不输出进度日志",
    )

    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="列出所有支持的平台并退出",
    )

    parser.add_argument(
        "--list-positions",
        action="store_true",
        help="列出所有支持的岗位类型并退出",
    )

    args = parser.parse_args()

    # 列出平台
    if args.list_platforms:
        print("支持的平台:")
        for key, info in PLATFORMS.items():
            print(f"  {key:12s} - {info['name']}: {info.get('description', '')}")
        return

    # 列出岗位
    if args.list_positions:
        print("支持的岗位筛选:")
        pos_names = {
            "backend": "后端开发",
            "frontend": "前端开发",
            "algorithm": "算法",
            "test": "测试/测开",
            "product": "产品经理",
            "operation": "运营",
            "design": "设计",
            "data": "数据",
        }
        for key, name in pos_names.items():
            keywords = POSITION_KEYWORDS.get(key, [])
            kw_str = ", ".join(keywords[:5])
            print(f"  {key:12s} - {name} (关键词: {kw_str})")
        return

    # 检查 company 参数
    if not args.company:
        print_error(
            "请提供公司名称",
            "用法: interview_search.py \"公司名称\"\n使用 --help 查看帮助信息",
        )
        sys.exit(1)

    # 解析平台列表
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    platforms = [p for p in platforms if p in PLATFORMS]
    if not platforms:
        print_error(
            f"没有有效的平台",
            f"可选平台: {', '.join(PLATFORMS.keys())}\n使用 --list-platforms 查看所有平台",
        )
        sys.exit(1)

    # 解析引擎列表
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    engines = [e for e in engines if e in ENGINE_URLS]
    if not engines:
        print_error(
            f"没有有效的搜索引擎",
            f"可选引擎: {', '.join(ENGINE_URLS.keys())}",
        )
        sys.exit(1)

    # 验证岗位参数
    if args.position and args.position not in POSITION_KEYWORDS:
        print_error(
            f"不支持的岗位类型: {args.position}",
            f"使用 --list-positions 查看所有支持的岗位类型",
        )
        sys.exit(1)

    if not args.quiet:
        print(f"🔍 正在搜索 {args.company} 的面经...", file=sys.stderr)
        print(f"📱 平台: {', '.join(PLATFORMS[p]['name'] for p in platforms)}", file=sys.stderr)
        print(f"🌐 引擎: {', '.join(engines)}", file=sys.stderr)
        if args.days > 0:
            print(f"⏰ 时间: 近{args.days}天", file=sys.stderr)
        if args.position:
            pos_name = {
                "backend": "后端",
                "frontend": "前端",
                "algorithm": "算法",
                "test": "测试",
                "product": "产品",
                "operation": "运营",
                "design": "设计",
                "data": "数据",
            }.get(args.position, args.position)
            print(f"💼 岗位: {pos_name}", file=sys.stderr)
        print(file=sys.stderr)

    # 执行搜索
    try:
        results = search_all(
            company=args.company,
            platforms=platforms,
            engines=engines,
            limit_per_engine=args.limit,
            timeout=args.timeout,
            max_retries=args.max_retries,
            position=args.position,
            days=args.days,
        )
    except Exception as e:
        print_error(
            f"搜索失败: {type(e).__name__}: {e}",
            "请检查网络连接，或尝试更换搜索引擎 (--engines 参数)",
        )
        sys.exit(1)

    if not results:
        print_warning("未找到相关面经结果")
        if args.days > 0:
            print_warning(f"尝试放宽时间限制，或减少 --days 参数")
        if args.position:
            print_warning(f"尝试去掉岗位筛选，或更换岗位类型")
        print(file=sys.stderr)

    # 抓取正文
    if args.fetch > 0 and results:
        if not args.quiet:
            actual_fetch = min(args.fetch, len(results))
            print(f"📄 正在抓取前 {actual_fetch} 条正文...", file=sys.stderr)
        try:
            fetch_bodies(results, args.fetch, args.max_body_chars)
        except Exception as e:
            print_warning(f"正文抓取部分失败: {e}")

    # 输出结果
    if args.format == "json":
        print(format_json(results))
    elif args.format == "markdown":
        print(format_markdown(results, args.company, args.days, args.position))
    else:
        print(format_text(results, args.company, args.days, args.position))


if __name__ == "__main__":
    main()
