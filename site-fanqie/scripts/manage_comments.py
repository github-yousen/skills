# -*- coding: utf-8 -*-
"""
用途：查看和回复读者评论（书评/章评/段评），管理粉丝互动。
用法：
  python manage_comments.py <book_id>                          # 查看书评列表
  python manage_comments.py <book_id> --chapter <item_id>      # 查看某章章评
  python manage_comments.py <book_id> --reply <comment_id> "回复内容"  # 回复评论
  python manage_comments.py <book_id> --fans                   # 查看粉丝列表
  python manage_comments.py <book_id> --like <comment_id>      # 点赞评论
  python manage_comments.py <book_id> --delete <comment_id>    # 删除评论
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import (
    get_book_comment_list, get_chapter_comment_list, get_reply_comment_list,
    reply_comment, delete_comment, digg_comment, stick_comment,
    get_comment_report_type_list, get_fan_list,
)


def fmt_time(ts):
    import datetime
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def show_comments(book_id, comment_list, label="书评"):
    """打印评论列表"""
    if not comment_list:
        print(f"  无{label}")
        return
    for c in comment_list:
        cid = c.get("comment_id", "")
        content = (c.get("content") or "")[:60]
        author = c.get("user_name") or c.get("nick_name") or "匿名"
        digg = c.get("digg_count", "0")
        ctime = fmt_time(c.get("create_time", ""))
        is_top = "📌" if c.get("is_stick") else " "
        print(f"  {is_top} [{cid[-8:]}] {author}: {content}  (赞{digg}, {ctime})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    book_id = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else ""

    if action == "--chapter":
        # 查看某章章评
        item_id = sys.argv[3]
        print(f"=== 第{item_id}章 章评 ===\n")
        r = get_chapter_comment_list(book_id, item_id, page_count=20)
        comments = (r.get("data") or {}).get("comment_list") or []
        show_comments(book_id, comments, "章评")

    elif action == "--reply":
        # 回复评论
        comment_id = sys.argv[3]
        content = sys.argv[4]
        print(f"回复评论 {comment_id}: {content}")
        r = reply_comment(comment_id, content)
        print(f"  code={r.get('code')} msg={r.get('message', '')}")

    elif action == "--like":
        # 点赞评论
        comment_id = sys.argv[3]
        r = digg_comment(comment_id, "1")
        print(f"点赞 {comment_id}: code={r.get('code')} msg={r.get('message', '')}")

    elif action == "--delete":
        # 删除评论
        comment_id = sys.argv[3]
        r = delete_comment(comment_id, book_id)
        print(f"删除 {comment_id}: code={r.get('code')} msg={r.get('message', '')}")

    elif action == "--fans":
        # 粉丝列表
        print(f"=== 粉丝列表 ===\n")
        r = get_fan_list(book_id, page_count=50)
        fans = (r.get("data") or {}).get("fan_list") or []
        if not fans:
            print("  无粉丝")
        for f in fans:
            print(f"  [{f.get('fan_id','')}] {f.get('fan_name','')}  关注时间={fmt_time(f.get('create_time',''))}")

    elif action == "--types":
        # 举报类型
        r = get_comment_report_type_list()
        types = (r.get("data") or {}).get("report_list") or []
        print("举报类型:")
        for t in types:
            print(f"  {t['report_id']}: {t['report_value']}")

    else:
        # 默认：查看书评列表
        print(f"=== 书评列表 (book_id={book_id}) ===\n")
        r = get_book_comment_list(book_id, page_count=20)
        comments = (r.get("data") or {}).get("comment_list") or []
        show_comments(book_id, comments, "书评")
        print(f"\n共 {len(comments)} 条")


if __name__ == "__main__":
    main()
