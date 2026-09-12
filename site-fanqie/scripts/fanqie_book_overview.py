# -*- coding: utf-8 -*-
"""查看番茄作者后台全部书籍的简洁概览（书名/状态/阶段/字数/各卷章节发布情况），用于快速了解发布状态。"""
import sys, os, json

# 确保能从技能目录导入 api_client（脚本可被任意 cwd 调用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import get_book_list, get_volume_list, get_chapter_list

books = get_book_list(page_index=0, page_count=50).get("data", {}).get("book_list", [])
print(f"共 {len(books)} 本书：")
print("=" * 80)
for b in books:
    bid = str(b.get("book_id"))
    name = b.get("book_name", "")
    intro = b.get("book_intro") or {}
    status = intro.get("status", "")
    tag = intro.get("tag", "")
    word = b.get("total_word_count") or b.get("word_count") or 0
    sec = b.get("security_status")
    print(f"■ {name}  (id={bid}, {word}字, intro.status={status}, tag={tag}, security={sec})")
    vols = get_volume_list(bid).get("data", {}).get("volume_list", [])
    for v in vols:
        vid = str(v.get("volume_id"))
        try:
            clist = []
            for pi in range(0, 20):
                chs = get_chapter_list(bid, vid, page_index=pi, page_count=15, status="0")
                items = (chs.get("data", {}) or {}).get("item_list") or []
                if not items:
                    break
                clist.extend(items)
        except Exception:
            clist = []
        published = sum(1 for c in clist if str(c.get("article_status")) == "1")
        hidden = sum(1 for c in clist if str(c.get("article_status")) == "2")
        draft = sum(1 for c in clist if str(c.get("article_status")) == "0")
        print(f"    卷「{v.get('volume_name','')}」 共{len(clist)}章: 已发布{published} / 断更隐藏{hidden} / 草稿{draft}")
print("=" * 80)
