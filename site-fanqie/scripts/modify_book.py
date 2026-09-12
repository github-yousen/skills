# 修改书籍信息（书名/简介/感谢语等）
# 用途：调用番茄 modify_book 接口修改书籍信息。实测需用 /app/book/modify_book/v0/ 才生效
# 用法:
#   python modify_book.py                     # 列出所有书，交互选择
#   python modify_book.py <book_id> --summary "新简介"
#   python modify_book.py <book_id> --name "新书名"
#   python modify_book.py <book_id> --gift-word "新感谢语"
#   python modify_book.py <book_id> --show    # 查看当前信息
import sys
import os
import json
import argparse

# 修复 Windows 默认 GBK 编码导致 emoji/中文输出崩溃
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 确保能导入同目录的 api_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_client import _req, modify_book_info, get_book_list


def show_book(book_id):
    """查看书籍详情"""
    d = _req('GET', '/api/author/book/book_detail/v0/', params={'book_id': book_id}).get('data', {})
    print(f"\n书名: {d.get('book_name')}")
    print(f"ID: {book_id}")
    print(f"简介: {d.get('abstract', '')[:200]}")
    print(f"感谢语: {d.get('gift_word', '')}")
    print(f"角色: {d.get('roles', [])}")
    cats = d.get('category', [])
    if cats:
        parts = []
        for c in cats:
            parts.append(f"{c.get('name','')}({c.get('label','')})")
        print("分类: " + ", ".join(parts))
    print(f"状态: status={d.get('status')} sign={d.get('sign_progress')} can_modify={d.get('can_modify')}")


def interactive_select():
    """列出所有书，返回选中的 book_id"""
    books = get_book_list(page_index=0, page_count=50)['data']['book_list']
    print("\n=== 书籍列表 ===")
    for i, b in enumerate(books, 1):
        print(f"{i}. {b['book_name']} (ID: {b['book_id']})")
    sel = input("\n选择书籍编号 (1-%d): " % len(books)).strip()
    try:
        return books[int(sel) - 1]['book_id']
    except Exception:
        print("无效选择")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='修改番茄小说书籍信息')
    parser.add_argument('book_id', nargs='?', help='书籍ID，缺省则列出选择')
    parser.add_argument('--summary', help='新简介')
    parser.add_argument('--name', help='新书名')
    parser.add_argument('--gift-word', help='新感谢语')
    parser.add_argument('--show', action='store_true', help='查看当前信息')
    parser.add_argument('--category', help='分类（签约书不可修改，勿用）')
    args = parser.parse_args()

    book_id = args.book_id
    if not book_id:
        book_id = interactive_select()

    if args.show or not (args.summary or args.name or args.gift_word):
        show_book(book_id)
        if not (args.summary or args.name or args.gift_word):
            print("\n提示: 使用 --summary/--name/--gift-word 参数修改对应字段")
            return

    # 组装修改字段
    fields = {}
    if args.summary:
        fields['summary'] = args.summary
    if args.name:
        fields['book_name'] = args.name
    if args.gift_word:
        fields['gift_word'] = args.gift_word

    print(f"\n=== 修改书籍 {book_id} ===")
    for k, v in fields.items():
        print(f"  {k}: {str(v)[:80]}...")
    if args.category:
        fields['category'] = args.category
        print("  ⚠️ 注意: 签约书传 category 会被拒绝")

    r = modify_book_info(book_id, **fields)
    print(f"\n返回: {json.dumps(r, ensure_ascii=False)[:300]}")

    if r.get('code') == 0:
        print("✅ 修改成功")
        # 验证
        d = _req('GET', '/api/author/book/book_detail/v0/', params={'book_id': book_id}).get('data', {})
        if args.summary:
            ok = d.get('abstract', '') == args.summary
            print(f"  简介验证: {'✅ 已生效' if ok else '⚠️ 未生效'}")
        if args.name:
            ok = d.get('book_name', '') == args.name
            print(f"  书名验证: {'✅ 已生效' if ok else '⚠️ 未生效'}")
    else:
        print(f"❌ 失败: {r.get('message')}")


if __name__ == '__main__':
    main()
