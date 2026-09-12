# -*- coding: utf-8 -*-
"""
用途：番茄书籍数据诊断——自动拉取全史多维度数据，按行业合格标准逐项评价，
      指出该书"哪方面数据不行"（完读/追读/书架/留存/更新等），并给出优化建议。
依赖：site-fanqienovel 技能目录下的 api_client.py 与 fanqienovel_auth.json 凭证。
用法：
  python diagnose_book.py                   # 诊断全部书
  python diagnose_book.py <book_id>         # 诊断指定书
"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = r"d:\temp\novel\.codebuddy\skills\site-fanqienovel"
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

from api_client import (
    get_book_list, get_book_detail, get_book_common_stats,
    get_book_increase_stats, get_chapter_stats, get_read_source,
)

# 权威合格标准（番茄作者社区共识，综合知乎/头条/贴吧 + 数据含义文档）
# 关键口径：
#   10万字读完率 = 从第1章持续读到10万字的读者÷点开第1章的读者（长线质量核心）
#   章节读完率   = 单章：读到章末÷进入本章（单章吸引力）
#   追更率       = 当日追更人数÷当日阅读人数（>20%优质，<10%难拿推荐）
#   书架比       = 当日新增书架÷当日阅读人数（>30%优质）
#   点击率       = 点击量÷展现量（>5%合格）
#   阅读人数     = 单日独立用户（≠在读人数：在读=14天累计）
STANDARDS = {
    "ch2_follow": 46,            # 第1→2章跟读率及格线 %（流失≤54%及格；首章流失高是常态）
    "first10_completion": 80,    # 前10章读完率及格线 %（从第1章读到第10章）
    "first10_completion_excellent": 90,  # 前10章读完率优秀线 %
    "mid_follow": 80,            # 中段章节跟读率及格线 %
    "completion_10w": 15,        # 10万字读完率合格线 %（脑洞25%）
    "completion_newbie": 8,      # 新手10万字读完率可接受线 %
    "follow_rate_good": 20,      # 追更率优质线 %（>20%优质）
    "follow_rate_bad": 10,       # 追更率危险线 %（<10%难拿推荐）
    "shelf_ratio_good": 30,      # 书架比优质线 %（当日书架/当日阅读 >30%）
    "ctr_good": 5,               # 点击率合格线 %（点击/展现 >5%）
    "uv_active": 50,             # 日活阅读活跃线（<此值偏冷）
    "uv_burst": 200,             # 日活阅读爆款线
}


def fmt_date(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%m-%d")
    except Exception:
        return str(ts)


def get_chapter_data(book_id):
    """拉取每章数据：官方跟读率(stats_type=4) + 完读率/流失(stats_type=3)

    章节跟读率官方定义：读完第N章的读者中继续读第N+1章的比例。
    用 stats_type=4 返回的 follow_read_rate 官方字段，**不要用相邻完读率之比推算**
    （完读率统计波动会导致>100%的失真值）。
    """
    r3 = get_chapter_stats(book_id, stats_type="3", latest_count=500, page_count=500)
    r4 = get_chapter_stats(book_id, stats_type="4", latest_count=500, page_count=500)
    c3 = (r3.get("data") or {}).get("chapter_stats_list") or []
    c4 = (r4.get("data") or {}).get("chapter_stats_list") or []
    follow_map = {c.get("indice", 0) + 1: c.get("follow_read_rate", "") for c in c4}
    return [{"idx": c.get("indice", 0) + 1,
             "title": c.get("title", ""),
             "wc": c.get("word_number", 0),
             "loss": (lambda x: float(x) if x else None)(c.get("loss_rate", "")),
             "complete": (lambda x: float(x) if x else None)(c.get("read_completion_rate", "")),
             "follow": (lambda x: float(x) if x else None)(follow_map.get(c.get("indice", 0) + 1, ""))}
            for c in c3]


def diagnose(book):
    bid = book.get("book_id")
    name = book.get("book_name") or "未知"
    wc = book.get("word_count", 0)
    ch_num = book.get("chapter_number", 0)

    print("\n" + "=" * 66)
    print(f"🔍 诊断: {name}  (book_id={bid})")
    print(f"   总字数 {wc} | {ch_num} 章")

    # 创建日期 → 历史天数
    days = 30
    try:
        d = (get_book_detail(bid).get("data") or {})
        ctime = d.get("create_time", "")
        if ctime:
            days = max(1, (int(time.time()) - int(ctime)) // 86400 + 1)
            print(f"   创建于 {datetime.fromtimestamp(int(ctime)).strftime('%Y-%m-%d')} ({days}天前)")
    except Exception:
        pass

    # 通用统计
    common = get_book_common_stats(bid, stats_type="1")
    d = common.get("data") or {}
    uv = int(d.get("reader_uv_daily", 0) or 0)
    uv_incr = d.get("reader_uv_daily_incr", "")
    rc = float(d.get("read_completion_rate", 0) or 0)
    shelf_daily = int(d.get("shelf_cnt_daily", 0) or 0)
    uv14 = int(d.get("reader_uv_14day_cnt", 0) or 0)

    problems = []
    passes = []

    # 提前拉取章节数据（评价3完读率/评价5流失跟读都要用）
    chapters = get_chapter_data(bid)

    # ── 评价 1: 更新状态（最重要的基础）──
    last_ch_time = book.get("last_chapter_time", "")
    if last_ch_time:
        last_days = (int(time.time()) - int(last_ch_time)) // 86400
        if last_days > 3:
            problems.append(f"⚠️ 断更{last_days}天: 读者追更流失，追读率归零")
        else:
            passes.append(f"✅ 更新正常（{last_days}天前更新）")
    else:
        problems.append("⚠️ 无章节: 空书，未开始连载")

    # ── 评价 2: 日活规模 ──
    if uv == 0 and wc > 0:
        problems.append(f"⚠️ 今日阅读0人: 无流量（断更/冷启动）")
    elif 0 < uv < STANDARDS["uv_active"]:
        problems.append(f"⚠️ 日活仅{uv}人（<{STANDARDS['uv_active']}活跃线），流量极低" +
                        (f"，较昨{uv_incr}%" if uv_incr else ""))
    elif STANDARDS["uv_active"] <= uv < STANDARDS["uv_burst"]:
        passes.append(f"✅ 日活{uv}人，达到活跃线（{uv_incr}%）")
    else:
        passes.append(f"🔥 日活{uv}人，爆款潜质！")

    # ── 评价 2.5: 追更数据（区分人数与比例，接口未返回人数时不臆算）──
    try:
        pursue_count = d.get("pursue_cnt_daily")
        pursue_rate = d.get("pursue_read_rate")
        if pursue_count is not None:
            pursue_count = int(pursue_count or 0)
            pursue_pct = pursue_count / uv * 100 if uv else 0
            if pursue_count == 0:
                problems.append("⚠️ 追更人数0: 当前没有读者阅读最近3天更新章节")
            elif pursue_pct < STANDARDS["follow_rate_bad"]:
                problems.append(f"⚠️ 追更人数{pursue_count}（追更率{pursue_pct:.1f}% < {STANDARDS['follow_rate_bad']}%危险线）")
            elif pursue_pct >= STANDARDS["follow_rate_good"]:
                passes.append(f"✅ 追更人数{pursue_count}（追更率{pursue_pct:.1f}% ≥ {STANDARDS['follow_rate_good']}%优质线）")
            else:
                passes.append(f"✅ 追更人数{pursue_count}（追更率{pursue_pct:.1f}%）")
        elif pursue_rate is not None:
            # 当前接口只返回 pursue_read_rate，无法确认它是人数还是比例，原样展示
            print(f"   📌 后台 pursue_read_rate={pursue_rate}（接口未返回 pursue_cnt_daily，不换算追更率）")
    except Exception:
        pass

    # ── 评价 3: 书籍读完率（不把章节锚点冒充10万字读完率）──
    # book_common.read_completion_rate 与 chapter_list.read_completion_rate 同名但上下文不同；
    # 截图显示字数读完率采用"作品达到10万字后新增读者"口径，当前抓到的接口没有直接档位字段。
    if wc >= 20000:
        print(f"   📌 书籍读完率字段: {rc}%（book_common；未强行标注10万/30万字档位）")

    # ── 评价 4: 书架/留存（用 read_source 流量来源新量口径）──
    try:
        src = get_read_source(bid,
                              start_date=str(int(time.time()) - 7 * 86400),
                              end_date=str(int(time.time())))
        sd = src.get("data") or {}
        total = int(sd.get("read_count_total", 0) or 0)
        shelf_flow = int(sd.get("read_count_shelf", 0) or 0)
        search_flow = int(sd.get("read_count_search", 0) or 0)
        if total > 0:
            shelf_pct = shelf_flow / total * 100
            search_pct = search_flow / total * 100
            if shelf_pct < 10:
                problems.append(f"⚠️ 书架回流仅{shelf_pct:.0f}%（近7天）: 读者看完不加书架，留存弱")
            else:
                passes.append(f"✅ 书架回流{shelf_pct:.0f}%（近7天）留存正常")
            passes.append(f"📌 流量结构: 搜索{search_pct:.0f}% / 书架{shelf_pct:.0f}% (近7天{total}次阅读)")
    except Exception:
        pass
    # 书架比（权威口径 = 当日新增书架÷当日阅读人数，优质>30%）
    try:
        if uv > 0 and shelf_daily >= 0:
            shelf_ratio = shelf_daily / uv * 100
            if shelf_ratio < STANDARDS["shelf_ratio_good"]:
                problems.append(f"⚠️ 书架比{shelf_ratio:.0f}%（<{STANDARDS['shelf_ratio_good']}%优质线）: 读者看完不加书架")
            else:
                passes.append(f"✅ 书架比{shelf_ratio:.0f}% ≥ {STANDARDS['shelf_ratio_good']}%优质线！")
    except Exception:
        pass
    if uv14 > 0:
        passes.append(f"✅ 14天累计阅读{uv14}人")

    # ── 评价 5: 章节流失分析（逐章读完率曲线 + 跟读率曲线，多方面比较）──
    # 字段含义（已确认）：
    #   complete(read_completion_rate) = 章节读完率 = 从第1章累计读到该章的比例（100%递减）
    #   loss = 100 - complete（累计流失）
    #   follow(follow_read_rate) = 章节跟读率 = 读完本章→继续读下一章的比例（非累计，后段高正常）
    if chapters and any(c.get("complete") is not None for c in chapters):
        # ① 关键锚点：第1/2章、第10章、50%处、末尾的读完率（逐章曲线取点）
        comp = {c["idx"]: c["complete"] for c in chapters if c.get("complete") is not None}
        if comp:
            ch1 = comp.get(1, 100)
            ch2 = comp.get(2)
            ch10 = comp.get(10)
            ch5 = comp.get(5)
            last_idx = max(comp.keys())
            last = comp.get(last_idx)

            # ② 读完率骤降段检测：相邻章读完率降幅 > 8 个百分点视为流失集中段
            drops = []
            idxs = sorted(comp.keys())
            for i in range(1, len(idxs)):
                a, b = idxs[i - 1], idxs[i]
                drop = comp.get(a, 0) - comp.get(b, 0)
                if drop >= 8:
                    drops.append(f"第{a}→{b}章读完率降{drop:.1f}%（{comp.get(a):.1f}%→{comp.get(b):.1f}%）")
            if drops:
                problems.append("⚠️ 读完率骤降段（流失集中）: " + "; ".join(drops[:3]))

            # ③ 第10章章节读完率：只作为曲线锚点，不使用自定义"前10章合格线"
            if ch10 is not None:
                print(f"   📌 第10章章节读完率={ch10:.2f}%（辅助观察点，非官方单独指标）")

            # ④ 第1→2章官方跟读率（stats_type=4 的 follow_read_rate）
            ch2_follow_obj = next((c for c in chapters if c["idx"] == 1), None)
            ch2_follow = ch2_follow_obj.get("follow") if ch2_follow_obj else None
            if ch2_follow is not None:
                if ch2_follow < STANDARDS["ch2_follow"]:
                    problems.append(f"⚠️ 第1→2章官方跟读{ch2_follow:.0f}% < 及格线{STANDARDS['ch2_follow']}%")
                else:
                    passes.append(f"✅ 第1→2章官方跟读{ch2_follow:.0f}%（≥{STANDARDS['ch2_follow']}%及格）")

            # ⑤ 跟读率骤降章（毒点章）：follow 明显低于相邻章
            follows = [(c["idx"], c.get("follow")) for c in chapters if c.get("follow") is not None]
            if len(follows) >= 4:
                low_pts = []
                for i in range(1, len(follows) - 1):
                    cur = follows[i][1]
                    prev = follows[i - 1][1]
                    nxt = follows[i + 1][1]
                    if prev and nxt and cur is not None:
                        neighbor_avg = (prev + nxt) / 2
                        if cur < STANDARDS["mid_follow"] and neighbor_avg - cur > 15:
                            low_pts.append(f"第{follows[i][0]}章跟读{cur:.0f}%（邻均{neighbor_avg:.0f}%）")
                if low_pts:
                    problems.append("⚠️ 疑似毒点章（跟读骤降）: " + "; ".join(low_pts[:3]))

            # ⑥ 分段对比：前10 / 中段 / 末尾 的读完率水平
            if last_idx > 20:
                seg_head = comp.get(10)
                seg_mid_idx = last_idx // 2
                seg_mid = comp.get(seg_mid_idx)
                seg_tail = comp.get(last_idx)
                if seg_mid is not None and seg_tail is not None:
                    print(f"   📊 读完率曲线: 第1章100% → 第10章{seg_head:.1f}% "
                          f"→ 第{seg_mid_idx}章{seg_mid:.1f}% → 第{last_idx}章{seg_tail:.1f}%")

            # ⑦ 末尾章节读完率（最新章节留存）
            if last is not None and last_idx > 20:
                if last < 1:
                    problems.append(f"⚠️ 最新章节读完率仅{last:.2f}%: 后期几乎无人读到")
    else:
        problems.append("⚠️ 无章节读完率数据")

    # ── 汇总输出 ──
    print(f"\n   📋 诊断结果:")
    for p in problems:
        print(f"   {p}")
    for p in passes:
        print(f"   {p}")

    # 结论
    severity = len(problems)
    if severity == 0:
        verdict = "🟢 数据健康，可继续稳定更新"
    elif severity <= 2:
        verdict = "🟡 存在短板，需针对性优化"
    elif severity <= 4:
        verdict = "🟠 多项指标不达标，建议重点整改"
    else:
        verdict = "🔴 数据严重不佳，评估是否重启或切书"
    print(f"\n   🎯 综合结论: {verdict}（{severity}项问题）")


def main():
    args = sys.argv[1:]
    only_id = args[0] if args else ""

    books_resp = get_book_list(page_index=0, page_count=20)
    book_list = books_resp.get("data", {}).get("book_list") or []
    print("📊 番茄书籍数据诊断（按行业合格标准）")
    for book in book_list:
        if only_id and book.get("book_id") != only_id:
            continue
        diagnose(book)


if __name__ == "__main__":
    main()
