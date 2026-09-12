# -*- coding: utf-8 -*-
"""
用途：番茄书籍全史多维数据分析——用书籍创建日期自动计算历史天数，
      拉取全部统计维度（阅读/收藏/评论/互动/转化），识别高峰期/低谷期。
依赖：site-fanqienovel 技能目录下的 api_client.py 与 fanqienovel_auth.json 凭证。
用法：
  python analyze_book_trends.py                  # 全部书（自动全史）
  python analyze_book_trends.py <book_id>        # 指定书（自动全史）
  python analyze_book_trends.py <book_id> <days> # 指定天数
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = r"d:\temp\novel\.codebuddy\skills\site-fanqienovel"
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

from api_client import (
    get_book_list, get_book_detail, get_book_common_stats,
    get_book_increase_stats, get_chapter_stats,
)

# 抓包发现的 stats_types 组合（覆盖尽可能多维度）
TREND_GROUPS = [
    ("1,3,4,19,2,17,14", "阅读/核心"),
    ("24,27,26,25,28,29", "收藏/互动"),
    ("9,18,10,11,12,13", "转化/比率"),
]

# 按数据特征对每行维度命名（组合内按行序）
ROW_NAMES = {
    "1,3,4,19,2,17,14": {0: "每日阅读", 1: "14天累计阅读", 3: "评论数", 4: "收藏数"},
    "24,27,26,25,28,29": {0: "收藏数", 2: "评论数", 4: "读者互动", 5: "打赏/互动"},
    # 该组合返回比率维度，但当前无法仅凭接口字段确认对应截图哪一条曲线；不强行命名
    "9,18,10,11,12,13": {0: "比率维度0(%)", 1: "比率维度1(%)"},
}


def fmt_date(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%m-%d")
    except Exception:
        return str(ts)


def auto_days(book_id):
    """用书籍创建时间自动计算历史天数"""
    try:
        d = (get_book_detail(book_id).get("data") or {})
        ctime = d.get("create_time") or d.get("createTime") or ""
        if ctime:
            days = max(1, (int(time.time()) - int(ctime)) // 86400 + 1)
            return days, ctime
    except Exception:
        pass
    return 30, ""


def analyze_dimension(book_id, stats_types, days):
    """拉取指定维度组的全史趋势，对每行做峰谷分析"""
    now = int(time.time())
    start = now - days * 86400
    resp = get_book_increase_stats(book_id, start_date=str(start), end_date=str(now),
                                   stats_types=stats_types)
    dl = (resp.get("data") or {}).get("data_list") or []
    if not dl:
        return None

    base_date = datetime.fromtimestamp(start)
    results = []
    for i, row in enumerate(dl):
        if not row:
            continue
        # 日期推断
        dates = []
        for j, v in enumerate(row):
            try:
                iv = int(v)
                if 1000000000 < iv < 2000000000:
                    dates.append(datetime.fromtimestamp(iv).strftime("%m-%d"))
                else:
                    dates.append((base_date + timedelta(days=j)).strftime("%m-%d"))
            except Exception:
                dates.append((base_date + timedelta(days=j)).strftime("%m-%d"))

        # 判断是否数值/比率行
        is_ratio = any(isinstance(v, str) and "." in v for v in row[:5] if v)
        try:
            nums = [float(v) for v in row if str(v) not in ("", "0") and str(v) != "0.0"]
        except Exception:
            nums = []
        nonzero = len(nums)
        if nonzero == 0:
            continue

        peak_val, peak_idx = max(nums), nums.index(max(nums))
        valley_val, valley_idx = min(nums), nums.index(min(nums))
        total = sum(nums)

        name = ROW_NAMES.get(stats_types, {}).get(i, f"维度{i}")

        # 找真实日期（第一个日期行的值，用于把索引映射到日期）
        real_dates = []
        for j, v in enumerate(row):
            try:
                iv = int(v)
                if 1000000000 < iv < 2000000000:
                    real_dates.append(datetime.fromtimestamp(iv).strftime("%m-%d"))
            except Exception:
                pass
        # 用索引映射日期（若无真实日期行则用 start+index）
        def idx_date(j):
            return dates[j] if j < len(dates) else "?"

        results.append({
            "name": name, "row_idx": i, "nonzero": nonzero, "total": total,
            "peak": (idx_date(peak_idx), peak_val),
            "valley": (idx_date(valley_idx), valley_val),
            "is_ratio": is_ratio, "values": [str(v) for v in row],
            "real_dates_found": len(real_dates) > 0,
        })
    return results


def analyze_chapter_loss(book_id):
    """章节流失分析"""
    resp = get_chapter_stats(book_id, stats_type="3", latest_count=500, page_count=500)
    cl = (resp.get("data") or {}).get("chapter_stats_list") or []
    if not cl:
        return None
    chapters = []
    for c in cl:
        loss = c.get("loss_rate", "")
        try:
            loss_val = float(loss) if loss else None
        except Exception:
            loss_val = None
        chapters.append({"idx": c.get("indice", 0) + 1,
                         "title": c.get("title", ""),
                         "loss": loss_val})
    return chapters


def main():
    args = sys.argv[1:]
    only_id = args[0] if args else ""
    days_override = int(args[1]) if len(args) > 1 else 0

    books_resp = get_book_list(page_index=0, page_count=20)
    book_list = books_resp.get("data", {}).get("book_list") or []

    print("=" * 70)
    print("📊 番茄书籍全史多维数据分析")
    print("=" * 70)

    for book in book_list:
        bid = book.get("book_id")
        name = book.get("book_name") or "未知"
        if only_id and bid != only_id:
            continue
        wc = book.get("word_count", 0)
        ch_num = book.get("chapter_number", 0)

        # 自动计算历史天数
        days, ctime = auto_days(bid)
        if days_override:
            days = days_override

        print(f"\n{'─'*66}")
        print(f"📖 {name}  (book_id={bid})")
        print(f"   总字数 {wc} | {ch_num} 章")
        if ctime:
            print(f"   创建于 {datetime.fromtimestamp(int(ctime)).strftime('%Y-%m-%d')} "
                  f"→ 历史 {days} 天")

        # 通用统计
        common = get_book_common_stats(bid, stats_type="1")
        d = common.get("data") or {}
        uv = d.get("reader_uv_daily", "0")
        rc = d.get("read_completion_rate", "0")
        pr = d.get("pursue_read_rate", "0")
        uv_incr = d.get("reader_uv_daily_incr", "")
        print(f"   今日: 日活 {uv} (较昨{uv_incr}%) | 完读率 {rc}% | 追读率 {pr}%")

        # 各维度全史趋势
        print(f"   ── 全史 {days} 天趋势 ──")
        any_data = False
        for types_str, label in TREND_GROUPS:
            dims = analyze_dimension(bid, types_str, days)
            if not dims:
                continue
            for dim in dims:
                any_data = True
                if dim["is_ratio"]:
                    print(f"   📈 [{dim['name']}] {dim['values'][-1]}% "
                          f"(近值, 共{dim['nonzero']}天)")
                else:
                    print(f"   📈 [{dim['name']}] 累计{dim['total']} "
                          f"| 🔺峰 {dim['peak'][0]}={dim['peak'][1]} "
                          f"| 🔻谷 {dim['valley'][0]}={dim['valley'][1]}")
        if not any_data:
            print("   无历史数据（新书/未上架）")

        # 章节流失
        chapters = analyze_chapter_loss(bid)
        if chapters and chapters[0]["loss"] is not None:
            losses = [c["loss"] for c in chapters if c["loss"] is not None]
            avg_loss = sum(losses) / len(losses) if losses else 0
            worst = sorted(chapters, key=lambda c: (c["loss"] or 0), reverse=True)[:3]
            print(f"   ── 章节流失（平均{round(avg_loss,1)}%）──")
            for c in worst:
                print(f"   ⚠️ 第{c['idx']}章 {c['title'][:20]} 流失{c['loss']}%")


if __name__ == "__main__":
    main()
