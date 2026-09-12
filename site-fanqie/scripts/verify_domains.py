import urllib.request, ssl, json, uuid, time
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'com.phoenix.read/72232 (Linux; U; Android 12; zh_CN; SM-G977N; Build/SP1A.210812.016; Cronet/TTNetVersion:5bf53e58 2023-03-07)'

HOSTS = [
    ('api5-normal-sinfonlinea.fqnovel.com',   'A(报告)  '),
    ('api5-normal-sinfonlineb.fqnovel.com',   'B(新发现)'),
    ('api5-normal-hl.fqnovel.com',            'HL(新发现)'),
    ('api3-normal-sinfonlinea.fqnovel.com',   'A3-A(推测)'),
    ('api3-normal-sinfonlineb.fqnovel.com',   'A3-B(新)'),
    ('api3-normal-hl.fqnovel.com',            'A3-HL(新)'),
]

def test(host, label):
    q = {
        'aid': '8662', 'app_name': 'novelread', 'version_code': '72232',
        'version_name': '7.2.2.32', 'device_platform': 'android', 'os_version': '12',
        'iid': '0', 'device_id': '0',
        'cell_id': '7470092475068071998', 'tab_type': '26', 'client_req_type': '2',
        'client_template': '2', 'screen_width_px': '1350',
        'selected_items': 'comic_series_rank', 'sub_selected_items': 'hot_play',
        'session_uuid': str(uuid.uuid4()), 'offset': '0',
        '_rticket': str(int(time.time() * 1000)),
    }
    qs = '&'.join(f'{k}={v}' for k, v in q.items())
    url = f'https://{host}/reading/bookapi/bookmall/cell/change/v?{qs}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': UA, 'Accept': 'application/json', 'Host': host
        })
        r = urllib.request.urlopen(req, context=ctx, timeout=15)
        j = json.loads(r.read())
        n = len(j.get('data', {}).get('cell_view', {}).get('cell_data', []) or [])
        print(f'{label} {host:50s} -> code={j.get("code")} msg={j.get("message")} items={n}')
    except Exception as e:
        print(f'{label} {host:50s} -> ERR: {e}')

for h, l in HOSTS:
    test(h, l)
