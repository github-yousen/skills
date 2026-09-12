# -*- coding: utf-8 -*-
"""
novel_crawler.py — 在线阅读站通用章节爬虫：把整本小说拼成完整 txt
适用于无打包接口、但正文以静态 HTML 呈现的笔趣阁/平板电子书系站点。

用法：
  py novel_crawler.py <目录页URL> --out 输出目录 [--limit N] [--start N] [--delay 0.5]
  py novel_crawler.py <目录页URL> --out d:/yousen/  --limit 5   # 先爬5章测试
  py novel_crawler.py <目录页URL> --out d:/yousen/              # 爬全本

特性：
  - 自动识别多种目录结构（<dd><a>、id="list" 等）与正文容器（content/htmlContent/nr 等）
  - 自动检测编码（UTF-8/GBK）
  - 断点续传（进度写入 <输出>/progress.json，中断后重跑自动跳过已抓章节）
  - 失败重试 + 请求限速（避免被反爬封禁）
  - 清理广告残留（脚本标记/广告词/HTML 实体）
"""
import argparse
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# 正文容器候选（按优先级）
CONTENT_PATTERNS = [
    r'<div[^>]*id="content[^"]*"[^>]*>(.*?)</div>',          # qiqixs: id="content{chid}"
    r'<div[^>]*class="content[^"]*"[^>]*>(.*?)</div>',        # qiqixs: class="content novel{id}"
    r'<div[^>]*id="htmlContent"[^>]*>(.*?)</div>',            # jieqi
    r'<div[^>]*id="chaptercontent"[^>]*>(.*?)</div>',
    r'<div[^>]*id="booktext"[^>]*>(.*?)</div>',
    r'<div[^>]*id="nr"[^>]*>(.*?)</div>',
    r'<div[^>]*id="chapterContent"[^>]*>(.*?)</div>',
    r'<div[^>]*class="?showtxt"?[^>]*>(.*?)</div>',
    r'<div[^>]*id="content"[^>]*>(.*?)</div>',
    r'<article[^>]*>(.*?)</article>',
]

# 广告残留清理
AD_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'<style[^>]*>.*?</style>',
    r'<!--.*?-->',
    r'一秒记住[^<]{0,40}',
    r'请收藏[^<]{0,40}',
    r'最新章节[^<]{0,40}',
    r'无弹窗[^<]{0,40}',
    r'天才一秒记住[^<]{0,40}',
    r'看书网[^<]{0,30}',
]


def _decode(data):
    for enc in ("utf-8", "gb18030"):
        try:
            return enc, data.decode(enc)
        except UnicodeDecodeError:
            continue
    return "gb18030", data.decode("gb18030", errors="replace")


def fetch(url, timeout=30):
    """优先 requests（走系统代理、请求头完整，实测兼容性最好），urllib 兜底"""
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
        r.raise_for_status()
        enc, text = _decode(r.content)
        return r.url, text, enc
    except ImportError:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            data = resp.read()
            final = resp.geturl()
        enc, text = _decode(data)
        return final, text, enc
    except Exception:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            data = resp.read()
            final = resp.geturl()
        enc, text = _decode(data)
        return final, text, enc


def parse_catalog(url):
    """解析目录页，返回 [(章节名, 绝对URL), ...] 按页面顺序"""
    final, html, enc = fetch(url)
    base = url.rsplit("/", 1)[0] + "/"
    # 模式1：<dd><a href="...">章节名</a></dd>（qiqixs/老笔趣阁模板）
    items = re.findall(r'<dd[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    # 模式2：id="list" 容器内的 a
    if len(items) < 5:
        m = re.search(r'<div[^>]*id="list"[^>]*>(.*?)</div>', html, re.S)
        if m:
            items = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S)
    # 模式3：任意 dl/dt 结构
    if len(items) < 5:
        m = re.search(r'<dl[^>]*>(.*?)</dl>', html, re.S)
        if m:
            items = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S)
    chaps = []
    for href, name in items:
        name = re.sub(r"<[^>]+>", "", name).strip()
        if not name or not href:
            continue
        if href.lower().endswith((".css", ".js", ".png", ".jpg")):
            continue
        if re.search(r"搜索|登录|注册|书架|排行|首页|分类|简介|目录", name):
            continue
        abs_url = urllib.parse.urljoin(base, href)
        chaps.append((name, abs_url))
    return chaps, enc


def extract_div(html, start_idx):
    """从起始标签位置开始，按 <div/</div> 平衡取完整闭合块"""
    i = html.find(">", start_idx)
    if i < 0:
        return None
    depth = 1
    pos = i + 1
    while pos < len(html):
        nxt_div = html.find("<div", pos)
        nxt_end = html.find("</div", pos)
        if nxt_end == -1:
            return None
        if nxt_div != -1 and nxt_div < nxt_end:
            depth += 1
            pos = nxt_div + 4
        else:
            depth -= 1
            if depth == 0:
                return html[i + 1:nxt_end]
            pos = nxt_end + 5
    return None


