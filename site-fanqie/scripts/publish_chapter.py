# -*- coding: utf-8 -*-
"""
用途：发布/更新番茄小说章节（创建->预审->发布 全流程，支持定时发布）。
用法：python publish_chapter.py <book_id> <content.md路径> [volume_id] [volume_name] [item_id] [--timer "2026-08-10 18:00"]
      python publish_chapter.py <book_id> <content.md> [volume_id] [volume_name] [item_id]  # 立即发布
      python publish_chapter.py <book_id> <content.md> --timer "2026-08-10 18:00"            # 定时发布
说明：
  - 默认自动取该 book 第一卷做发布；可传 volume_id / volume_name 覆盖
  - content.md 第一行须为 `# 第X章 标题`，其余为正文（标题不会进正文）
  - 传 item_id 时表示更新/重发该章节（不新建）
  - --timer "yyyy-mm-dd HH:MM" 指定定时发布时间（秒级时间戳传给后端）
依赖：api_client.py（同目录）与 fanqienovel_auth.json 凭证。
"""
import os
import sys
import json
import re
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from api_client import (
    get_volume_list, new_article, pre_audit_article, publish_article,
    chapter_md_to_html,
)


def usage():
    print(__doc__)
    sys.exit(1)


def parse_timer_arg(argv):
    """从参数列表提取 --timer 值，返回 (timer_str, 剩余参数)"""
    timer_str = ""
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == "--timer" and i + 1 < len(argv):
            timer_str = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return timer_str, rest


def timer_to_timestamp(timer_str):
    """将 'yyyy-mm-dd HH:MM' 或 'yyyy-mm-dd HH:MM:SS' 转为秒级时间戳字符串"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(timer_str.strip(), fmt)
            ts = int(dt.timestamp())
            # 定时时间必须在未来
            if ts <= int(datetime.now().timestamp()):
                print(f"[!] 定时时间 {timer_str} 已过期，请指定未来时间")
                sys.exit(1)
            return str(ts)
        except ValueError:
            continue
    # 尝试纯数字（已经是时间戳）
    if timer_str.strip().isdigit():
        return timer_str.strip()
    print(f"[!] 无法解析时间: {timer_str}，支持格式: yyyy-mm-dd HH:MM")
    sys.exit(1)


def publish_chapter_from_md_timer(book_id, volume_id, volume_name, md_text,
                                   item_id=None, timer_time=None):
    """从整章 Markdown 发布章节，支持定时"""
    title, body_html = chapter_md_to_html(md_text)
    result = {"title": title, "item_id": item_id, "ok": False}

    # ① 创建或复用章节
    if not item_id:
        new_resp = new_article(book_id, volume_id)
        data = new_resp.get("data") or {}
        item_id = data.get("item_id") or data.get("id") or new_resp.get("item_id")
        if not item_id:
            result["new"] = new_resp
            result["error"] = f"创建章节失败: {new_resp.get('message')}"
            return result
        result["new"] = new_resp
        result["item_id"] = item_id

    # ② 预审
    result["audit"] = pre_audit_article(item_id, body_html)

    # ③ 发布（立即或定时）
    if timer_time:
        result["publish"] = publish_article(
            book_id, item_id, volume_id, title, body_html,
            volume_name=volume_name, timer_status="1", timer_time=timer_time,
        )
    else:
        result["publish"] = publish_article(
            book_id, item_id, volume_id, title, body_html,
            volume_name=volume_name,
        )
    result["ok"] = str(result["publish"].get("code")) in ("0", "None", "none")
    if not result["ok"]:
        result["error"] = result["publish"].get("message")
    return result


def main():
    if len(sys.argv) < 3:
        usage()

    # 提取 --timer 参数
    timer_str, rest = parse_timer_arg(sys.argv[1:])
    timer_time = timer_to_timestamp(timer_str) if timer_str else None

    if len(rest) < 2:
        usage()

    book_id = rest[0]
    md_path = rest[1]
    volume_id = rest[2] if len(rest) > 2 else ""
    volume_name = rest[3] if len(rest) > 3 else ""
    item_id = rest[4] if len(rest) > 4 else ""

    # 未指定卷时自动取第一卷
    if not volume_id:
        vols = (get_volume_list(book_id).get("data") or {}).get("volume_list") or []
        if not vols:
            print("[!] 未找到卷，请手动传入 volume_id")
            sys.exit(1)
        volume_id = vols[0].get("volume_id")
        volume_name = volume_name or vols[0].get("volume_name") or "第一卷：默认"
    if not volume_name:
        volume_name = "第一卷：默认"

    if not os.path.exists(md_path):
        print(f"[!] content.md 不存在: {md_path}")
        sys.exit(1)

    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    mode = f"定时发布(时间戳={timer_time})" if timer_time else "立即发布"
    print(f"book_id={book_id}  volume_id={volume_id}  volume_name={volume_name}"
          f"  item_id={item_id or '(新建)'}  模式={mode}")
    print(f"content: {md_path}")

    result = publish_chapter_from_md_timer(
        book_id=book_id, volume_id=volume_id, volume_name=volume_name,
        md_text=md_text, item_id=item_id or None, timer_time=timer_time,
    )

    print(f"\n标题: {result.get('title')}")
    print(f"item_id: {result.get('item_id')}")
    if result.get("ok"):
        print("✅ 发布成功！" + ("（定时）" if timer_time else ""))
    else:
        print(f"❌ 发布失败: {result.get('error')}")
        if result.get("new"):
            print("   新建章节响应:", json.dumps(result["new"], ensure_ascii=False)[:300])

    # 保存结果供复查
    out = os.path.join(_SCRIPT_DIR, "..", "publish_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out}")

    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
