# -*- coding: utf-8 -*-
"""
novel_download.py — 网络小说 TXT 下载核心脚本
支持：多数据源搜索 / 打包下载 / 编码转换 / 完整性验证 / 章节合并
用法示例：
  py novel_download.py 书名 --search                     # 站内搜索定位书籍
  py novel_download.py 书名 --source sudugu --id 102     # 速读谷下载
  py novel_download.py 书名 --source qiqixs --id 11055   # 平板电子书网下载
  py novel_download.py 书名 --source bookshuku --id 30736
  py novel_download.py 书名 --source baidupan --url https://pan.baidu.com/s/xxx
  py novel_download.py 文件路径 --convert --verify       # 转码+验证
  py novel_download.py 原文件 --merge "193,374-375" --out 合集.txt
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

SOURCES = {
    "sudugu": {
        "name": "速读谷",
        "search": "https://www.sudugu.co/modules/article/search.php",
        "download": "https://www.sudugu.co/modules/article/packdown.php?aid={aid}",
        "page": "https://www.sudugu.co/{aid}/",
        "note": "jieqi 系统，txt 打包直链，无反爬；GBK 编码；超长书支持分卷(start/end)",
    },
    "qiqixs": {
        "name": "平板电子书网",
        "download": "http://txt.qiqixs.info/txt/{aid}/{name}.txt",
        "zip": "http://txt.qiqixs.info/zip/{aid}/{name}.txt",
        "page": "http://www.77nt.info/txt/xiazai{aid}.html",
        "note": "信息全（字数/章节/最新章节）；下载子域有 Cloudflare 防护，requests 可能 403，需浏览器",
    },
    "bookshuku": {
        "name": "TXT图书下载网",
        "search": "http://wap.bookshuku.org/search.html?keyword={kw}",
        "download": "http://txt.bookshuku.org/home/down/txt/id/{aid}",
        "zip": "http://txt.bookshuku.org/home/down/zip/id/{aid}",
        "page": "http://wap.bookshuku.org/bookinfo/{aid}.html",
        "note": "txt/zip 双格式；下载子域有 Cloudflare 防护",
    },
    "woshuge": {
        "name": "我书阁",
        "search": "https://www.woshuge.com/search.html",
        "page": "https://www.woshuge.com/txtbook_download/{aid}/",
        "api": "https://www.woshuge.com/api/download/{aid}",
        "zip": "https://www.woshuge.com{path}",
        "note": "POST /api/download/{aid} 返回 zip 直链，无需登录、无反爬，全自动；zip 内含 UTF-8 txt",
    },
}


def http_get(url, timeout=30, referer=None):
    """零依赖 GET 请求（urllib），返回 bytes 或抛异常"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if referer:
        req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_post(url, data, timeout=30, referer=None, json_body=False):
    if json_body:
        body = json.dumps(data).encode()
        headers = {"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"}
    else:
        body = urllib.parse.urlencode(data).encode()
        headers = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=body, headers=headers)
    if referer:
        req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------- 搜索 ----------------

def search_sudugu(keyword):
    """速读谷搜索。注意：单结果命中时会 302 直接跳转到书籍页 /{aid}/"""
    url = SOURCES["sudugu"]["search"] + "?" + urllib.parse.urlencode({"searchkey": keyword})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        final_url = resp.geturl()
        html = resp.read().decode("gb18030", errors="replace")
    # 情况一：单结果直接跳转到书籍页
    if "search.php" not in final_url:
        m = re.search(r"/(\d+)/?$", final_url)
        if m:
            return [(m.group(1), keyword + "（搜索直达）")]
        return []
    # 情况二：搜索列表页，匹配书籍链接
    results = []
    pat = re.compile(r'<a[^>]*href="(?:https?://www\.sudugu\.co)?/(\d+)/"[^>]*>([^<]{2,40})</a>')
    for m in pat.finditer(html):
        aid, name = m.group(1), m.group(2).strip()
        if keyword not in name and "续章" not in name and "同人" not in name:
            continue
        if (aid, name) not in results:
            results.append((aid, name))
    return results


def search_woshuge(keyword):
    """我书阁站内搜索，返回 (id, 书名)。结果页书名常带'全本txt免费下载'等后缀"""
    url = SOURCES["woshuge"]["search"] + "?" + urllib.parse.urlencode({"keyword": keyword})
    html = http_get(url).decode("utf-8", errors="replace")
    results = []
    seen_ids = set()
    # 链接可能带 ?ref=xxx 后缀，先提取所有 txtbook_download 链接块再解析
    for m in re.finditer(r'<a[^>]*href="/txtbook_download/(\d+)/[^"]*"[^>]*>(.*?)</a>', html, re.S):
        aid, inner = m.group(1), m.group(2)
        name = re.sub(r"<[^>]+>", "", inner).strip()
        name = re.sub(r"(全本txt免费下载|txt免费下载|txt下载|全文下载|免费下载|电子书|_TXT|\.txt|百度云下载|网盘下载)", "", name).strip()
        if not name or keyword not in name:
            continue
        if aid in seen_ids:
            continue
        seen_ids.add(aid)
        results.append((aid, name))
    return results


