"""
web-searcher 自带鲁棒 HTTP 抓取层（零外部依赖）。

设计参考 web-reverse-engineer/scripts/web_fetch_source.py 的 fetch_url，
但不依赖该模块，可独立 import。

核心能力：
- 自动解压 gzip/deflate；可选 br/zstd
- 多级编码识别：HTTP 头 -> HTML meta -> utf-8；按域名回退 GBK
- 反爬页检测（CF 5秒盾、百度安全验证、微博跳转等）
- 指数退避重试（429/5xx/超时/连接错误）
- SSL 跳过验证
- 沙箱友好（无需任何第三方 pip 包）
"""
from __future__ import annotations

import gzip
import random
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Any

# ============ 可选解压库（沙箱内可能未装） ============
try:
    import brotli  # type: ignore
    HAS_BROTLI = True
except ImportError:
    try:
        import brotlicffi as brotli  # type: ignore
        HAS_BROTLI = True
    except ImportError:
        HAS_BROTLI = False

try:
    import zstandard  # type: ignore
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

# ============ 配置 ============
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}
# 已知声明 charset 不准 / 实际用 GBK 的中文站点
GBK_DOMAINS = ("bing.com", "baidu.com", "sogou.com", "so.com", "haosou.com")

# SSL 上下文：跳过验证（沙箱里自签证书常见）
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 反爬强特征：出现即可判定为拦截页
ANTIBOT_MARKERS = [
    ("sina visitor system", "微博访客系统跳转页"),
    ("just a moment", "Cloudflare 5秒盾"),
    ("checking your browser", "Cloudflare JS 挑战"),
    ("cf-browser-verification", "Cloudflare 浏览器验证"),
    ("enable javascript and cookies to continue", "JS/Cookie 强校验"),
    ("百度安全验证", "百度安全验证"),
    ("请完成安全验证", "安全验证页"),
    ("点击继续访问", "风控拦截页"),
    ("captcha", "验证码页"),
    ("滑动验证", "滑块验证"),
    ("forbidden", "访问被拒"),
    ("access denied", "访问被拒"),
]


# ============ 解压 / 编码 / 反爬 ============

def _accept_encoding() -> str:
    """按已装库动态协商压缩格式：未装 br/zstd 时绝不声明，避免拿到乱码。"""
    encs = ["gzip", "deflate"]
    if HAS_BROTLI:
        encs.append("br")
    if HAS_ZSTD:
        encs.append("zstd")
    return ", ".join(encs)


def _decompress(raw: bytes, encoding: str) -> bytes:
    """按 Content-Encoding 自动解压；失败回退原 bytes。"""
    enc = (encoding or "").lower().strip()
    if not enc or enc == "identity":
        return raw
    try:
        if enc == "gzip":
            return gzip.decompress(raw)
        if enc == "deflate":
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
        if enc == "br" and HAS_BROTLI:
            return brotli.decompress(raw)
        if enc == "zstd" and HAS_ZSTD:
            return zstandard.ZstdDecompressor().decompress(raw)
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] 解压 {enc} 失败: {e}", file=sys.stderr)
        return raw
    print(
        f"  [WARN] 服务器返回 {enc} 压缩但缺少解压库，内容可能乱码。"
        f"建议: pip install brotli zstandard",
        file=sys.stderr,
    )
    return raw


def _detect_charset(raw: bytes, content_type: str, url: str = "") -> str:
    """多级编码识别：HTTP 头 -> HTML meta -> 域名回退 GBK -> utf-8。"""
    ct = (content_type or "").lower()
    if "charset=" in ct:
        cs = ct.split("charset=")[-1].split(";")[0].strip().strip("\"'")
        if cs:
            return cs

    head = raw[:4096].decode("latin-1", errors="ignore").lower()
    m = re.search(rb"<meta[^>]+charset=[\"']?\s*([a-z0-9_\-]+)".decode("latin-1"), head)
    if not m:
        m = re.search(
            r'content=["\'][^"\']*charset=([a-z0-9_\-]+)', head
        )
    if m:
        return m.group(1)

    # 中文搜索引擎常声明 utf-8 但实际返回 GBK —— 按域名兜底
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        host = ""
    if any(d in host for d in GBK_DOMAINS):
        return "gbk"

    return "utf-8"


