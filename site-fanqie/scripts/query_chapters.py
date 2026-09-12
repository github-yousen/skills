# -*- coding: utf-8 -*-
"""
用途：查询番茄作者后台书籍/章节状态（含隐藏/断更识别）。
用法：python query_chapters.py                  # 只列出全部书籍（不拉章节），确定书后
      python query_chapters.py <book_id>        # 列出书籍，并拉取指定书的章节
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import json
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import get_book_list, get_volume_list, get_chapter_list

ARTICLE_STATUS = {
    "0": "草稿",
    "1": "已发布",
    "2": "断更/隐藏",   # 实测：article_status=2 是断更/隐藏，不是审核中
    "3": "已驳回",
    "4": "已下架",
}


def fmt_time(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def status_of(ch):
    """返回 (状态名, 隐藏标志, 说明)。隐藏/断更通过 cant_modify_reason 识别。"""
    st = str(ch.get("article_status", ch.get("display_status", "?")))
    st_name = ARTICLE_STATUS.get(st, f"状态{st}")
    reason = ch.get("cant_modify_reason", "") or ""
    hidden = bool(reason and "断更" in reason)
    return st_name, hidden, reason


def query_book(book_id):
    try:
        vol_resp = get_volume_list(book_id)
        vols = vol_resp.get("data", {}).get("volume_list") or []
    except Exception as e:
        print(f"  获取卷列表失败：{e}")
        return
    for vol in vols:
        vol_id = vol.get("volume_id")
        vol_name = vol.get("volume_name") or "默认卷"
        print(f"  [卷] {vol_name}  (volume_id={vol_id})")
        page_index = 0
        while True:
            ch_resp = get_chapter_list(book_id, volume_id=vol_id or "",
                                       page_index=page_index, page_count=15, status="0")
            data = ch_resp.get("data", {}) or {}
            items = data.get("item_list") or []
            if not items:
                break
            for ch in items:
                idx = ch.get("index", "")
                ch_title = ch.get("title") or "无标题"
                st_name, hidden, reason = status_of(ch)
                item_id = ch.get("item_id")
                wc = ch.get("word_number", "")
                ctime = fmt_time(ch.get("create_time", ""))
                mark = "★" if ch.get("article_status") == 1 else " "
                h_flag = " [隐藏]" if hidden else ""
                r_text = f" 原因:{reason}" if reason else ""
                print(f"    {mark} [{st_name}]{h_flag} 第{idx}章 {ch_title}  "
                      f"(item_id={item_id}, {wc}字, 创建={ctime}, can_delete={ch.get('can_delete')}){r_text}")
            page_index += 1
            if page_index * 15 >= 200:
                break


def main():
    books_resp = get_book_list(page_index=0, page_count=20)
    book_list = books_resp.get("data", {}).get("book_list") or []
    if not book_list:
        print("未查询到书籍：", json.dumps(books_resp, ensure_ascii=False)[:800])
        return

    only_id = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"共 {len(book_list)} 本书：\n")
    for book in book_list:
        book_id = book.get("book_id") or book.get("id")
        title = book.get("book_name") or book.get("name") or "未知书名"
        if only_id and book_id != only_id:
            continue
        word_count = book.get("word_count", "")
        print("=" * 64)
        print(f"书籍：{title}  (book_id={book_id}, 全书{word_count}字)")
        if only_id:
            query_book(book_id)
        print()

    if not only_id:
        print("提示：确定书籍后，用 python query_chapters.py <book_id> 查看对应章节")


if __name__ == "__main__":
    main()
