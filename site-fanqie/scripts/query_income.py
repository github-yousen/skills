# -*- coding: utf-8 -*-
"""
用途：查询番茄小说作者后台收益数据（单本汇总/每日明细/月度/礼物/互动）
用法：python query_income.py [book_id]
      python query_income.py              # 全部书籍
      python query_income.py <book_id>    # 只查某书
说明：
  - 收益核心接口需要 VM 加密（X-Muye-Encrypt-Key），通过 fanqie_encrypt.js 完成
  - 依赖：在技能目录执行 npm install crypto-js bignumber.js
"""
import os
import sys
import json
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import (
    get_income_book_list, get_income_book_summary, get_income_book_daily,
    get_income_book_monthly, get_income_gift_summary, get_income_interaction_summary,
    get_income_compensation_list,
)


def ts_to_date(ts):
    """秒级时间戳 -> yyyy-mm-dd"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(ts)


def ts_to_month(ts):
    """秒级时间戳 -> yyyy-mm"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m")
    except (TypeError, ValueError):
        return str(ts)


def fmt(v):
    """金额格式化"""
    try:
        return f"¥{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def query_one_book(book_id, book_name=""):
    """查询单本书收益"""
    print(f"\n{'='*70}")
    print(f"📖 {book_name or book_id}  (book_id={book_id})")
    print(f"{'='*70}")

    # 1. 收益汇总
    print("\n【收益汇总】")
    try:
        s = get_income_book_summary(book_id)
        d = s.get("data") or {}
        if s.get("code") == 0 and d:
            print(f"  累计番茄APP收入: {fmt(d.get('novel_app_income', 0))}")
            print(f"  昨日收入:       {fmt(d.get('yesterday_income_novel_app', 0))}")
            print(f"  增长率:         {d.get('novel_app_increase', '-')}%")
            print(f"  数据就绪:       {'是' if d.get('is_data_ready') == 1 else '否'}")
        else:
            print(f"  [!] code={s.get('code')} msg={s.get('message')}")
    except Exception as e:
        print(f"  [!] 失败: {e}")

    # 2. 每日明细（近7天）
    print("\n【每日收益明细（近7天）】")
    try:
        now = int(time.time())
        start = str(now - 7 * 86400)
        daily = get_income_book_daily(book_id, start_date=start, end_date=str(now))
        d = daily.get("data") or {}
        if daily.get("code") == 0 and d.get("income_daily_list"):
            print(f"  {'日期':<12} {'阅读费':>8} {'听书费':>8} {'合计':>8}")
            print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
            for item in d["income_daily_list"]:
                date = ts_to_date(item.get("date", ""))
                read_fee = fmt(item.get("novel_app_read_fee", 0))
                listen_fee = fmt(item.get("novel_app_listen_fee", 0))
                total = fmt(item.get("novel_app_total", 0))
                print(f"  {date:<12} {read_fee:>8} {listen_fee:>8} {total:>8}")
        else:
            print(f"  [!] 无数据 code={daily.get('code')}")
    except Exception as e:
        print(f"  [!] 失败: {e}")

    # 3. 月度收益
    print("\n【月度收益（近半年）】")
    try:
        now = int(time.time())
        start = str(now - 180 * 86400)
        monthly = get_income_book_monthly(book_id, start_date=start, end_date=str(now))
        d = monthly.get("data") or {}
        if monthly.get("code") == 0 and d.get("income_monthly_list"):
            print(f"  {'月份':<8} {'总收入':>10} {'阅读费':>10} {'听书费':>10} {'礼物':>8}")
            print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
            for item in d["income_monthly_list"]:
                month = item.get("month", "")
                total = fmt(item.get("total", 0))
                detail = item.get("detail") or {}
                read_fee = fmt(detail.get("novel_app_read_fee", 0))
                listen_fee = fmt(detail.get("novel_app_listen_fee", 0))
                gift = fmt(detail.get("novel_app_gift", 0))
                print(f"  {month:<8} {total:>10} {read_fee:>10} {listen_fee:>10} {gift:>8}")
        else:
            print(f"  [!] 无数据 code={monthly.get('code')}")
    except Exception as e:
        print(f"  [!] 失败: {e}")

    # 4. 礼物收益
    print("\n【礼物收益】")
    try:
        gift = get_income_gift_summary(book_id)
        d = gift.get("data") or {}
        if gift.get("code") == 0 and d:
            print(f"  礼物总收入: {fmt(d.get('gift_income', 0))}")
            print(f"  礼物数量:   {d.get('gift_count', 0)}")
        else:
            print(f"  [!] 无数据")
    except Exception as e:
        print(f"  [!] 失败: {e}")

    # 5. 互动收益
    print("\n【互动收益】")
    try:
        inter = get_income_interaction_summary(book_id)
        d = inter.get("data") or {}
        if inter.get("code") == 0 and d:
            print(f"  互动收入: {fmt(d.get('interaction_income', 0))}")
            print(f"  礼物数量: {d.get('gift_count', 0)}")
        else:
            print(f"  [!] 无数据")
    except Exception as e:
        print(f"  [!] 失败: {e}")


def main():
    book_id = sys.argv[1] if len(sys.argv) > 1 else ""

    if book_id:
        # 查单本书
        query_one_book(book_id)
    else:
        # 查全部书籍
        print("=== 收益页书籍列表 ===")
        try:
            bl = get_income_book_list()
            d = bl.get("data") or {}
            books = d.get("income_book_list") or []
            print(f"共 {d.get('total_count', 0)} 本有收益入口的书籍\n")
            for b in books:
                bid = b.get("book_id", "")
                name = b.get("book_name", "")
                ct = b.get("contract_type", "")
                ct_str = {1: "分成", 2: "买断", 3: "分成(签约)"}.get(ct, str(ct))
                print(f"  📖 {name}  (book_id={bid}, 签约类型={ct_str})")
                query_one_book(bid, name)
        except Exception as e:
            print(f"[!] 获取书籍列表失败: {e}")

    # 收益补偿
    print(f"\n{'='*70}")
    print("【收益补偿】")
    try:
        comp = get_income_compensation_list()
        d = comp.get("data") or {}
        cl = d.get("compensation_list") or []
        if cl:
            for c in cl:
                print(f"  {json.dumps(c, ensure_ascii=False)[:200]}")
        else:
            print("  无补偿记录")
    except Exception as e:
        print(f"  [!] 失败: {e}")


if __name__ == "__main__":
    main()