def detect_block(text: str, body_len: int = 0) -> list[str]:
    """检测反爬 / 拦截 / 占位页。返回触发的特征描述列表。"""
    low = text.lower()
    hits: list[str] = []
    for marker, desc in ANTIBOT_MARKERS:
        if marker in low:
            hits.append(desc)
    if body_len and body_len < 2048 and ("<html" in low or "<!doctype" in low):
        hits.append("响应过小(<2KB)，疑似占位/跳转页")
    # 去重保序
    return list(dict.fromkeys(hits))


# ============ 主入口 ============

def fetch_url(
    url: str,
    timeout: int = 20,
    max_retries: int = 3,
    extra_headers: dict[str, str] | None = None,
    return_meta: bool = False,
    verbose: bool = False,
) -> Any:
    """抓取 URL 内容（鲁棒版）。

    自动解压 / 多级编码 / 反爬检测 / 指数退避重试 / SSL 跳过验证。

    return_meta=False 时返回 str（向后兼容）。
    return_meta=True 时返回 dict {text, raw, encoding, charset, status, blocks, headers, error}。
    """
    headers = dict(DEFAULT_HEADERS)
    headers["Accept-Encoding"] = _accept_encoding()
    if extra_headers:
        headers.update(extra_headers)

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
                raw = resp.read()
                enc = resp.headers.get("Content-Encoding", "")
                ctype = resp.headers.get("Content-Type", "")
                data = _decompress(raw, enc)
                charset = _detect_charset(data, ctype, url)
                try:
                    text = data.decode(charset, errors="ignore")
                except (LookupError, TypeError):
                    text = data.decode("utf-8", errors="ignore")
                blocks = detect_block(text, len(data))
                if blocks and verbose:
                    print(
                        f"  [反爬提示] {url} 疑似未拿到真实内容: {', '.join(blocks)}",
                        file=sys.stderr,
                    )
                if return_meta:
                    return {
                        "text": text,
                        "raw": data,
                        "encoding": enc or "identity",
                        "charset": charset,
                        "content_type": ctype,
                        "status": getattr(resp, "status", 200),
                        "blocks": blocks,
                        "headers": dict(resp.headers),
                        "error": None,
                    }
                return text

        except urllib.error.HTTPError as e:
            last_err = e
            code = e.code
            if code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = min(2 ** attempt, 8) + random.uniform(0, 0.5)
                if verbose:
                    print(
                        f"  [重试 {attempt}/{max_retries}] HTTP {code}, {wait:.1f}s 后重试 {url}",
                        file=sys.stderr,
                    )
                time.sleep(wait)
                continue
            if verbose:
                if code == 403:
                    print(f"  [ERROR] 403 Forbidden: 可能需要更真实 UA/Cookie/Referer -> {url}", file=sys.stderr)
                elif code == 404:
                    print(f"  [ERROR] 404 Not Found: {url}", file=sys.stderr)
                else:
                    print(f"  [ERROR] HTTP {code}: {url}", file=sys.stderr)
            break
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, ConnectionError) as e:
            last_err = e
            if attempt < max_retries:
                wait = min(2 ** attempt, 8) + random.uniform(0, 0.5)
                if verbose:
                    print(
                        f"  [重试 {attempt}/{max_retries}] {type(e).__name__}, {wait:.1f}s 后重试 {url}",
                        file=sys.stderr,
                    )
                time.sleep(wait)
                continue
            if verbose:
                print(f"  [ERROR] {type(e).__name__}: {e} -> {url}", file=sys.stderr)
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if verbose:
                print(f"  [ERROR] {url}: {e}", file=sys.stderr)
            break

    if return_meta:
        return {
            "text": "",
            "raw": b"",
            "encoding": "",
            "charset": "",
            "content_type": "",
            "status": getattr(last_err, "code", 0),
            "blocks": [],
            "headers": {},
            "error": str(last_err) if last_err else "unknown",
        }
    return ""


# ============ 自检 ============

if __name__ == "__main__":
    """快速自检：抓一个中文页面验证解压 + 编码。"""
    if len(sys.argv) < 2:
        print("用法: python http_client.py <url>")
        sys.exit(1)

    meta = fetch_url(sys.argv[1], return_meta=True, verbose=True)
    print(f"status={meta['status']}  encoding={meta['encoding']}  "
          f"charset={meta['charset']}  text_len={len(meta['text'])}")
    if meta["blocks"]:
        print(f"反爬标记: {meta['blocks']}")
    if meta["error"]:
        print(f"error: {meta['error']}")
    print("--- 前 300 字符 ---")
    print(meta["text"][:300].replace("\n", " "))
