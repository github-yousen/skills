# -*- coding: utf-8 -*-
"""
用途：查询指定书籍的每章数据表格（完读率/追读率/流失率/段评/催更/字数/发布时间）。
用法：python query_chapter_stats.py <book_id>          # 查某书全部章节
      python query_chapter_stats.py <book_id> <N>      # 只查最近 N 章
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import json
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import _req


def usage():
    print(__doc__)
    sys.exit(1)


def get_ch_stats(book_id, stats_type, latest_count):
    resp = _req("GET", "/api/author/stats/chapter_list_v1/v0/",
                params={"book_id": book_id, "stats_type": stats_type,
                        "page_count": latest_count, "page_index": 0,
                        "latest_count": latest_count})
    return (resp.get("data") or {}).get("chapter_stats_list") or []


def fmt(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%m-%d")
    except Exception:
        return str(ts)


def main():
    if len(sys.argv) < 2:
        usage()
    bid = sys.argv[1]
    latest = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    # 拉取三种 stats_type 数据，按 item_id 合并
    d3 = {c["item_id"]: c for c in get_ch_stats(bid, "3", latest)}     # 完读率/流失率
    d4 = {c["item_id"]: c for c in get_ch_stats(bid, "4", latest)}     # 追读率
    d567 = {c["item_id"]: c for c in get_ch_stats(bid, "5,6,7", latest)}  # 段评/章评/催更

    if not d3:
        print(f"[!] 未获取到章节数据，请检查 book_id={bid}")
        sys.exit(1)

    all_ids = sorted(d3.keys(), key=lambda x: d3[x].get("indice", 0))

    print(f"共 {len(all_ids)} 章（book_id={bid}）")
    print(f"{'章':<4}{'标题':<28}{'字数':>5}  {'完读%':>6}{'追读%':>6}{'流失%':>6}{'段评':>4}{'催更':>4}  {'发布于'}")
    print("-" * 90)
    for iid in all_ids:
        c3 = d3[iid]
        c4 = d4.get(iid, {})
        c5 = d567.get(iid, {})
        title = c3.get("title", "")[:26]
        idx = c3.get("indice", 0) + 1
        wc = c3.get("word_number", 0)
        rc = c3.get("read_completion_rate", "")
        fl = c3.get("loss_rate", "")
        fr = c4.get("follow_read_rate", "")
        para = c5.get("comment_paragraph_cnt", 0)
        remind = c5.get("reminder_cnt", 0)
        pt = fmt(c3.get("publish_time", ""))
        print(f"第{idx:<3}{title:<28}{wc:>5}  {rc:>6}{fr:>6}{fl:>6}{para:>4}{remind:>4}  {pt}")


if __name__ == "__main__":
    main()
