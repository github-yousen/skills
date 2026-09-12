# -*- coding: utf-8 -*-
"""
用途：每日签到/请假/签到券管理，保障全勤奖收益。
用法：
  python attend.py <book_id>                        # 每日签到
  python attend.py <book_id> --leave "yyyy-mm-dd"  # 请假（避免断更清零）
  python attend.py <book_id> --ticket <ticket_id>  # 使用签到券补签
  python attend.py --status                        # 查看签到券状态
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import json
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import (
    attend_book, ask_for_leave, use_check_in_ticket,
    get_check_in_ticket_count, get_check_in_ticket_list, get_attend_book_list,
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--status":
        # 查看签到券状态
        print("=== 签到券状态 ===\n")
        r = get_check_in_ticket_count()
        print(f"签到券数量: {json.dumps(r.get('data'), ensure_ascii=False)}")
        r2 = get_check_in_ticket_list()
        tickets = (r2.get("data") or {}).get("ticket_list") or []
        for t in tickets:
            print(f"  券ID={t.get('ticket_id','')} 过期={t.get('expire_time','')}")
        return

    book_id = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else ""

    if action == "--leave":
        # 请假
        date = sys.argv[3]
        print(f"请假: book_id={book_id} date={date}")
        r = ask_for_leave(book_id, date)
        print(f"  code={r.get('code')} msg={r.get('message', '')}")

    elif action == "--ticket":
        # 使用签到券补签
        ticket_id = sys.argv[3]
        print(f"使用签到券: ticket_id={ticket_id} book_id={book_id}")
        r = use_check_in_ticket(ticket_id, book_id)
        print(f"  code={r.get('code')} msg={r.get('message', '')}")

    else:
        # 默认：每日签到
        today = datetime.date.today().strftime("%Y-%m-%d")
        print(f"每日签到: book_id={book_id} date={today}")
        r = attend_book(book_id)
        print(f"  code={r.get('code')} msg={r.get('message', '')}")
        if r.get("code") == 0:
            print("  ✅ 签到成功！")
        elif "已签到" in (r.get("message") or "") or r.get("code") == -2:
            print("  （今日已签到或不可重复签到）")


if __name__ == "__main__":
    main()
