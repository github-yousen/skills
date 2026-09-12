# -*- coding: utf-8 -*-
"""
番茄短剧(红果短剧)排行榜查询脚本
==================================
无需任何登录凭证 / 签名,裸 HTTP 请求即可获取官方排行榜数据。

接口来源: 逆向分析 yinjg1997/hongguo 项目 + 实测验证(2026-08-23)

用法:
  py scripts/fanqie_drama_rank.py                # 全部榜单各前15条
  py scripts/fanqie_drama_rank.py hot            # 指定榜单(短剧热播榜)
  py scripts/fanqie_drama_rank.py new 50         # 指定榜单 + 数量
  py scripts/fanqie_drama_rank.py --list         # 列出所有可用榜单

可用榜单(board):
  recommend  短剧推荐榜 (comic_series_hot_rank, 官方字段: X万推荐)
  hot        短剧热播榜 (hot_play, X万推荐)
  new        短剧新剧榜 (new_rank)
  comic_hot  漫剧热播榜 (comic_series_hot_play, X万热度)
  comic_new  漫剧新剧榜 (comic_series_new_rank)
"""
import sys
import json
import uuid
import time
import urllib.request
import ssl

HOSTS = [
    'api5-normal-sinfonlinea.fqnovel.com',  # default (historical stable)
    'api5-normal-sinfonlineb.fqnovel.com',  # phone's primary (海外 sin cluster)
    'api5-normal-hl.fqnovel.com',           # phone's secondary (国内 HL cluster)
    'api3-normal-sinfonlinea.fqnovel.com',
    'api3-normal-sinfonlineb.fqnovel.com',
    'api3-normal-hl.fqnovel.com',
]
HOST = HOSTS[0]
UA = ('com.phoenix.read/72232 (Linux; U; Android 12; zh_CN; SM-G977N; '
      'Build/SP1A.210812.016; Cronet/TTNetVersion:5bf53e58 2023-03-07)')

BOARDS = {
    'recommend': 'comic_series_hot_rank',
    'hot': 'hot_play',
    'new': 'new_rank',
    'comic_hot': 'comic_series_hot_play',
    'comic_new': 'comic_series_new_rank',
}
BOARD_NAMES = {
    'recommend': '短剧推荐榜', 'hot': '短剧热播榜', 'new': '短剧新剧榜',
    'comic_hot': '漫剧热播榜', 'comic_new': '漫剧新剧榜',
}
CELL_ID = '7470092475068071998'

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def fetch_rank(board_key, limit=15, offset=0, hosts=None):
    """拉取指定榜单的一页(每页15条),按域名列表 failover。返回 (条目, used_host)。"""
    sub = BOARDS[board_key]
    q = {
        'aid': '8662', 'app_name': 'novelread', 'version_code': '72232',
        'version_name': '7.2.2.32', 'device_platform': 'android', 'os_version': '12',
        'iid': '0', 'device_id': '0',
        'cell_id': CELL_ID, 'tab_type': '26', 'client_req_type': '2',
        'client_template': '2', 'screen_width_px': '1350',
        'selected_items': 'comic_series_rank', 'sub_selected_items': sub,
        'session_uuid': str(uuid.uuid4()), 'offset': str(offset),
        '_rticket': str(int(time.time() * 1000)),
    }
    qs = '&'.join(f'{k}={v}' for k, v in q.items())
    last_err = None
    for h in (hosts or HOSTS):
        url = f'https://{h}/reading/bookapi/bookmall/cell/change/v?{qs}'
        headers = {'User-Agent': UA, 'Accept': 'application/json',
                   'Accept-Encoding': 'identity', 'Host': h}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=_ctx, timeout=20) as resp:
                j = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if j.get('code') != 0:
                raise RuntimeError(f"code={j.get('code')} msg={j.get('message')}")
            cv = j.get('data', {}).get('cell_view', {})
            cells = cv.get('cell_data') or []
            items = []
            for item in cells:
                v = item.get('video_data')
                if isinstance(v, list):
                    v = v[0] if v else {}
                v = v or {}
                sid = v.get('series_id') or v.get('book_id')
                if not sid:
                    continue
                items.append({
                    'rank': offset + len(items) + 1,
                    'series_id': str(sid),
                    'title': v.get('title', ''),
                    'episode_cnt': v.get('episode_cnt', 0),
                    'score': v.get('score', ''),
                    'play_cnt': v.get('play_cnt', 0),
                    'hot': v.get('rec_text') or '',
                    'copyright': v.get('copyright', ''),
                    'cover': v.get('cover', ''),
                    'intro': (v.get('video_desc') or '')[:60],
                })
            return items, bool(cv.get('has_more')), cv.get('next_offset'), h
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"all hosts failed, last: {last_err}")


def fetch_rank_all(board_key, limit=30):
    """循环翻页拉取榜单,直到数量足够或没有更多。"""
    results, offset, has_more, used_host = [], 0, True, None
    while len(results) < limit and has_more:
        page, has_more, offset, used_host = fetch_rank(board_key, limit=15, offset=offset)
        results.extend(page)
        if not page:
            break
    return results[:limit], used_host


def main():
    args = sys.argv[1:]
    if '--list' in args:
        print('可用榜单:')
        for k, v in BOARDS.items():
            print(f'  {k:10s} {BOARD_NAMES[k]:8s} (sub_selected_items={v})')
        print()
        print('可用 API 域名（按尝试顺序）:')
        for h in HOSTS:
            print(f'  - {h}')
        return
    boards = [a for a in args if a in BOARDS]
    limit = 30
    for a in args:
        if a.isdigit():
            limit = int(a)
            break
    if not boards:
        boards = list(BOARDS)
    for bk in boards:
        print(f'===== {BOARD_NAMES[bk]} (sub={BOARDS[bk]}) =====')
        try:
            items, used = fetch_rank_all(bk, limit)
            print(f'  [via {used}]')
            for it in items:
                hot = it['hot'] or f"{it['play_cnt']}播放"
                score = f"★{it['score']}" if it['score'] else ''
                print(f"  {it['rank']:>2}. [{it['episode_cnt']}集] {score} {hot}  {it['title']}  (id={it['series_id']}, 出品:{it['copyright']})")
        except Exception as e:
            print(f'  拉取失败: {e}')
        print()


if __name__ == '__main__':
    main()
