# -*- coding: utf-8 -*-
"""
用途：查询书籍数据统计汇总（日活阅读/完读率/追读率/30天趋势/章节概况）。
用法：python query_stats.py                  # 全部书籍
      python query_stats.py <book_id>        # 只查某本书
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import (
    get_book_list, get_stats_book_list, get_book_common_stats,
    get_book_increase_stats, get_chapter_stats,
)


def fmt(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%m-%d %H:%M")
    except Exception:
        return str(ts)


def main():
    only_id = sys.argv[1] if len(sys.argv) > 1 else ""

    # 统计页书籍列表（page_count=-1 表示全部，实测）
    stats_books = get_stats_book_list(page_index=0, page_count=-1)
    sbl = stats_books.get("data", {}).get("book_list") or []
    print(f"统计页书籍: {len(sbl)} 本")

    books_resp = get_book_list(page_index=0, page_count=20)
    book_list = books_resp.get("data", {}).get("book_list") or []
    now = int(time.time())

    for book in book_list:
        bid = book.get("book_id")
        name = book.get("book_name") or "未知"
        if only_id and bid != only_id:
            continue
        print("\n" + "=" * 66)
        print(f"📖 {name}  (book_id={bid})")
        print(f"   总字数: {book.get('word_count')} | 章节数: {book.get('chapter_number')} | "
              f"最新章节: {book.get('last_chapter_title')}")

        # 通用统计（stats_type=1 常规）
        try:
            common = get_book_common_stats(bid, stats_type="1")
            d = common.get("data") or {}
            update = d.get("update_time") or ""
            print(f"   数据更新: {fmt(update) if update and update != '0' else '未更新'}")
            for k in ["reader_uv_daily", "read_completion_rate", "pursue_read_rate",
                      "add_bookshelf", "read_count", "comment_count", "risk_rate"]:
                if k in d and str(d[k]) not in ("", "0", "-1"):
                    print(f"     {k}: {d[k]}")
        except Exception as e:
            print(f"   通用统计失败: {e}")

        # 30天趋势（stats_types=1,3,4,19,2,17,14）
        try:
            inc = get_book_increase_stats(bid, start_date=str(now - 30 * 86400),
                                          end_date=str(now),
                                          stats_types="1,3,4,19,2,17,14")
            dl = (inc.get("data") or {}).get("data_list") or []
            if dl:
                non_zero = sum(1 for v in dl[0] if str(v) not in ("", "0"))
                total = sum(int(v) for v in dl[0] if str(v).isdigit()) if dl[0] else 0
                print(f"   30天阅读趋势: 有数据 {non_zero} 天, 累计 {total}")
        except Exception as e:
            print(f"   趋势统计失败: {e}")

        # 章节概况
        try:
            chs = get_chapter_stats(bid, stats_type="3", latest_count=30, page_count=30)
            cd = chs.get("data") or {}
            cl = cd.get("chapter_stats_list") or []
            print(f"   章节统计: {cd.get('total_count')} 章")
            for ch in cl[:5]:
                title = ch.get("title", "")
                wc = ch.get("word_number", "")
                pt = fmt(ch.get("publish_time", ""))
                print(f"     - {title} ({wc}字, 发布于{pt})")
        except Exception as e:
            print(f"   章节统计失败: {e}")


if __name__ == "__main__":
    main()