def download_woshuge(aid, out_dir):
    """我书阁：POST /api/download/{aid} 拿 zip 直链 → 下载 → 解压出 txt"""
    try:
        resp = http_post(SOURCES["woshuge"]["api"].format(aid=aid),
                         {"timestamp": 0}, json_body=True,
                         referer=SOURCES["woshuge"]["page"].format(aid=aid))
        j = json.loads(resp.decode("utf-8", errors="replace"))
        if j.get("code") != 0 or not j.get("data", {}).get("url"):
            print(f"  API 返回异常: {str(j)[:200]}")
            return []
        rel = j["data"]["url"]
        fname = j["data"].get("filename", "book.zip")
        zip_url = SOURCES["woshuge"]["zip"].format(path=urllib.parse.quote(rel, safe="/"))
        zip_path = os.path.join(out_dir, fname)
        n = download_url(zip_url, zip_path, referer=SOURCES["woshuge"]["page"].format(aid=aid))
        print(f"  zip 下载完成: {n} bytes")
        # 解压 zip
        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            txt_members = [x for x in z.namelist() if x.lower().endswith((".txt", ".text"))]
            if not txt_members:
                print("  zip 内无 txt，成员:", z.namelist())
                return []
            member = txt_members[0]
            data = z.read(member)
            out_path = os.path.join(out_dir, os.path.splitext(fname)[0] + ".bin")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  解压 {member} -> {out_path} ({len(data)} bytes)")
            return [out_path]
    except Exception as e:
        print(f"  下载失败({type(e).__name__}): {str(e)[:150]}")
        return []


def search_all(keyword, author=None):
    """站内搜索（速读谷 + 我书阁）+ 提示全网搜索。
    bookshuku 搜索为 JS 渲染无法静态抓取，qiqixs 无稳定搜索接口，
    两者都通过 web_search 找详情页 URL 再解析出书籍 ID。"""
    print(f"== 站内搜索: {keyword} ==")
    found = []
    for src, fn in (("sudugu", search_sudugu), ("woshuge", search_woshuge)):
        try:
            res = fn(keyword)
            print(f"\n[{SOURCES[src]['name']}] 命中 {len(res)} 条")
            for aid, name in res[:10]:
                print(f"  id={aid}  {name}")
                found.append((src, aid, name))
        except Exception as e:
            print(f"[{SOURCES[src]['name']}] 搜索失败: {type(e).__name__}: {e}")
    print(f"\n[bookshuku / qiqixs] 搜索为 JS 渲染，请用 web_search 搜")
    print(f"  '{keyword} site:bookshuku.org' 或 '{keyword} txt 下载'")
    print(f"  再从详情页 URL（bookinfo/{keyword}数字.html、xiazai数字.html）提取 ID")
    if author:
        print(f"\n提示: 用 web_search 搜 '{keyword} {author} txt 下载' 补充全网结果")
    else:
        print(f"\n提示: 用 web_search 搜 '{keyword} txt 下载 完本' 补充全网结果")
    print("\n选书要点：匹配作者名、章节数最多、状态最新；速读谷/我书阁直链优先。")
    return found


# ---------------- 下载 ----------------

def download_url(url, out_path, referer=None, timeout=300):
    data = http_get(url, timeout=timeout, referer=referer)
    with open(out_path, "wb") as f:
        f.write(data)
    return len(data)


def download_sudugu(aid, out_dir):
    url = SOURCES["sudugu"]["download"].format(aid=aid)
    max_ch = None
    try:
        page = http_get(SOURCES["sudugu"]["page"].format(aid=aid), timeout=30).decode("gb18030", errors="replace")
        m = re.search(r"第([0-9]+)章", page)
        if m:
            max_ch = int(m.group(1))
    except Exception:
        pass
    parts = []
    if max_ch and max_ch > 800:
        print(f"  章节数 {max_ch}，分卷下载")
        for start in range(1, max_ch + 1, 500):
            end = min(start + 499, max_ch)
            u = url + f"&start={start}&end={end}"
            p = os.path.join(out_dir, f"part_{start}-{end}.bin")
            try:
                n = download_url(u, p, referer=SOURCES["sudugu"]["page"].format(aid=aid))
                parts.append(p)
                print(f"  part {start}-{end}: {n} bytes")
            except Exception as e:
                print(f"  part {start}-{end} 失败: {e}")
    else:
        p = os.path.join(out_dir, "book.bin")
        n = download_url(url, p, referer=SOURCES["sudugu"]["page"].format(aid=aid))
        parts.append(p)
        print(f"  下载完成: {n} bytes")
    return parts


