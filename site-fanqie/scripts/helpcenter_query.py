# -*- coding: utf-8 -*-
"""
番茄帮助中心 / 作家课堂查询工具（免登录，直接调用）
用法（CLI 子命令）:
  py helpcenter_query.py tree                          # 帮助中心三级分类树
  py helpcenter_query.py article <category_id> [--save [路径]]  # 文章详情（默认打印纯文本正文；--save 可选存 HTML 源）
  py helpcenter_query.py search <关键词> [页码=1]       # 搜索帮助文章
  py helpcenter_query.py tutorials [tab] [页码=0]      # 作家课堂教程列表
  py helpcenter_query.py list-help                     # 遍历全部帮助文章清单（108篇，稍慢）

tab 可选: 1=新手专区 2=大神专访 3=写作技巧 4=品类指南 5=平台宝典（默认，也支持中文tab名）

接口（2026-08-25 实测免登录可用）:
- GET /api/author/hfc/all_category/v0/            分类树
- GET /api/author/hfc/article_info/v0/?category_id=xx    文章详情
- GET /api/author/hfc/search_article/v0/?query=xx&page_index=1&page_count=10  搜索
- GET /api/node/tutorial/list?type=5&page_index=0&page_count=15   教程列表
"""
import sys
import os
import json
import time
import urllib.request
import urllib.parse
import ssl
import io

# Windows GBK 控制台兼容
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

_BASE = "https://fanqienovel.com"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

TAB_NAMES = {1: "新手专区", 2: "大神专访", 3: "写作技巧", 4: "品类指南", 5: "平台宝典"}
_NAME_TO_TAB = {v: k for k, v in TAB_NAMES.items()}


def _get(path, params=None):
    url = _BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://fanqienovel.com/writer/zone/help",
    })
    with urllib.request.urlopen(req, context=_CTX, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_tree():
    j = _get("/api/author/hfc/all_category/v0/")
    if j.get("code") != 0:
        print("接口返回异常:", j.get("message"))
        return
    def walk(items, depth=0):
        for it in items:
            print("  " * depth + f"- {it['title']} (category_id={it['category_id']})")
            walk(it.get("child_category") or [], depth + 1)
    walk(j["data"])


def cmd_article(cid, save=None):
    j = _get("/api/author/hfc/article_info/v0/", {"category_id": cid})
    if j.get("code") != 0 or not j.get("data"):
        print("无文章:", j.get("message") or "该分类下没有文章")
        return
    d = j["data"]
    print(f"标题: {d.get('title')}")
    print(f"item_id: {d.get('item_id')}")
    print(f"更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(d['modify_time']))}")
    content = d.get("content") or ""
    # 打印纯文本正文
    import re
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    print(f"\n正文: {text}")
    if save:
        out = save if save != "1" else os.path.join(os.getcwd(), f"help_article_{cid}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\nHTML源已保存: {os.path.abspath(out)}")


def cmd_search(kw, page=1):
    j = _get("/api/author/hfc/search_article/v0/",
             {"query": kw, "page_index": page, "page_count": 10})
    if j.get("code") != 0:
        print("接口返回异常:", j.get("message"))
        return
    lst = (j.get("data") or {}).get("search_list") or []
    import re
    if not lst:
        print(f"第{page}页无结果")
        return
    print(f"共找到（第{page}页 {len(lst)} 条）:")
    for it in lst:
        pc = it.get("parent_category") or {}
        title = re.sub(r"<[^>]+>", "", it.get("title_highlight", ""))
        print(f"  - {title} (category_id={it.get('category_id')}, item_id={it.get('item_id')}, "
              f"rank1={pc.get('1')}, rank2={pc.get('2')}, rank3={pc.get('3')})")
    print("提示: 打开 /writer/zone/help/article?rank1={1}&rank2={2}&rank3={3} 查看对应文章")


def cmd_tutorials(tab, page):
    t = tab if isinstance(tab, int) else (TAB_NAMES.get(tab) and tab or None)
    if t is None:
        # 尝试解析名称或数字
        t = _NAME_TO_TAB.get(str(tab)) or (int(tab) if str(tab).isdigit() else None)
    if t not in TAB_NAMES:
        print(f"无效 tab: {tab}，可选: " + ", ".join(f"{k}={v}" for k, v in TAB_NAMES.items()))
        return
    j = _get("/api/node/tutorial/list", {"type": t, "page_index": page, "page_count": 15})
    data = j.get("data") or {}
    lst = data.get("tutorial_list") or []
    if j.get("code") not in (0, None) and not lst:
        print("接口返回异常:", j.get("message"))
        return
    print(f"[{TAB_NAMES[t]}] 第{page + 1}页，共 {data.get('total_count', '?')} 篇:")
    for i, it in enumerate(lst, 1):
        video = " [视频]" if it.get("is_video") == 1 else ""
        print(f"  {i}. {it.get('title')}（{it.get('time')}）{video}")
        print(f"     链接: {it.get('link')}")


def cmd_list_help():
    j = _get("/api/author/hfc/all_category/v0/")
    if j.get("code") != 0:
        print("分类树接口异常:", j.get("message"))
        return
    leaves = []
    def walk(items, path):
        for it in items:
            p = path + [it["title"]]
            kids = it.get("child_category") or []
            if not kids:
                leaves.append((it["category_id"], p))
            else:
                walk(kids, p)
    walk(j["data"], [])
    print(f"叶子分类 {len(leaves)} 个，开始拉取文章...")
    n = 0
    for i, (cid, path) in enumerate(leaves, 1):
        try:
            a = _get("/api/author/hfc/article_info/v0/", {"category_id": cid})
            if a.get("code") == 0 and a.get("data"):
                n += 1
                print(f"  [{i}/{len(leaves)}] {' > '.join(path)} -> {a['data'].get('title')}")
            else:
                print(f"  [{i}/{len(leaves)}] {' > '.join(path)} -> (无文章)")
        except Exception as e:
            print(f"  [{i}/{len(leaves)}] {cid} 请求失败: {e}")
        time.sleep(0.1)
    print(f"完成: 共 {n} 篇文章")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "tree":
        cmd_tree()
    elif cmd == "article" and len(args) >= 2:
        # article <category_id> [--save [路径]]：默认只打印，--save 可选存 HTML 源
        save = None
        rest = args[2:]
        if "--save" in rest:
            i = rest.index("--save")
            save = rest[i + 1] if i + 1 < len(rest) and not rest[i + 1].startswith("--") else "1"
        cmd_article(args[1], save)
    elif cmd == "search" and len(args) >= 2:
        cmd_search(args[1], int(args[2]) if len(args) > 2 else 1)
    elif cmd == "tutorials":
        tab = args[1] if len(args) > 1 else "5"
        page = int(args[2]) if len(args) > 2 else 0
        cmd_tutorials(tab, page)
    elif cmd == "list-help":
        cmd_list_help()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
