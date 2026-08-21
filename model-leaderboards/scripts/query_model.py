# -*- coding: utf-8 -*-
"""
模型排行榜聚合查询工具
功能:
  1. 查询指定模型在各榜单的排名/分数
  2. 列出某个榜单 Top N
  3. 列出所有支持的榜单/分类
用法:
  python query_model.py "claude-opus"                 # 模糊查询模型在各榜单表现
  python query_model.py "gpt-5" --exact               # 精确匹配
  python query_model.py "qwen" --board coding         # 指定 LMArena 分类查询
  python query_model.py --top lmarena overall 10      # LMArena overall 榜 Top10
  python query_model.py --top livebench Overall 10    # LiveBench Top10
  python query_model.py --list                        # 列出所有榜单及分类
  python query_model.py --refresh                     # 先刷新数据再查询
"""
import os
import sys
import json
import re

# 强制 UTF-8 输出，避免 Windows GBK 控制台编码错误
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, 'data')


def load_data(name):
    path = os.path.join(DATA_DIR, f'{name}.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def list_all():
    """列出所有支持的榜单和分类"""
    print('=' * 70)
    print('模型排行榜聚合查询 - 可用数据源')
    print('=' * 70)

    specs = [
        ('lmarena', 'LMArena Chatbot Arena', 'Elo rating', 'boards'),
        ('livebench', 'LiveBench', 'score %', 'models'),
        ('swebench', 'SWE-bench', '代码能力', 'boards'),
        ('eqbench', 'EQ-Bench v4', 'Elo 情感智能', 'models'),
        ('artificialanalysis', 'Artificial Analysis', 'Intelligence Index', 'models'),
        ('opencompass', 'OpenCompass 司南', '综合分 0-100', 'boards'),
        ('superclue', 'SuperCLUE 中文榜', '总分 0-100', 'boards'),
        ('mmlupro', 'MMLU-Pro', '准确率 0-1', 'models'),
        ('gpqa', 'GPQA Diamond', '准确率 %', 'models'),
        ('terminalbench', 'Terminal-Bench 2.1', '成功率 %', 'models'),
        ('swebenchpro', 'SWE-bench Pro', 'resolved %', 'models'),
        ('browsecomp', 'BrowseComp-Plus', 'Accuracy %', 'models'),
    ]
    for name, label, metric, kind in specs:
        data = load_data(name)
        if not data:
            print(f'\n■ {label} — [未抓取，运行 fetch_all.py]')
            continue
        print(f'\n■ {label} ({data.get("url", "")})')
        print(f'  指标: {data.get("metric", metric)} | 模型数: {data.get("models_count", "?")}'
              f' | 更新: {data.get("updated", data.get("release", data.get("generated_at", "?")))}')
        if kind == 'boards' and data.get('boards'):
            cats = sorted(data['boards'].keys())
            print(f'  分类({len(cats)}): {", ".join(cats[:12])}{"..." if len(cats) > 12 else ""}')
        elif kind == 'models':
            cats = data.get('categories', [])
            if cats:
                print(f'  分类: {", ".join(cats)}')


def search_model(query, exact=False, board='overall', limit=12):
    """在全部榜单中搜索模型。
    board 参数: lmarena 榜单限定查看的分类，默认 overall
    limit 参数: 每个榜单最多显示条数"""
    print('=' * 70)
    print(f'模型搜索: "{query}" {"(精确)" if exact else "(模糊)"}'
          f'{" (每个榜单限 " + str(limit) + " 条)" if limit else ""}')
    print('=' * 70)

    import re as _re

    def _tokens(s):
        """将模型名/查询词拆成 token 集合（兼容连字符/空格/斜杠/点号）"""
        return {t for t in _re.split(r'[-\s_/.()]+', (s or '').lower()) if t}

    q_tokens = _tokens(query)
    if not q_tokens:
        print('查询词为空')
        sys.exit(0)

    if exact:
        def match(model, q):
            return (model or '').lower() == q.lower()
    else:
        def match(model, q):
            mt = _tokens(model)
            # 查询词的每个 token 都需在模型 token 中找到包含关系
            # 例如 qwen -> qwen3.8（qwen 是 qwen3.8 的子串）；gpt -> gpt54
            for qt in q_tokens:
                if not any(qt in m or m in qt for m in mt):
                    return False
            return True

    q = query.strip().lower()
    found = False
    shown = {'count': 0}

    # 1. LMArena（默认只看 overall 榜，其他分类用 --board 指定）
    data = load_data('lmarena')
    if data and data.get('boards'):
        boards = data['boards']
        if board in boards:
            print(f'\n▶ LMArena Chatbot Arena — [{board}] (Elo rating, 更新 {data.get("updated", "")})')
            n = 0
            for h in boards[board]:
                if match(h['model'], q):
                    found = True
                    print(f'  #{h["rank"]} {h["model"]} ({h["org"]})'
                          f' | Elo {h["rating"]} (CI {h["rating_ci"][0]}-{h["rating_ci"][1]})'
                          f' | {h["vote_count"]} votes')
                    n += 1
                    if limit and n >= limit:
                        print(f'  ... (已显示 {n} 条，共 {sum(1 for m in boards[board] if match(m["model"], q))} 条匹配)')
                        break
        else:
            cats = list(boards.keys())
            print(f'\n▶ LMArena Chatbot Arena — [分类 "{board}" 不存在，可用: {", ".join(cats[:15])}...]')

    # 2. LiveBench
    data = load_data('livebench')
    if data and data.get('models'):
        print(f'\n▶ LiveBench (release {data.get("release", "?")})')
        n = 0
        for i, m in enumerate(data['models'], 1):
            if match(m['model'], q):
                found = True
                score = m.get('Overall')
                print(f'  #{i} {m["model"]} | Overall {score}', end='')
                for c in data.get('categories', [])[:6]:
                    if c != 'Overall' and m.get(c) is not None:
                        print(f' | {c} {m[c]}', end='')
                print()
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    # 3. SWE-bench
    data = load_data('swebench')
    if data and data.get('boards'):
        print('\n▶ SWE-bench (代码能力)')
        n = 0
        for cat, rows in data['boards'].items():
            for i, r in enumerate(rows, 1):
                if match(r.get('model_display') or r.get('model') or '', q):
                    found = True
                    print(f'  [{cat}] {r.get("model", "")} | agent={r.get("agent")}'
                          f' | cost={r.get("cost")} | {r.get("date", "")}')
                    n += 1
                    if limit and n >= limit:
                        print(f'  ... (已显示 {n} 条)')
                        break
            if limit and n >= limit:
                break

    # 4. EQ-Bench
    data = load_data('eqbench')
    if data and data.get('models'):
        print(f'\n▶ EQ-Bench v4 (Elo 情感智能, {data.get("generated_at", "")})')
        n = 0
        for i, m in enumerate(data['models'], 1):
            if match(m['model'], q):
                found = True
                ci = m.get('ci') or []
                print(f'  #{i} {m["model"]} | Elo {m.get("elo")}'
                      f' (CI {ci[0]}-{ci[1]}) | n={m.get("n_scenarios")}')
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    # 5. Artificial Analysis
    data = load_data('artificialanalysis')
    if data and data.get('models'):
        print(f'\n▶ Artificial Analysis ({data.get("metric", "Intelligence Index")})')
        n = 0
        for i, m in enumerate(data['models'], 1):
            if match(m['model'], q):
                found = True
                ii = m.get('intelligence_index')
                print(f'  #{i} {m["model"]} | Index {ii}', end='')
                if m.get('coding_index') is not None:
                    print(f' | Coding {m["coding_index"]}', end='')
                if m.get('agentic_index') is not None:
                    print(f' | Agentic {m["agentic_index"]}', end='')
                if m.get('input_price') is not None:
                    print(f' | $in {m["input_price"]}/1M', end='')
                print()
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    # 6. OpenCompass 司南
    data = load_data('opencompass')
    if data and data.get('boards'):
        print(f'\n▶ OpenCompass 司南 (上海AI实验室)')
        for cat in ['Overall', 'Coding', 'Math', 'Reasoning', 'Agentic', 'Knowledge', 'Language']:
            board = data['boards'].get(cat)
            if not board:
                continue
            hits = [r for r in board if match(r['model'], q)]
            for h in hits[:3]:
                found = True
                print(f'  [{cat}] #{h["rank"]} {h["model"]} ({h["org"]})'
                      f' | {h["score"]} | {"开源" if str(h.get("open_source","")).upper()=="YES" else "闭源"}')
            if limit and hits and len(hits) > 3:
                print(f'    ... ({len(hits)} 条)')

    # 7. SuperCLUE
    data = load_data('superclue')
    if data and data.get('boards'):
        print(f'\n▶ SuperCLUE 中文榜 ({data.get("month", "")})')
        for sheet in ['总排行榜', '开源排行榜', '推理模型总排行榜']:
            board = data['boards'].get(sheet)
            if not board:
                continue
            for i, r in enumerate(board, 1):
                model = str(r.get('模型名称') or '')
                if match(model, q):
                    found = True
                    ocs = r.get('开/闭源')
                    src_tag = ''
                    if sheet == '开源排行榜':
                        src_tag = ' | 开源'
                    elif ocs:
                        src_tag = f' | {"开源" if ocs == "开源" else "闭源"}'
                    print(f'  [{sheet}] {model} ({r.get("机构","")})'
                          f' | 总分 {r.get("总分")}'
                          f' | 数学推理 {r.get("数学推理")}'
                          f' | 智能体编程 {r.get("智能体编程")}'
                          f'{src_tag}')
            if limit and any(match(str(r.get('模型名称') or ''), q) for r in board):
                pass

    # 8. MMLU-Pro
    data = load_data('mmlupro')
    if data and data.get('models'):
        print(f'\n▶ MMLU-Pro (UIUC TIGER-Lab, 准确率 0-1)')
        n = 0
        for i, m in enumerate(data['models'], 1):
            if match(m['model'], q):
                found = True
                print(f'  #{i} {m["model"]} | Overall {m.get("overall")}', end='')
                for sub in (data.get('subjects') or [])[:5]:
                    if m.get(sub) is not None:
                        print(f' | {sub} {m[sub]}', end='')
                print()
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    # 9-12. GPQA / Terminal-Bench / SWE-bench Pro / BrowseComp（evals.report 系）
    evals_sources = [
        ('gpqa', 'GPQA Diamond', '博士级科学推理'),
        ('terminalbench', 'Terminal-Bench 2.1', 'CLI 智能体'),
        ('swebenchpro', 'SWE-bench Pro', '企业级代码'),
    ]
    for src_name, label, tag in evals_sources:
        data = load_data(src_name)
        if not data or not data.get('models'):
            continue
        print(f'\n▶ {label} ({tag})')
        n = 0
        for m in data['models']:
            if match(m['model'], q):
                found = True
                print(f'  #{m["rank"]} {m["model"]} ({m["lab"]})'
                      f' | {m.get("score_display", m.get("score"))}'
                      f' | {m.get("status", "")}'
                      f' | {m.get("date", "")}'
                      f'{" | 开源" if m.get("is_open") else ""}')
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    # BrowseComp-Plus（LLM+Retriever 组合）
    data = load_data('browsecomp')
    if data and data.get('models'):
        print(f'\n▶ BrowseComp-Plus (网页浏览智能体)')
        n = 0
        for m in data['models']:
            if match(m['model'], q):
                found = True
                print(f'  #{m["rank"]} {m["model"]} + {m["retriever"]}'
                      f' | Acc {m.get("accuracy")}% | Recall {m.get("recall")}%'
                      f' | {"开源" if m.get("open_weights") == "Yes" else "闭源"}')
                n += 1
                if limit and n >= limit:
                    print(f'  ... (已显示 {n} 条)')
                    break

    if not found:
        print('\n⚠ 未找到匹配模型。尝试更短的关键词，或用 --list 查看全部数据。')
        print('  例如: python query_model.py "claude" / "gpt" / "qwen" / "gemini"')


def show_top(source, category, n=10):
    """显示某榜单 Top N"""
    data = load_data(source)
    if not data:
        print(f'✗ {source} 无缓存数据，请先运行: python fetch_all.py {source}')
        return

    print('=' * 70)
    print(f'{source} Top {n} — {category or "默认"}')
    print('=' * 70)

    if source == 'lmarena':
        board = (data.get('boards') or {}).get(category or 'overall')
        if not board:
            cats = list((data.get('boards') or {}).keys())
            print(f'✗ 无分类 "{category}"。可用分类: {", ".join(cats[:20])}')
            return
        print(f'指标: {data["metric"]} | 更新: {data.get("updated", "")}')
        for r in board[:n]:
            print(f'  #{r["rank"]:<3} {r["model"]:<50} {r["org"]:<12}'
                  f' Elo {r["rating"]:<8} {r["vote_count"]} votes')

    elif source == 'livebench':
        models = data.get('models', [])
        cat = category or 'Overall'
        print(f'指标: score % | release: {data.get("release", "")}')
        for i, m in enumerate(models[:n], 1):
            print(f'  #{i:<3} {m["model"]:<50} {cat}: {m.get(cat, "-")}')

    elif source == 'swebench':
        board = (data.get('boards') or {}).get(category)
        if not board:
            cats = list((data.get('boards') or {}).keys())
            print(f'✗ 无分类 "{category}"。可用分类: {", ".join(cats)}')
            return
        print('指标: 模型 + agent + 成本')
        for i, r in enumerate(board[:n], 1):
            print(f'  #{i:<3} {r.get("model", ""):<50} agent={r.get("agent")}'
                  f' cost=${r.get("cost")}')

    elif source == 'eqbench':
        models = data.get('models', [])
        print(f'指标: Elo | 生成于: {data.get("generated_at", "")}')
        for i, m in enumerate(models[:n], 1):
            ci = m.get('ci') or []
            print(f'  #{i:<3} {m["model"]:<50} Elo {m.get("elo")}'
                  f' (CI {ci[0]}-{ci[1]})')

    elif source == 'artificialanalysis':
        models = data.get('models', [])
        print(f'指标: {data.get("metric", "Intelligence Index")}')
        for i, m in enumerate(models[:n], 1):
            print(f'  #{i:<3} {m["model"]:<50} Index {m.get("intelligence_index")}'
                  f' | Coding {m.get("coding_index", "-")}'
                  f' | Agentic {m.get("agentic_index", "-")}')

    elif source == 'opencompass':
        board = (data.get('boards') or {}).get(category or 'Overall')
        if not board:
            cats = list((data.get('boards') or {}).keys())
            print(f'✗ 无分类 "{category}"。可用分类: {", ".join(cats)}')
            return
        print(f'指标: {data["metric"]}')
        for r in board[:n]:
            print(f'  #{r["rank"]:<3} {r["model"]:<50} {r["org"]:<12}'
                  f' {r["score"]} | {"开源" if str(r.get("open_source","")).upper()=="YES" else "闭源"}'
                  f' | {r.get("update_date", "")}')

    elif source == 'superclue':
        board = (data.get('boards') or {}).get(category or '总排行榜')
        if not board:
            cats = list((data.get('boards') or {}).keys())
            print(f'✗ 无分类 "{category}"。可用分类: {", ".join(cats)}')
            return
        print(f'指标: {data["metric"]} | 月份: {data.get("month", "")}')
        for i, r in enumerate(board[:n], 1):
            ocs = r.get('开/闭源')
            src_tag = ''
            if category == '开源排行榜':
                src_tag = ' | 开源'
            elif ocs:
                src_tag = f' | {"开源" if ocs == "开源" else "闭源"}'
            print(f'  #{i:<3} {str(r.get("模型名称","")):<50} {str(r.get("机构","")):<10}'
                  f' 总分 {r.get("总分")} | 数学推理 {r.get("数学推理")}'
                  f' | 智能体编程 {r.get("智能体编程")}{src_tag}')

    elif source == 'mmlupro':
        models = data.get('models', [])
        print(f'指标: {data.get("metric", "准确率 0-1")}')
        for i, m in enumerate(models[:n], 1):
            print(f'  #{i:<3} {m["model"]:<50} Overall {m.get("overall")}')

    elif source in ('gpqa', 'terminalbench', 'swebenchpro'):
        models = data.get('models', [])
        print(f'指标: {data.get("metric", "")}')
        for m in models[:n]:
            print(f'  #{m["rank"]:<3} {m["model"]:<50} {m["lab"]:<15}'
                  f' {m.get("score_display", m.get("score")):<8}'
                  f' {m.get("status", ""):<10} {m.get("date", "")}')

    elif source == 'browsecomp':
        models = data.get('models', [])
        print(f'指标: {data.get("metric", "Accuracy %")}')
        for m in models[:n]:
            print(f'  #{m["rank"]:<3} {m["model"]:<30} + {m["retriever"]:<22}'
                  f' Acc {m.get("accuracy")}% | Recall {m.get("recall")}%'
                  f' | {"开源" if m.get("open_weights") == "Yes" else "闭源"}')


if __name__ == '__main__':
    args = sys.argv[1:]

    if '--list' in args:
        list_all()
        sys.exit(0)

    if '--refresh' in args:
        from fetch_all import FETCHERS
        for name, fn in FETCHERS.items():
            fn(force=True)

    if '--top' in args:
        i = args.index('--top')
        rest = args[i + 1:]
        if len(rest) < 2:
            print('用法: python query_model.py --top <source> <category> [N]')
            sys.exit(1)
        src = rest[0]
        cat = rest[1]
        n = int(rest[2]) if len(rest) > 2 and rest[2].isdigit() else 10
        show_top(src, cat, n)
        sys.exit(0)

    if len(args) >= 1:
        exact = '--exact' in args
        board = 'overall'
        if '--board' in args:
            bi = args.index('--board')
            if bi + 1 < len(args):
                board = args[bi + 1]
        limit = 12
        if '--limit' in args:
            li = args.index('--limit')
            if li + 1 < len(args) and args[li + 1].isdigit():
                limit = int(args[li + 1])
        query = [a for a in args if not a.startswith('--')]
        if query:
            search_model(query[0], exact=exact, board=board, limit=limit)
            sys.exit(0)

    print(__doc__)