def download_qiqixs(aid, name, out_dir):
    url = SOURCES["qiqixs"]["download"].format(aid=aid, name=urllib.parse.quote(name))
    p = os.path.join(out_dir, "book.bin")
    try:
        n = download_url(url, p, referer=SOURCES["qiqixs"]["page"].format(aid=aid))
        print(f"  直连成功: {n} bytes")
        return [p]
    except Exception as e:
        print(f"  直连失败({type(e).__name__}): 大概率是 Cloudflare 防护")
        print(f"  → 请用 agent-browser 打开: {url}")
        print(f"  → 或在浏览器手动访问（可能需勾选'请验证您是真人'），下载后放到: {p}")
        return []


def download_bookshuku(aid, out_dir):
    for ext, key in (("txt", "download"), ("zip", "zip")):
        url = SOURCES["bookshuku"][key].format(aid=aid)
        p = os.path.join(out_dir, f"book.{ext}")
        try:
            n = download_url(url, p, referer=SOURCES["bookshuku"]["page"].format(aid=aid))
            print(f"  [{ext}] 成功: {n} bytes")
            return [p]
        except Exception as e:
            print(f"  [{ext}] 失败({type(e).__name__}): 可能 Cloudflare 防护")
    print(f"  → 请用 agent-browser 打开: {SOURCES['bookshuku']['download'].format(aid=aid)}")
    return []


def download_baidupan(share_url, out_path):
    """百度网盘分享免登录下载"""
    html = http_get(share_url).decode("utf-8", errors="replace")

    def grab(p):
        m = re.search(p, html)
        return m.group(1) if m else None

    shareid = grab(r'"shareid"\s*:\s*"?(\d+)"?')
    uk = grab(r'"uk"\s*:\s*"?(\d+)"?')
    sign = grab(r'"sign"\s*:\s*"?([^"]+)"?')
    ts = grab(r'"timestamp"\s*:\s*"?([^"]+)"?')
    bdstoken = grab(r'"bdstoken"\s*:\s*"?([^"]+)"?')
    if not (shareid and sign and ts):
        errno = grab(r'"errno"\s*:\s*(-?\d+)')
        print(f"  分享页参数不全 (errno={errno})，链接可能已失效或需登录")
        return False
    wlist = json.loads(http_get(
        f"https://pan.baidu.com/share/wlist?shareid={shareid}&uk={uk}&fsid=-1"
        f"&order=time&desc=1&showempty=0&page=1&num=100"))
    if wlist.get("errno") != 0:
        print(f"  wlist errno={wlist.get('errno')}")
        return False
    flist = wlist["list"]
    print("  分享文件:", [(f["server_filename"], f["size"]) for f in flist])
    fid = flist[0]["fs_id"]
    dl = json.loads(http_post(
        f"https://pan.baidu.com/api/sharedownload?sign={sign}&timestamp={ts}"
        f"&bdstoken={bdstoken}&fid_list=[{fid}]&primaryid={shareid}&uk={uk}"
        f"&product=share&type=nolimit",
        {"encrypt": 0, "product": "share", "type": "nolimit"}))
    dlink = dl.get("dlink")
    if not dlink:
        print("  获取 dlink 失败:", str(dl)[:200])
        return False
    data = http_get(dlink, referer="https://pan.baidu.com/")
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"  下载成功: {len(data)} bytes")
    return True


# ---------------- 转码与验证 ----------------

def detect_encoding(data):
    for enc in ("utf-8", "gb18030"):
        try:
            data.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "gb18030"


def convert_and_verify(path, out_path=None):
    data = open(path, "rb").read()
    enc = detect_encoding(data)
    print(f"编码: {enc}")
    text = data.decode(enc, errors="replace")
    if out_path:
        with io.open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已转码保存: {out_path} ({os.path.getsize(out_path)} bytes)")
    chaps = re.findall(r"第\s*([0-9]+)\s*章", text)
    if chaps:
        nums = [int(c) for c in chaps]
        print(f"章节标题数: {len(chaps)}，范围: 第{min(nums)} ~ 第{max(nums)}章")
        uniq = sorted(set(nums))
        gaps = [uniq[i] + 1 for i in range(len(uniq) - 1) if uniq[i + 1] != uniq[i] + 1]
        if gaps:
            print(f"疑似缺章(断点后首章): {gaps[:10]}{'...' if len(gaps) > 10 else ''}")
        else:
            print("章节连续 OK")
    print(f"总字符数: {len(text)}")
    print("--- 开头 200 字 ---")
    print(text[:200].strip())
    print("--- 结尾 300 字 ---")
    print(text[-300:].strip())
    return text