def parse_content(html):
    """提取正文纯文本（多容器模式 + 平衡 div 解析 + 清洗）"""
    body = None
    for pat in CONTENT_PATTERNS:
        m = re.search(pat, html, re.S)
        if m:
            body = extract_div(html, m.start())
            if body and len(re.sub(r"<[^>]+>", "", body).strip()) > 20:
                break
            body = None
    if body is None:
        return None
    # 先删 script/style/注释（防止其内容在去标签后残留为文本）
    for p in AD_PATTERNS:
        body = re.sub(p, "", body, flags=re.I | re.S)
    # 段落化：br/p/div 换行
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</p>|</div>", "\n", body, flags=re.I)
    # 去标签
    body = re.sub(r"<[^>]+>", "", body)
    # 实体还原
    body = body.replace("&nbsp;", " ").replace("&ldquo;", "\u201c").replace("&rdquo;", "\u201d")
    body = body.replace("&mdash;", "\u2014").replace("&hellip;", "\u2026").replace("&amp;", "&")
    body = body.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # 压缩空行
    lines = [l.strip() for l in body.split("\n")]
    lines = [l for l in lines if l]
    return "\n".join(lines)


def crawl(catalog_url, out_dir, limit=None, start=1, delay=0.5, max_retries=3):
    print(f"== 解析目录: {catalog_url}")
    chaps, enc = parse_catalog(catalog_url)
    print(f"章节数: {len(chaps)}，页面编码: {enc}")
    if not chaps:
        print("未解析到章节，目录结构可能不支持（试试换站）")
        return

    os.makedirs(out_dir, exist_ok=True)
    progress_path = os.path.join(out_dir, "progress.json")
    done = set()
    if os.path.exists(progress_path):
        try:
            done = set(json.load(open(progress_path, encoding="utf-8")))
            print(f"续传：已抓 {len(done)} 章")
        except Exception:
            done = set()

    target = chaps[start - 1:]
    if limit:
        target = target[:limit]
    total = len(target)
    print(f"本次任务: 第{start}章起，共 {total} 章")

    out_parts = []
    ok = 0
    fail = 0
    for i, (name, url) in enumerate(target, start=start):
        if url in done:
            ok += 1
            continue
        content = None
        for attempt in range(max_retries):
            try:
                _, html, _ = fetch(url)
                content = parse_content(html)
                if content:
                    break
            except Exception as e:
                print(f"  [{i}/{total}] 第{attempt+1}次失败: {type(e).__name__}")
                time.sleep(delay * 3)
        if not content:
            print(f"  [{i}/{total}] 失败: {name} ({url})")
            fail += 1
            continue
        part = f"\n\n{name}\n\n{content}\n"
        out_parts.append(part)
        done.add(url)
        # 保存进度
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(sorted(done), f, ensure_ascii=False)
        ok += 1
        if i % 10 == 0 or i == total:
            print(f"  进度 {i}/{total} (成功{ok} 失败{fail})")
        time.sleep(delay)

    # 汇总写文件
    if out_parts:
        name = os.path.basename(catalog_url.rstrip("/")) or "novel"
        out_path = os.path.join(out_dir, f"{name}_crawled.txt")
        # 新章节追加到已有文件
        if os.path.exists(out_path):
            with io.open(out_path, "r", encoding="utf-8") as f:
                existing = f.read()
            with io.open(out_path, "w", encoding="utf-8") as f:
                f.write(existing + "".join(out_parts))
        else:
            with io.open(out_path, "w", encoding="utf-8") as f:
                f.write("".join(out_parts))
        print(f"\n完成: 新增 {len(out_parts)} 章，累计成功 {ok}，失败 {fail}")
        print(f"输出: {out_path} ({os.path.getsize(out_path)} bytes)")
    else:
        print("无新章节写入（可能全部已完成）")


def main():
    ap = argparse.ArgumentParser(description="在线阅读站章节爬虫")
    ap.add_argument("url", help="章节目录页 URL")
    ap.add_argument("--out", default="d:/yousen/", help="输出目录")
    ap.add_argument("--limit", type=int, default=None, help="仅爬前 N 章（测试用）")
    ap.add_argument("--start", type=int, default=1, help="从第几章开始")
    ap.add_argument("--delay", type=float, default=0.5, help="每章间隔秒数")
    args = ap.parse_args()
    crawl(args.url, args.out, limit=args.limit, start=args.start, delay=args.delay)


if __name__ == "__main__":
    main()
