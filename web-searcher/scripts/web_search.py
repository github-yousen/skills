"""
web-searcher 主入口（Python 版）

特性：
- 并行抓取 5 个搜索引擎（ThreadPoolExecutor）
- 自动解压 / 多级编码 / 反爬检测（依赖 http_client.fetch_url）
- 域过滤（allowed/blocked）、去重、多种输出格式
- 零外部 Python 依赖

用法:
    python web_search.py "搜索词" --limit 10 --json
    python web_search.py "Vue3 教程" --lang zh --engines bing,baidu
    python web_search.py "AI 2026" --allowed-domains arxiv.org,github.com
    python web_search.py "Python" --format markdown --limit 5
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

# 让 python scripts/web_search.py 能直接 import http_client
sys.path.insert(0, str(Path(__file__).resolve().parent))
from http_client import fetch_url  # noqa: E402
from html_to_markdown import convert as html_to_markdown  # noqa: E402

# ============ 引擎 URL 模板 ============
ENGINE_URLS: dict[str, str] = {
    "bing": "https://www.bing.com/search?q={q}",
    "google": "https://www.google.com/search?q={q}&num={n}",
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "baidu": "https://www.baidu.com/s?wd={q}",
    "sogou": "https://www.sogou.com/web?query={q}",
}
DEFAULT_ENGINES_EN = ["bing", "google", "duckduckgo", "sogou"]
DEFAULT_ENGINES_ZH = ["bing", "baidu", "google"]


# ============ HTML 工具 ============

class _TagStripper(HTMLParser):
    """基于 HTMLParser 的纯文本提取，比正则可靠。"""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def strip_html(s: str) -> str:
    p = _TagStripper()
    try:
        p.feed(s)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", "", s).strip()
    return p.text or re.sub(r"<[^>]+>", "", s).strip()


def decode_entities(s: str) -> str:
    return unescape(s).strip()


def _extract_window(flat: str, start: int, pattern: str, window: int = 1500) -> str:
    """在 flat[start:start+window] 内按 pattern 抓第一个匹配并 strip。"""
    m = re.search(pattern, flat[start : start + window], re.DOTALL)
    if not m:
        return ""
    return strip_html(decode_entities(m.group(1)))


# ============ 各引擎 HTML 解析 ============

def parse_bing(html: str, limit: int) -> list[dict]:
    flat = html.replace("\r", "").replace("\n", "")
    results: list[dict] = []
    pattern = re.compile(
        r'<h2[^>]*>(.*?)</h2>\s*<div[^>]*class="b_caption"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(flat):
        if len(results) >= limit:
            break
        title_html, caption_html, block = m.group(1), m.group(2), m.group(0)

        url = ""
        b64 = re.search(r"u=a1([A-Za-z0-9+/=_\-]+)", block)
        if b64:
            s = b64.group(1).replace("-", "+").replace("_", "/")
            s += "=" * ((-len(s)) % 4)
            try:
                url = base64.b64decode(s).decode("utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                url = ""
        if not url:
            href = re.search(r'href="(https?://[^"]+)"', block)
            if href:
                url = href.group(1)
        if not url or re.search(r"bing\.com/search|microsoft\.com", url):
            continue

        title = strip_html(decode_entities(title_html)) or url.split("/")[2]
        snippet = _extract_window(caption_html, 0, r'class="b_lineclamp\d+"[^>]*>(.*?)</p>')
        results.append({"title": title, "url": url, "snippet": snippet, "engine": "bing"})
    return results


def parse_google(html: str, limit: int) -> list[dict]:
    flat = html.replace("\r", "").replace("\n", "")
    pattern = re.compile(r'href="/url\?q=(https?://[^&"]+)[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
    results: list[dict] = []
    seen: set[str] = set()
    for m in pattern.finditer(flat):
        if len(results) >= limit:
            break
        url = urllib.parse.unquote(m.group(1))
        if re.search(r"google\.com/search|youtube\.com/results", url):
            continue
        dk = re.sub(r"[?#].*", "", url)
        if dk in seen:
            continue
        seen.add(dk)
        title = strip_html(decode_entities(m.group(2)))
        results.append({"title": title, "url": url, "snippet": "", "engine": "google"})
    return results


def parse_ddg(html: str, limit: int) -> list[dict]:
    flat = html.replace("\r", "").replace("\n", "")
    pattern = re.compile(
        r'class="result__a"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL
    )
    results: list[dict] = []
    for m in pattern.finditer(flat):
        if len(results) >= limit:
            break
        url = m.group(1)
        if "duckduckgo.com" in url:
            continue
        title = strip_html(decode_entities(m.group(2))) or url.split("/")[2]
        # snippet 在该 a 标签附近往后 1500 字符内
        snippet = _extract_window(
            flat, m.end(), r'class="result__snippet[^"]*"[^>]*>(.*?)</[^>]+>'
        )
        results.append({"title": title, "url": url, "snippet": snippet, "engine": "ddg"})
    return results


def parse_baidu(html: str, limit: int) -> list[dict]:
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
        # snippet 在 h3 之后
        snippet = ""
        for cls in ("c-abstract", "c-span9", "c-lineclamp"):
            snippet = _extract_window(flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>')
            if snippet:
                break
        results.append({"title": title, "url": url, "snippet": snippet, "engine": "baidu"})
    return results


def parse_sogou(html: str, limit: int) -> list[dict]:
    flat = html.replace("\r", "").replace("\n", "")
    pattern = re.compile(r'<h3 class="vr-title[^"]*">(.*?)</h3>', re.DOTALL)
    results: list[dict] = []
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
        snippet = ""
        for cls in ("str_info", "abstract", "rb"):
            snippet = _extract_window(flat, m.end(), rf'class="{cls}[^"]*"[^>]*>(.*?)</[^>]+>')
            if snippet:
                break
        results.append({"title": title, "url": url, "snippet": snippet, "engine": "sogou"})
    return results


PARSERS = {
    "bing": parse_bing,
    "google": parse_google,
    "duckduckgo": parse_ddg,
    "baidu": parse_baidu,
    "sogou": parse_sogou,
}


# ============ 抓取编排 ============

@dataclass
class Result:
    title: str
    url: str
    snippet: str
    engine: str
    body: str | None = None  # --fetch 模式填充（markdown 格式正文）
    body_status: str = ""    # "ok" / "fetch_failed" / "blocked" / "skipped"


def search_engine(
    engine: str, query: str, limit: int, timeout: int, max_retries: int
) -> list[Result]:
    """单引擎搜索：构造 URL → 抓 HTML → 解析。失败返回空列表。"""
    if engine not in ENGINE_URLS:
        return []
    q = urllib.parse.quote(query)
    n = max(limit * 2, 20)  # google num 参数多请求一点，解析时再截断
    url = ENGINE_URLS[engine].format(q=q, n=n)
    try:
        meta = fetch_url(url, timeout=timeout, max_retries=max_retries, return_meta=True)
        if not meta["text"]:
            print(
                f"  [{engine}] 空响应 (status={meta['status']}, error={meta['error']})",
                file=sys.stderr,
            )
            return []
        if meta["blocks"]:
            print(
                f"  [{engine}] ⚠ 反爬: {', '.join(meta['blocks'])}",
                file=sys.stderr,
            )
        parser = PARSERS.get(engine)
        if not parser:
            return []
        return [Result(**r) for r in parser(meta["text"], limit)]
    except Exception as e:  # noqa: BLE001
        print(f"  [{engine}] 抓取失败: {type(e).__name__}: {e}", file=sys.stderr)
        return []


def _domain_ok(url: str, allowed: list[str], blocked: list[str]) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return True
    for d in blocked:
        d = d.strip().lower()
        if d and (host == d or host.endswith("." + d)):
            return False
    if allowed:
        for d in allowed:
            d = d.strip().lower()
            if d and (host == d or host.endswith("." + d)):
                return True
        return False
    return True


def fetch_bodies(
    results: list[Result],
    n: int,
    max_chars: int = 5000,
    timeout: int = 20,
    max_retries: int = 2,
) -> None:
    """对前 n 条结果抓取正文，原地填充 result.body / result.body_status。

    实现链路：
      fetch_url (http_client) → HTML 字符串
        → html_to_markdown.convert() (自实现，零依赖)
          → 按段落边界截断到 max_chars
            → 写入 result.body

    失败不抛异常，结果状态写到 result.body_status：
      - "ok": 成功
      - "blocked(原因)": 命中反爬，正文可能不完整
      - "fetch_failed(原因)": 网络/超时/空响应
      - "error(类型)": 其他异常
    """
    targets = results[:n]
    if not targets:
        return
    print(f"  [fetch] 正在抓取前 {len(targets)} 条正文（每条超时 {timeout}s）...", file=sys.stderr)
    for i, r in enumerate(targets, 1):
        try:
            meta = fetch_url(
                r.url, timeout=timeout, max_retries=max_retries, return_meta=True
            )
            if not meta["text"]:
                r.body_status = f"fetch_failed({meta.get('error') or 'empty'})"
                print(f"  [fetch] ({i}/{len(targets)}) ✗ {r.url[:60]}... → {r.body_status}", file=sys.stderr)
                continue
            md = html_to_markdown(meta["text"], max_chars=max_chars)
            r.body = md
            if meta["blocks"]:
                r.body_status = f"blocked({','.join(meta['blocks'])})"
                print(f"  [fetch] ({i}/{len(targets)}) ⚠ {r.url[:60]}... → {r.body_status}", file=sys.stderr)
            else:
                r.body_status = "ok"
                print(f"  [fetch] ({i}/{len(targets)}) ✓ {r.url[:60]}... → {len(md)} chars", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            r.body_status = f"error({type(e).__name__})"
            print(f"  [fetch] ({i}/{len(targets)}) ✗ {r.url[:60]}... → {r.body_status}", file=sys.stderr)


def search_all(
    query: str,
    engines: list[str],
    limit: int = 10,
    timeout: int = 15,
    max_retries: int = 2,
    allowed: list[str] | None = None,
    blocked: list[str] | None = None,
) -> list[Result]:
    """并行抓所有引擎，合并去重 + 域过滤。"""
    all_results: list[Result] = []
    with ThreadPoolExecutor(max_workers=min(len(engines), 6)) as pool:
        futures = {
            pool.submit(search_engine, eng, query, limit, timeout, max_retries): eng
            for eng in engines
        }
        for fut in as_completed(futures):
            eng = futures[fut]
            try:
                all_results.extend(fut.result())
            except Exception as e:  # noqa: BLE001
                print(f"  [{eng}] 任务失败: {e}", file=sys.stderr)

    if allowed or blocked:
        all_results = [
            r for r in all_results
            if _domain_ok(r.url, allowed=allowed or [], blocked=blocked or [])
        ]

    seen: set[str] = set()
    unique: list[Result] = []
    for r in all_results:
        try:
            u = urllib.parse.urlparse(r.url)
            key = (u.netloc + u.path).lower()
        except Exception:  # noqa: BLE001
            key = r.url
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


# ============ 输出 ============

def render_text(results: list[Result], query: str, engines: list[str]) -> str:
    if not results:
        return (
            f"未找到与「{query}」相关的结果。\n"
            f"建议：换关键词 / 放宽域过滤 / 加引擎。"
        )
    lines = [
        f"\n=== 搜索结果: {query} ===",
        f"共 {len(results)} 条（来源: {', '.join(engines)}）\n",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}")
        lines.append(f"   {r.url}")
        if r.snippet:
            lines.append(f"   {r.snippet}")
        if r.body:
            lines.append(f"   --- 正文（{r.body_status}，{len(r.body)} chars）---")
            for ln in r.body.splitlines():
                lines.append(f"   | {ln}")
        elif r.body_status and r.body_status != "ok":
            lines.append(f"   ⚠ 正文抓取: {r.body_status}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(results: list[Result], query: str, engines: list[str]) -> str:
    if not results:
        return f"_未找到与「{query}」相关的结果。_"
    lines = [f"## 搜索结果: {query}", f"来源: {', '.join(engines)}", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. [{r.title}]({r.url})")
        lines.append(f"_来源: {r.engine}_")
        if r.snippet:
            lines.append(f"> {r.snippet}")
        if r.body:
            lines.append("")
            lines.append(f"<details><summary>正文（{r.body_status}，{len(r.body)} 字符）</summary>\n")
            lines.append(r.body)
            lines.append("\n</details>")
        elif r.body_status and r.body_status != "ok":
            lines.append(f"\n⚠ 正文抓取失败: {r.body_status}")
        lines.append("")
    return "\n".join(lines)


def render_json(results: list[Result]) -> str:
    return json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)


# ============ CLI ============

def _has_chinese(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def _parse_list(s: str) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in re.split(r"[,;\s]+", s) if x.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="web_search",
        description="多引擎并行网络检索（web-searcher Python 版，零外部依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("query", help="搜索词")
    p.add_argument(
        "--engines", default="",
        help="逗号分隔的引擎列表，可选 bing,google,duckduckgo,baidu,sogou",
    )
    p.add_argument("--limit", "-l", type=int, default=10, help="每引擎最大结果数（默认 10）")
    p.add_argument(
        "--lang", default="auto", choices=["en", "zh", "auto"],
        help="auto=按 query 是否含中文自动选；zh=强制加 baidu；en=不加（默认 auto）",
    )
    p.add_argument(
        "--format", "-f", default="text",
        choices=["text", "markdown", "json"],
        help="输出格式（默认 text）",
    )
    p.add_argument("--timeout", type=int, default=15, help="单引擎超时秒数（默认 15）")
    p.add_argument("--max-retries", type=int, default=2, help="单引擎重试次数（默认 2）")
    p.add_argument("--allowed-domains", default="", help="仅显示的域名（逗号分隔）")
    p.add_argument("--blocked-domains", default="", help="排除的域名（逗号分隔）")
    p.add_argument(
        "--no-verbose", action="store_true",
        help="静默模式：不打印反爬/重试日志到 stderr",
    )
    p.add_argument(
        "--fetch", type=int, default=0, metavar="N",
        help="对前 N 个结果抓取正文并转 markdown（0=不抓）",
    )
    p.add_argument(
        "--max-body-chars", type=int, default=5000,
        help="--fetch 模式下单个正文最大字符数（默认 5000，按段落边界截断）",
    )
    args = p.parse_args(argv)

    # 引擎选择
    if args.engines:
        engines = [e.strip().lower() for e in args.engines.split(",") if e.strip()]
        unknown = [e for e in engines if e not in ENGINE_URLS]
        if unknown:
            print(f"未知引擎: {', '.join(unknown)}；可选: {', '.join(ENGINE_URLS)}", file=sys.stderr)
            return 2
    else:
        if args.lang == "zh" or (args.lang == "auto" and _has_chinese(args.query)):
            engines = list(DEFAULT_ENGINES_ZH)
        else:
            engines = list(DEFAULT_ENGINES_EN)

    allowed = _parse_list(args.allowed_domains)
    blocked = _parse_list(args.blocked_domains)

    results = search_all(
        args.query, engines,
        limit=args.limit, timeout=args.timeout, max_retries=args.max_retries,
        allowed=allowed, blocked=blocked,
    )

    if args.fetch > 0 and results:
        fetch_bodies(
            results, n=args.fetch,
            max_chars=args.max_body_chars,
            timeout=args.timeout, max_retries=args.max_retries,
        )

    if args.format == "json":
        print(render_json(results))
    elif args.format == "markdown":
        print(render_markdown(results, args.query, engines))
    else:
        print(render_text(results, args.query, engines))

    return 0


if __name__ == "__main__":
    sys.exit(main())