# ---------------- 章节合并 ----------------

def parse_ranges(s):
    out = set()
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def merge_chapters(path, ranges, out_path):
    text = io.open(path, encoding="utf-8").read()
    chap_pat = re.compile(r"\n\s*第\s*([0-9]+)\s*章[^\n]*")
    chap_idx = []
    seen = set()
    for m in chap_pat.finditer(text):
        no = int(m.group(1))
        if no in seen:
            continue
        seen.add(no)
        chap_idx.append((no, m.start(), m.group(0).strip()))
    chap_idx.sort(key=lambda x: x[1])
    want = set(ranges)
    out = []
    for i in range(len(chap_idx)):
        no, pos, title = chap_idx[i]
        if no not in want:
            continue
        nxt = chap_idx[i + 1][1] if i + 1 < len(chap_idx) else len(text)
        body = text[pos:nxt].strip()
        lines = body.split("\n")
        tl = lines[0].strip() if lines else ""
        if tl:
            body = body.replace("\n" + tl, "\n", 1)
        out.append(f"\n\n{'='*60}\n【{no}】{tl}\n{'='*60}\n\n{body.strip()}")
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"合并完成: {out_path} ({os.path.getsize(out_path)} bytes)，共 {len(out)} 章")


# ---------------- 主入口 ----------------

def main():
    ap = argparse.ArgumentParser(description="网络小说 TXT 下载工具")
    ap.add_argument("subject", help="书名或文件路径")
    ap.add_argument("--search", action="store_true", help="站内搜索书籍 ID")
    ap.add_argument("--author", default=None, help="作者名（辅助选书）")
    ap.add_argument("--source", choices=["sudugu", "qiqixs", "bookshuku", "woshuge", "baidupan"], default=None)
    ap.add_argument("--id", default=None, help="数据源书籍 ID")
    ap.add_argument("--url", default=None, help="百度网盘分享链接")
    ap.add_argument("--out", default="d:/yousen/", help="输出目录或输出文件路径")
    ap.add_argument("--convert", action="store_true", help="转码为 UTF-8")
    ap.add_argument("--verify", action="store_true", help="完整性验证")
    ap.add_argument("--merge", default=None, help="合并章节，如 193,374-375")
    args = ap.parse_args()

    if args.search:
        search_all(args.subject, args.author)
        return

    if args.merge:
        merge_chapters(args.subject, parse_ranges(args.merge), args.out)
        return

    if args.convert or args.verify:
        out_path = None
        if args.convert:
            base = os.path.basename(args.subject)
            name = re.sub(r"\.(txt|bin|zip)$", "", base, flags=re.I)
            out_path = args.out if args.out.lower().endswith(".txt") else os.path.join(args.out, name + ".txt")
        convert_and_verify(args.subject, out_path)
        return

    if args.source == "baidupan":
        if not args.url:
            print("百度网盘需 --url 分享链接")
            return
        out_path = args.out if args.out.lower().endswith(".txt") else os.path.join(args.out, "baidupan.bin")
        download_baidupan(args.url, out_path)
        return

    if not args.id:
        print("请提供 --id（先用 --search 查找），或指定 --source baidupan --url")
        return

    os.makedirs(args.out, exist_ok=True)
    if args.source == "sudugu":
        parts = download_sudugu(args.id, args.out)
    elif args.source == "qiqixs":
        parts = download_qiqixs(args.id, args.subject, args.out)
    elif args.source == "bookshuku":
        parts = download_bookshuku(args.id, args.out)
    elif args.source == "woshuge":
        parts = download_woshuge(args.id, args.out)
    else:
        print(f"未知数据源: {args.source}")
        return

    # 下载完成后自动转码验证，并保存为 {书名}.txt（UTF-8）
    if parts:
        if len(parts) > 1:
            texts = []
            for p in parts:
                data = open(p, "rb").read()
                texts.append(data.decode(detect_encoding(data), errors="replace"))
            full = "".join(texts)
            out_path = os.path.join(args.out, args.subject + ".txt")
            with io.open(out_path, "w", encoding="utf-8") as f:
                f.write(full)
            print(f"\n== 分卷合并完成: {out_path} ({os.path.getsize(out_path)} bytes) ==")
            convert_and_verify(out_path)
        else:
            print(f"\n== 转码保存 ==")
            convert_and_verify(parts[0], os.path.join(args.out, args.subject + ".txt"))


if __name__ == "__main__":
    main()
