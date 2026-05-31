# 网站源码逆向分析 - 通用抓取脚本（鲁棒增强版）
# 用法: python web_fetch_source.py <url> [output_dir]
# 功能: 抓取目标URL的原始HTML + 所有关联JS文件 + 提取关键信息
# 增强: 自动解压(gzip/deflate/br/zstd) + 重试退避 + 反爬页检测 + 多级编码识别
import urllib.request
import urllib.parse
import urllib.error
import ssl
import re
import json
import os
import sys
import time
import gzip
import zlib
from collections import defaultdict
from datetime import datetime

# ============ 可选解压库（有则用，无则降级） ============
try:
    import brotli  # pip install brotli
    HAS_BROTLI = True
except ImportError:
    try:
        import brotlicffi as brotli
        HAS_BROTLI = True
    except ImportError:
        HAS_BROTLI = False
try:
    import zstandard  # pip install zstandard
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

# ============ 配置 ============
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEFAULT_HEADERS = {
    'User-Agent': DEFAULT_USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    # 注意: 不再用 identity。很多服务器无视 identity 强制返回 gzip/br,
    # 导致拿到二进制乱码。这里按已装解压库动态协商, 默认 gzip/deflate(标准库可解压)。
}

# SSL上下文（跳过验证）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 反爬 / 拦截页强特征（出现几乎可确定是拦截页，不会嵌在正常页里）
ANTIBOT_MARKERS = [
    ('sina visitor system', '微博访客系统跳转页'),
    ('just a moment', 'Cloudflare 5秒盾'),
    ('checking your browser', 'Cloudflare JS 挑战'),
    ('cf-browser-verification', 'Cloudflare 浏览器验证'),
    ('enable javascript and cookies to continue', 'JS/Cookie 强校验'),
    ('百度安全验证', '百度安全验证'),
    ('请完成安全验证', '安全验证页'),
    ('点击继续访问', '风控拦截页'),
]
# 弱特征：可能嵌在正常页面(如登录组件)，仅当出现在 <title> 或页面很小时才判定
ANTIBOT_WEAK = [
    ('captcha', '验证码页'),
    ('geetest', '极验验证'),
    ('滑动验证', '滑块验证'),
    ('verify', '验证页'),
    ('robot check', '机器人校验'),
    ('forbidden', '访问被拒'),
    ('access denied', '访问被拒'),
]


# ============ 工具函数 ============

def normalize_url(url, base_url=''):
    """规范化URL，处理相对路径、协议相对路径等"""
    if not url or url.startswith('data:') or url.startswith('blob:'):
        return None
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        if base_url:
            parsed = urllib.parse.urlparse(base_url)
            return f'{parsed.scheme}://{parsed.netloc}{url}'
        return None
    if not url.startswith('http'):
        if base_url:
            return urllib.parse.urljoin(base_url, url)
        return None
    return url


def _accept_encoding():
    """根据已装库动态生成 Accept-Encoding。无 br/zstd 库时绝不声明,
    避免服务器返回无法解压的格式。"""
    encs = ['gzip', 'deflate']
    if HAS_BROTLI:
        encs.append('br')
    if HAS_ZSTD:
        encs.append('zstd')
    return ', '.join(encs)


def _decompress(raw, encoding):
    """按 Content-Encoding 自动解压"""
    enc = (encoding or '').lower().strip()
    if not enc or enc == 'identity':
        return raw
    try:
        if enc == 'gzip':
            return gzip.decompress(raw)
        if enc == 'deflate':
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
        if enc == 'br' and HAS_BROTLI:
            return brotli.decompress(raw)
        if enc == 'zstd' and HAS_ZSTD:
            return zstandard.ZstdDecompressor().decompress(raw)
    except Exception as e:
        print(f'  [WARN] 解压 {enc} 失败: {e}')
        return raw
    # 声明了压缩但无对应解压库
    print(f'  [WARN] 服务器返回 {enc} 压缩，但缺少解压库，内容可能乱码。'
          f'建议: pip install brotli zstandard')
    return raw


def _detect_charset(raw, content_type):
    """多级编码识别: HTTP头 -> HTML meta -> 默认 utf-8"""
    ct = (content_type or '').lower()
    if 'charset=' in ct:
        cs = ct.split('charset=')[-1].split(';')[0].strip().strip('"\'')
        if cs:
            return cs
    head = raw[:4096].decode('latin-1', errors='ignore').lower()
    m = re.search(r'<meta[^>]+charset=["\']?\s*([a-z0-9_\-]+)', head)
    if m:
        return m.group(1)
    m = re.search(r'content=["\'][^"\']*charset=([a-z0-9_\-]+)', head)
    if m:
        return m.group(1)
    return 'utf-8'


def detect_block(text, body_len):
    """检测是否为反爬 / 拦截 / 占位页。强特征直接判定，弱特征需结合 title/小页面。"""
    low = text.lower()
    hits = []
    for marker, desc in ANTIBOT_MARKERS:
        if marker in low:
            hits.append(desc)
    # 取 title 内容，弱特征只在 title 中或极小页面才算
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.S | re.I)
    title = (m.group(1).lower() if m else '')
    for marker, desc in ANTIBOT_WEAK:
        if marker in title or (body_len < 4096 and marker in low):
            hits.append(desc)
    if body_len < 2048 and ('<html' in low or '<!doctype' in low):
        hits.append('响应过小(<2KB)，疑似占位/跳转页')
    return list(dict.fromkeys(hits))  # 去重保序


def fetch_url(url, timeout=20, max_retries=3, extra_headers=None, return_meta=False):
    """抓取URL内容（鲁棒版）。

    - 自动解压 gzip/deflate/br/zstd
    - 对 429/5xx/超时/连接错误指数退避重试
    - 多级编码识别
    - 反爬页检测
    return_meta=False 时返回文本字符串（向后兼容）；
    return_meta=True 时返回 dict（含 raw/encoding/charset/status/blocks 等）。
    """
    headers = dict(DEFAULT_HEADERS)
    headers['Accept-Encoding'] = _accept_encoding()
    if extra_headers:
        headers.update(extra_headers)

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                raw = resp.read()
                enc = resp.headers.get('Content-Encoding', '')
                ctype = resp.headers.get('Content-Type', '')
                data = _decompress(raw, enc)
                charset = _detect_charset(data, ctype)
                try:
                    text = data.decode(charset, errors='ignore')
                except (LookupError, TypeError):
                    text = data.decode('utf-8', errors='ignore')
                blocks = detect_block(text, len(data))
                if blocks:
                    print(f'  [反爬提示] {url} 可能未拿到真实内容: {", ".join(blocks)}')
                if return_meta:
                    return {
                        'text': text, 'raw': data, 'encoding': enc or 'identity',
                        'charset': charset, 'content_type': ctype,
                        'status': getattr(resp, 'status', 200), 'blocks': blocks,
                        'headers': dict(resp.headers), 'error': None,
                    }
                return text
        except urllib.error.HTTPError as e:
            last_err = e
            code = e.code
            if code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = min(2 ** attempt, 8)
                print(f'  [重试 {attempt}/{max_retries}] HTTP {code}, {wait}s 后重试 {url}')
                time.sleep(wait)
                continue
            if code == 403:
                print(f'  [ERROR] 403 Forbidden: 可能需要更真实的 UA / Cookie / Referer -> {url}')
            elif code == 404:
                print(f'  [ERROR] 404 Not Found: {url}')
            else:
                print(f'  [ERROR] HTTP {code}: {url}')
            break
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError) as e:
            last_err = e
            if attempt < max_retries:
                wait = min(2 ** attempt, 8)
                print(f'  [重试 {attempt}/{max_retries}] {type(e).__name__}, {wait}s 后重试 {url}')
                time.sleep(wait)
                continue
            print(f'  [ERROR] {type(e).__name__}: {e} -> {url}')
            break
        except Exception as e:
            last_err = e
            print(f'  [ERROR] {url}: {e}')
            break

    if return_meta:
        return {'text': '', 'raw': b'', 'encoding': '', 'charset': '',
                'content_type': '', 'status': getattr(last_err, 'code', 0),
                'blocks': [], 'headers': {}, 'error': str(last_err)}
    return ''


def resolve_js_url(src, page_url):
    """解析JS文件的完整URL"""
    if not src or src.startswith('data:') or src.startswith('blob:'):
        return None
    # 过滤明显非JS的资源
    skip_patterns = ['google-analytics', 'gtag', 'facebook', 'doubleclick',
                     'adservice', 'analytics', 'hotjar', 'clarity']
    for p in skip_patterns:
        if p in src.lower():
            return None
    return normalize_url(src, page_url)


# ============ HTML解析 ============

class SourceExtractor:
    """从HTML源码中提取关键信息"""

    def __init__(self, html, page_url):
        self.html = html
        self.page_url = page_url
        self.js_files = []
        self.inline_scripts = []
        self.css_files = []
        self.links = []
        self.meta_info = {}
        self.initial_state = {}

    def extract_all(self):
        self._extract_scripts()
        self._extract_styles()
        self._extract_links()
        self._extract_meta()
        self._extract_initial_state()
        return self

    def _extract_scripts(self):
        # 外部JS文件
        script_srcs = re.findall(r'<script[^>]*\ssrc=["\']([^"\']+)["\']', self.html)
        for src in script_srcs:
            url = resolve_js_url(src, self.page_url)
            if url:
                self.js_files.append(url)

        # 内联脚本
        inline = re.findall(r'<script[^>]*>(.*?)</script>', self.html, re.DOTALL)
        for s in inline:
            s = s.strip()
            if s and len(s) > 10:  # 过滤空脚本
                self.inline_scripts.append(s)

    def _extract_styles(self):
        css_hrefs = re.findall(r'<link[^>]*\shref=["\']([^"\']+\.css[^"\']*)["\']', self.html)
        for href in css_hrefs:
            url = normalize_url(href, self.page_url)
            if url:
                self.css_files.append(url)

    def _extract_links(self):
        hrefs = re.findall(r'<a[^>]*\shref=["\']([^"\']+)["\']', self.html)
        for href in hrefs:
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                self.links.append(href)

    def _extract_meta(self):
        # 技术栈识别
        if 'next-route-announcer' in self.html or '__NEXT_DATA__' in self.html:
            self.meta_info['framework'] = 'Next.js'
        if '__NUXT__' in self.html:
            self.meta_info['framework'] = 'Nuxt.js'
        if 'ng-app' in self.html or 'ng-version' in self.html:
            self.meta_info['framework'] = 'Angular'
        if '__INITIAL_STATE__' in self.html:
            self.meta_info['framework'] = 'Vue (SSR)'
        if 'data-reactroot' in self.html or '__NEXT_DATA__' in self.html:
            self.meta_info['framework'] = 'React (SSR)'
        if 'vite' in self.html.lower():
            self.meta_info['bundler'] = 'Vite'
        if 'webpack' in self.html.lower():
            self.meta_info['bundler'] = 'Webpack'

        # 查找 source map 引用
        sourcemap = re.findall(r'sourceMappingURL\s*=\s*(\S+)', self.html)
        if sourcemap:
            self.meta_info['source_maps'] = sourcemap

    def _extract_initial_state(self):
        # Vue SSR: window.__INITIAL_STATE__
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', self.html, re.DOTALL)
        if m:
            try:
                self.initial_state['__INITIAL_STATE__'] = json.loads(m.group(1))
            except:
                self.initial_state['__INITIAL_STATE__raw'] = m.group(1)[:5000]

        # Next.js: __NEXT_DATA__
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', self.html, re.DOTALL)
        if m:
            try:
                self.initial_state['__NEXT_DATA__'] = json.loads(m.group(1))
            except:
                pass

        # Nuxt.js: __NUXT__
        m = re.search(r'window\.__NUXT__\s*=\s*(.*?);\s*</script>', self.html, re.DOTALL)
        if m:
            self.initial_state['__NUXT__raw'] = m.group(1)[:5000]

        # 通用: window.__pinia__
        m = re.search(r'window\.__pinia__\s*=\s*\(function', self.html)
        if m:
            self.meta_info['state_management'] = 'Pinia'


# ============ JS分析 ============

class JSAnalyzer:
    """分析JS源码，提取API端点、鉴权信息等"""

    # API路径提取正则
    API_PATTERNS = [
        # (正则, 类型名, 是否为方法-URL对)
        (r'["\'`](/x/[a-zA-Z0-9_/.-]+)["\'`]', 'x-api', False),
        (r'["\'`](/api/[a-zA-Z0-9_/.-]+)["\'`]', 'api-path', False),
        (r'["\'`](/pgc/[a-zA-Z0-9_/.-]+)["\'`]', 'pgc-api', False),
        (r'["\'`](/v[0-9]+/[a-zA-Z0-9_/.-]+)["\'`]', 'versioned-api', False),
        # 通用 REST 前缀（非B站专用，提升通用性）
        (r'["\'`](/(?:rest|gateway|service|graphql|gql|rpc|bff|openapi|backend)/[a-zA-Z0-9_/.-]+)["\'`]', 'rest-api', False),
        (r'(https?://api\.[a-z0-9.-]+\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'api-domain', False),
        (r'(https?://[a-z0-9.-]*passport[a-z0-9.-]*\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'passport', False),
        (r'(https?://[a-z0-9.-]*graphql[a-z0-9.-]*\.[a-z]+)', 'graphql', False),
        (r'method:\s*["\'](GET|POST|PUT|DELETE|PATCH)["\'].{0,60}?url:\s*["\']([^"\']+)["\']', 'method-url', True),
        # axios/请求库调用点: axios.get("/x"), request.post("/x"), $http.put("/x")
        (r'(?:axios|request|http|fetch|api|\$http|service)\.(get|post|put|delete|patch)\s*\(\s*["\'`]([^"\'`]+)["\'`]', 'call-site', True),
        # fetch("url")
        (r'fetch\s*\(\s*["\'`](https?://[^"\'`]+|/[a-zA-Z0-9_/.-]+)["\'`]', 'fetch', False),
        (r'["\'`](/(?:medialist|audio|live|member|msg|dynamic|feed|account)[a-zA-Z0-9_/.-]+)["\'`]', 'biz-path', False),
    ]

    # 鉴权关键词
    AUTH_KEYWORDS = [
        'Authorization', 'Bearer', 'token', 'Token', 'csrf', 'csrf_token',
        'Cookie', 'SESSDATA', 'bili_jct', 'DedeUserID', 'buvid',
        'localStorage.setItem', 'sessionStorage.setItem',
        'interceptors.request', 'interceptors.response',
        'withCredentials', 'X-Token', 'Access-Token',
        'getToken', 'setToken', 'refreshToken',
        'login', 'logout', 'auth',
    ]

    # 签名/加密关键词
    SIGN_KEYWORDS = [
        'w_rid', 'wts', 'wbi', 'sign', 'signature', 'hmac', 'md5', 'sha256',
        'encrypt', 'decrypt', 'mixin_key', 'img_key', 'sub_key',
        'GenWebTicket', 'access_token', 'appkey',
    ]

    def __init__(self, js_content, source_name=''):
        self.content = js_content
        self.source = source_name
        self.apis = []
        self.auth_info = []
        self.sign_info = []

    def analyze(self):
        self._extract_apis()
        self._extract_auth()
        self._extract_signing()
        return self

    def _extract_apis(self):
        for pattern, ptype, is_method_url in self.API_PATTERNS:
            matches = re.findall(pattern, self.content)
            for m in matches:
                if is_method_url:
                    method, path = m
                    # 校验：必须是合法路径/URL，过滤格式串、普通单词等噪音
                    if not re.match(r'^(/|https?://)', path):
                        continue
                    if ' ' in path or '%s' in path or '${' in path:
                        continue
                    if any(path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ico', '.map']):
                        continue
                    self.apis.append({'method': method.upper(), 'path': path, 'type': ptype, 'source': self.source})
                else:
                    path = m
                    # 过滤静态资源
                    if any(path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ico', '.map']):
                        continue
                    if len(path) < 5:
                        continue
                    self.apis.append({'method': '', 'path': path, 'type': ptype, 'source': self.source})

    def _extract_auth(self):
        for kw in self.AUTH_KEYWORDS:
            for m in re.finditer(re.escape(kw), self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 150)
                ctx = self.content[start:end].replace('\n', ' ')
                self.auth_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

    def _extract_signing(self):
        for kw in self.SIGN_KEYWORDS:
            for m in re.finditer(kw, self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 200)
                ctx = self.content[start:end].replace('\n', ' ')
                self.sign_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

        # 特别提取 WBI mixin_key 数组（B站等网站的反爬签名）
        mixin_match = re.search(r'\[(\d+(?:,\s*\d+){30,})\]', self.content)
        if mixin_match:
            self.sign_info.append({
                'keyword': 'mixin_key_array',
                'context': f'[{mixin_match.group(1)}]',
                'source': self.source
            })


# ============ 功能增强：Chunk发现 / SourceMap还原 / 路由 / 域名 / 报告 ============

def discover_chunks(content, base_js_url, page_url, limit=25):
    """从主JS中发现代码分割的 chunk 文件URL（Vite 动态import + Webpack5 chunk映射）。

    现代前端业务逻辑大多在 chunk 里，不抓 chunk 等于漏掉绝大部分接口。
    """
    found = set()

    # 1) 显式字符串引用：含 hash 或 chunk/assets 关键字的 .js
    for m in re.findall(r'["\'`]([a-zA-Z0-9_\-./]*?(?:[._-][0-9a-f]{6,}|chunk|assets/|static/js/)[a-zA-Z0-9_\-./]*?\.js)["\'`]', content):
        if not m.endswith('.map'):
            found.add(m)

    # 2) 动态 import("...")（Vite/Rollup 常见）
    for m in re.findall(r'import\(\s*["\']([^"\']+\.js)["\']', content):
        found.add(m)

    # 3) Webpack5 默认 chunk 文件名重建: "static/js/"+e+"."+{id:"hash",..}[e]+".js"
    wp = re.search(
        r'["\']([\w./-]*?)["\']\s*\+\s*\w+\s*\+\s*["\']\.["\']\s*\+\s*\{([^{}]*?)\}\[\w+\]\s*\+\s*["\']\.js["\']',
        content)
    if wp:
        prefix = wp.group(1)
        for cid, chash in re.findall(r'(\w+)\s*:\s*["\']([0-9a-f]{6,})["\']', wp.group(2)):
            found.add(f'{prefix}{cid}.{chash}.js')

    # 解析为完整URL并去重
    urls = []
    seen = set()
    for f in found:
        full = normalize_url(f, base_js_url) or normalize_url(f, page_url)
        if full and full not in seen and not full.endswith('.map'):
            seen.add(full)
            urls.append(full)
    return urls[:limit]


def _clean_source_path(src):
    """清洗 source map 里的源文件路径，转成安全的相对路径"""
    s = re.sub(r'^(webpack-internal://|webpack://|file://|https?://)', '', src)
    s = s.replace('\x00', '').replace('..', '_').replace(':', '_')
    s = re.sub(r'[<>|*?"]', '_', s).lstrip('/')
    s = re.sub(r'^(\.+/)+', '', s)
    return s or 'unknown.js'


def restore_sourcemap(map_url, output_dir):
    """下载 source map 并还原 sourcesContent 为原始目录结构（拿到未混淆源码）。"""
    raw = fetch_url(map_url)
    if not raw:
        return None
    try:
        sm = json.loads(raw)
    except Exception:
        return {'map_url': map_url, 'ok': False, 'reason': 'JSON解析失败'}

    sources = sm.get('sources', []) or []
    contents = sm.get('sourcesContent', []) or []
    if not contents:
        return {'map_url': map_url, 'ok': False, 'reason': '无 sourcesContent（无法还原源码，只有映射）',
                'sources_count': len(sources)}

    src_root = os.path.join(output_dir, 'sourcemap_restored')
    restored = []
    for src, code in zip(sources, contents):
        if not code:
            continue
        rel = _clean_source_path(src)
        # 跳过第三方库噪音（可选保留）
        fpath = os.path.join(src_root, rel)
        try:
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(code)
            restored.append({'path': rel, 'size': len(code), 'code': code})
        except Exception:
            continue
    return {'map_url': map_url, 'ok': True, 'restored_count': len(restored),
            'dir': src_root, 'files': restored}


def extract_routes(html, initial_state, js_texts):
    """提取页面路由（Next.js / Vue Router / React Router / 通用 path 声明）。"""
    routes = []
    seen = set()

    def add(path, name=''):
        if path and path.startswith('/') and len(path) < 120 and path not in seen:
            if not any(path.lower().endswith(ext) for ext in ['.js', '.css', '.png', '.svg', '.json', '.ico', '.woff']):
                seen.add(path)
                routes.append({'path': path, 'name': name})

    # Next.js 当前页
    nd = initial_state.get('__NEXT_DATA__') if isinstance(initial_state, dict) else None
    if isinstance(nd, dict):
        if nd.get('page'):
            add(nd['page'], 'next-page')

    # JS 中的路由声明: {path:"/xxx", name:"yyy", component:...}
    blob = '\n'.join(js_texts)
    for m in re.finditer(r'[{,]\s*path\s*:\s*["\']([^"\']+)["\'](?:[^{}]*?name\s*:\s*["\']([^"\']+)["\'])?', blob):
        add(m.group(1), m.group(2) or '')

    return routes[:120]


def summarize_domains(unique_apis, js_files, page_url):
    """汇总涉及的所有域名并分类。"""
    domains = defaultdict(set)

    def classify(host):
        h = host.lower()
        if 'passport' in h or 'login' in h or 'sso' in h or 'account' in h or 'auth' in h:
            return '鉴权/登录'
        if h.startswith('api') or '.api.' in h or 'api.' in h or 'openapi' in h:
            return 'API 接口'
        if 'graphql' in h:
            return 'GraphQL'
        if any(k in h for k in ['static', 'cdn', 'assets', 'img', 'static']):
            return '静态资源/CDN'
        if any(k in h for k in ['log', 'track', 'analytics', 'report', 'data.', 'stat']):
            return '日志/监控'
        return '其它'

    page_host = urllib.parse.urlparse(page_url).netloc

    for api in unique_apis:
        p = api.get('path', '')
        if p.startswith('http'):
            host = urllib.parse.urlparse(p).netloc
            if host:
                domains[classify(host)].add(host)
    for ju in js_files:
        host = urllib.parse.urlparse(ju).netloc
        if host and host != page_host:
            domains[classify(host)].add(host)
    if page_host:
        domains['主站'].add(page_host)

    return {k: sorted(v) for k, v in domains.items()}


def _guess_module(path):
    """根据路径关键词归类业务模块"""
    p = path.lower()
    if any(k in p for k in ['login', 'logout', 'passport', 'auth', 'token', 'user', 'account', 'nav', 'member']):
        return '认证 / 用户'
    if any(k in p for k in ['log', 'track', 'report', 'stat', 'analytics', 'monitor', 'collect']):
        return '上报 / 监控'
    if any(k in p for k in ['search', 'feed', 'recommend', 'list', 'detail', 'info']):
        return '内容 / 列表'
    return '业务接口'


def generate_markdown_report(report, extractor, routes, domains, sourcemaps, output_dir, template_path=None):
    """按模板自动生成 Markdown 操作手册，实现成果沉淀（核心交付）。"""
    url = report['url']
    host = urllib.parse.urlparse(url).netloc
    meta = report.get('meta_info', {})

    lines = []
    lines.append(f'# {host} 操作手册\n')
    lines.append(f'> 首次分析时间：{report["timestamp"]}')
    lines.append(f'> 目标网站：{url}')
    lines.append('> 文档用途：**下次直接看本文档操作，无需重新分析**\n')
    lines.append('> ⚠️ 本文档由脚本自动生成骨架，`{...}` / TODO 处需结合源码人工补全。\n')
    lines.append('---\n')

    # 一、基本信息
    has_sm = any(s and s.get('ok') for s in sourcemaps) if sourcemaps else False
    lines.append('## 一、基本信息\n')
    lines.append('| 项目 | 内容 |')
    lines.append('|------|------|')
    lines.append(f'| 目标 URL | {url} |')
    lines.append(f'| 前端框架 | {meta.get("framework", "未识别")} |')
    lines.append(f'| 打包工具 | {meta.get("bundler", "未识别")} |')
    lines.append(f'| 状态管理 | {meta.get("state_management", "未识别")} |')
    lines.append(f'| Source Map | {"有（已还原源码）" if has_sm else "无/未还原"} |')
    main_js = report['js_files_analyzed'][0]['filename'] if report.get('js_files_analyzed') else '-'
    lines.append(f'| 主 JS 文件 | `{main_js}` |')
    if report.get('antibot_blocks'):
        lines.append(f'| ⚠️ 反爬状态 | {", ".join(report["antibot_blocks"])} |')
    lines.append('')
    lines.append('---\n')

    # 二、凭证（从鉴权/签名引用推断）
    auth_kw = sorted({a['keyword'] for a in report.get('auth_info', [])})
    sign_kw = sorted({s['keyword'] for s in report.get('sign_info', [])})
    lines.append('## 二、凭证说明\n')
    lines.append('> 根据源码中出现的鉴权关键词推断，需结合实际确认。\n')
    lines.append(f'- **检测到的鉴权关键词**：{", ".join(auth_kw) if auth_kw else "（无明显鉴权）"}')
    lines.append(f'- **检测到的签名/加密关键词**：{", ".join(sign_kw) if sign_kw else "（无）"}')
    lines.append('\n**获取 Cookie**：浏览器登录 → F12 → Application → Cookies → 复制对应域名的值\n')
    lines.append('---\n')

    # 三、API 接口清单（按推断模块分组）
    apis = report.get('apis', [])
    by_module = defaultdict(list)
    for api in apis:
        by_module[_guess_module(api['path'])].append(api)
    lines.append('## 三、API 接口清单\n')
    lines.append(f'> 共提取 {len(apis)} 个接口（含 chunk / sourcemap 还原源码）。\n')
    for module in ['认证 / 用户', '内容 / 列表', '业务接口', '上报 / 监控']:
        items = by_module.get(module)
        if not items:
            continue
        lines.append(f'### {module}\n')
        lines.append('| 方法 | 路径 | 来源JS |')
        lines.append('|------|------|--------|')
        for api in items[:80]:
            method = api.get('method') or 'GET?'
            path = api['path'].replace('|', '\\|')
            lines.append(f'| {method} | `{path}` | {api.get("source", "")} |')
        if len(items) > 80:
            lines.append(f'| ... | 其余 {len(items) - 80} 个见 analysis_report.json | |')
        lines.append('')
    lines.append('---\n')

    # 四、页面路由
    lines.append('## 四、页面功能地图\n')
    if routes:
        lines.append('| 路径 | 名称/说明 |')
        lines.append('|------|-----------|')
        for r in routes[:80]:
            lines.append(f'| `{r["path"]}` | {r.get("name", "")} |')
        if len(routes) > 80:
            lines.append(f'| ... | 其余 {len(routes) - 80} 条 |')
    else:
        lines.append('未提取到显式路由（可能为 SSR 或路由在未抓取的 chunk 中）。')
    lines.append('')
    lines.append('---\n')

    # 五、域名体系
    lines.append('## 五、域名体系\n')
    lines.append('| 域名 | 用途 |')
    lines.append('|------|------|')
    for use, hosts in domains.items():
        for h in hosts:
            lines.append(f'| `{h}` | {use} |')
    lines.append('')
    lines.append('---\n')

    # 六、附录：JS 清单 + SourceMap
    lines.append('## 六、附录\n')
    lines.append('### 6.1 JS 文件清单\n')
    lines.append('| 文件名 | 大小(B) | 接口数 |')
    lines.append('|--------|---------|--------|')
    for js in report.get('js_files_analyzed', [])[:60]:
        lines.append(f'| `{js["filename"]}` | {js["size"]} | {js["api_count"]} |')
    lines.append('')
    if sourcemaps:
        lines.append('### 6.2 Source Map 还原\n')
        for s in sourcemaps:
            if s and s.get('ok'):
                lines.append(f'- ✅ `{s["map_url"]}` → 还原 {s["restored_count"]} 个源文件到 `sourcemap_restored/`')
            elif s:
                lines.append(f'- ❌ `{s["map_url"]}`：{s.get("reason", "失败")}')
        lines.append('')
    lines.append('---\n')
    lines.append('*文档由 web-reverse-engineer 技能自动生成，接口有变化请重新分析更新。*')

    out_path = os.path.join(output_dir, f'{host}_report.md')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return out_path


# ============ 主流程 ============

def analyze_website(url, output_dir='web_analysis'):
    """主分析流程"""
    print(f'[*] 目标: {url}')
    print(f'[*] 输出目录: {output_dir}')
    print()

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    js_dir = os.path.join(output_dir, 'js')
    os.makedirs(js_dir, exist_ok=True)

    # ---- 步骤1: 抓取HTML ----
    print('[1] 抓取原始HTML...')
    meta = fetch_url(url, return_meta=True)
    html = meta['text']
    if not html:
        print(f'[!] 无法获取HTML，退出。原因: {meta.get("error") or "状态码 " + str(meta.get("status"))}')
        return None
    print(f'    Content-Encoding: {meta["encoding"]}, charset: {meta["charset"]}')
    if meta['blocks']:
        print(f'    [!] 警告: 疑似被反爬拦截({", ".join(meta["blocks"])})，'
              f'后续提取可能无效。建议提供 Cookie 或改用真实浏览器渲染。')

    html_path = os.path.join(output_dir, 'page_source.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'    HTML长度: {len(html)}, 已保存到 {html_path}')

    # ---- 步骤2: 解析HTML提取信息 ----
    print('\n[2] 解析HTML结构...')
    extractor = SourceExtractor(html, url).extract_all()

    print(f'    外部JS文件: {len(extractor.js_files)}')
    print(f'    内联脚本: {len(extractor.inline_scripts)}')
    print(f'    CSS文件: {len(extractor.css_files)}')
    print(f'    页面链接: {len(extractor.links)}')
    print(f'    技术栈: {extractor.meta_info}')
    print(f'    初始状态: {list(extractor.initial_state.keys())}')

    # 保存HTML提取结果
    html_info = {
        'url': url,
        'content_encoding': meta['encoding'],
        'charset': meta['charset'],
        'antibot_blocks': meta['blocks'],
        'js_files': extractor.js_files,
        'css_files': extractor.css_files,
        'meta_info': extractor.meta_info,
        'initial_state_keys': list(extractor.initial_state.keys()),
        'links_count': len(extractor.links),
    }
    with open(os.path.join(output_dir, 'html_info.json'), 'w', encoding='utf-8') as f:
        json.dump(html_info, f, ensure_ascii=False, indent=2)

    # 保存initial_state
    if extractor.initial_state:
        with open(os.path.join(output_dir, 'initial_state.json'), 'w', encoding='utf-8') as f:
            json.dump(extractor.initial_state, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤3: 抓取并分析JS文件 ----
    print(f'\n[3] 抓取并分析JS文件...')
    all_apis = []
    all_auth = []
    all_sign = []
    js_results = []
    js_texts = []          # 收集JS文本用于路由提取
    chunk_urls = set()     # 待抓取的 chunk
    sourcemap_results = [] # source map 还原结果
    fetched_urls = set()

    # 优先级排序：主入口JS放前面
    js_files = extractor.js_files
    # 识别主入口（通常文件名含 index/app/main）
    def js_priority(url):
        fname = url.split('/')[-1].lower()
        if any(k in fname for k in ['index', 'app', 'main', 'vendor', 'chunk']):
            if 'vendor' in fname:
                return 0
            if 'index' in fname:
                return 1
            if 'app' in fname:
                return 2
            return 3
        return 9

    js_files.sort(key=js_priority)

    def process_js(js_url, idx, total, tag=''):
        """抓取并分析单个JS，返回是否成功"""
        fname = js_url.split('/')[-1].split('?')[0]
        if not fname.endswith('.js'):
            fname += '.js'
        fpath = os.path.join(js_dir, fname)
        print(f'  [{idx}/{total}]{tag} {fname}')
        content = fetch_url(js_url)
        if not content:
            return
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'    长度: {len(content)}')
        js_texts.append(content)

        analyzer = JSAnalyzer(content, fname).analyze()
        all_apis.extend(analyzer.apis)
        all_auth.extend(analyzer.auth_info)
        all_sign.extend(analyzer.sign_info)
        js_results.append({
            'filename': fname, 'url': js_url, 'size': len(content),
            'api_count': len(analyzer.apis), 'auth_count': len(analyzer.auth_info),
            'sign_count': len(analyzer.sign_info),
        })

        # 发现 chunk（自动加入待抓队列）
        for cu in discover_chunks(content, js_url, url):
            if cu not in fetched_urls:
                chunk_urls.add(cu)

        # 发现并还原 source map
        sm_ref = re.search(r'sourceMappingURL\s*=\s*(\S+\.map)', content)
        if sm_ref:
            map_url = normalize_url(sm_ref.group(1), js_url)
            if map_url:
                print(f'    !! 发现 Source Map: {map_url}，尝试还原源码...')
                sm = restore_sourcemap(map_url, output_dir)
                if sm:
                    sourcemap_results.append(sm)
                    if sm.get('ok'):
                        print(f'       ✅ 还原 {sm["restored_count"]} 个源文件')
                        # 还原的未混淆源码也参与接口分析
                        for srcf in sm.get('files', []):
                            a = JSAnalyzer(srcf['code'], 'sm:' + srcf['path']).analyze()
                            all_apis.extend(a.apis)
                            all_auth.extend(a.auth_info)
                            all_sign.extend(a.sign_info)
                    else:
                        print(f'       ⚠️ {sm.get("reason")}')

    # 第一轮：HTML 中直接引用的 JS
    for i, js_url in enumerate(js_files):
        fetched_urls.add(js_url)
        process_js(js_url, i + 1, len(js_files))

    # 第二轮：自动发现的 chunk 文件
    if chunk_urls:
        chunk_list = sorted(chunk_urls)
        print(f'\n[3.1] 自动发现 {len(chunk_list)} 个 chunk，开始抓取...')
        for i, cu in enumerate(chunk_list):
            fetched_urls.add(cu)
            process_js(cu, i + 1, len(chunk_list), tag='[chunk]')

    # ---- 步骤4: 分析内联脚本 ----
    print(f'\n[4] 分析内联脚本...')
    for i, script in enumerate(extractor.inline_scripts):
        js_texts.append(script)
        analyzer = JSAnalyzer(script, f'inline_script_{i+1}').analyze()
        all_apis.extend(analyzer.apis)
        all_auth.extend(analyzer.auth_info)
        all_sign.extend(analyzer.sign_info)

    # ---- 步骤5: 去重并输出 ----
    print(f'\n[5] 汇总结果...')

    # API去重
    seen_apis = set()
    unique_apis = []
    for api in all_apis:
        key = f"{api.get('method', '')}:{api['path']}"
        if key not in seen_apis:
            seen_apis.add(key)
            unique_apis.append(api)

    # 按类型分组
    grouped = defaultdict(list)
    for api in unique_apis:
        grouped[api['type']].append(api)

    # 鉴权去重
    seen_auth = set()
    unique_auth = []
    for a in all_auth:
        key = f"{a['keyword']}:{a['context'][:50]}"
        if key not in seen_auth:
            seen_auth.add(key)
            unique_auth.append(a)

    # 签名去重
    seen_sign = set()
    unique_sign = []
    for s in all_sign:
        key = f"{s['keyword']}:{s['context'][:50]}"
        if key not in seen_sign:
            seen_sign.add(key)
            unique_sign.append(s)

    # ---- 步骤5.5: 提取路由 + 域名汇总 ----
    print(f'\n[5.1] 提取路由与域名...')
    routes = extract_routes(html, extractor.initial_state, js_texts)
    domains = summarize_domains(unique_apis, list(fetched_urls), url)
    print(f'    路由: {len(routes)} 条, 域名: {sum(len(v) for v in domains.values())} 个')

    # 保存完整结果
    report = {
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'meta_info': extractor.meta_info,
        'antibot_blocks': meta.get('blocks', []),
        'js_files_analyzed': js_results,
        'chunk_fetched': len([u for u in fetched_urls if u not in extractor.js_files]),
        'sourcemaps': [{k: v for k, v in s.items() if k != 'files'} for s in sourcemap_results if s],
        'routes': routes,
        'domains': domains,
        'total_apis': len(unique_apis),
        'total_auth_refs': len(unique_auth),
        'total_sign_refs': len(unique_sign),
        'apis': unique_apis,
        'auth_info': unique_auth,
        'sign_info': unique_sign,
    }

    report_path = os.path.join(output_dir, 'analysis_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤6: 自动生成 Markdown 操作手册 ----
    print(f'\n[6] 生成 Markdown 操作手册...')
    md_path = None
    try:
        md_path = generate_markdown_report(report, extractor, routes, domains,
                                           sourcemap_results, output_dir)
        print(f'    已生成: {md_path}')
    except Exception as e:
        print(f'    [WARN] 报告生成失败: {e}')

    # ---- 步骤7: 输出摘要 ----
    sm_ok = sum(1 for s in sourcemap_results if s and s.get('ok'))
    print(f'\n{"="*60}')
    print(f'分析完成!')
    print(f'{"="*60}')
    print(f'HTML: {len(html)} chars')
    print(f'JS文件: {len(js_results)} 个（含 chunk {report["chunk_fetched"]} 个）')
    print(f'Source Map 还原: {sm_ok} 个')
    print(f'API端点: {len(unique_apis)} 个')
    for typ, items in sorted(grouped.items()):
        print(f'  {typ}: {len(items)} 个')
    print(f'路由: {len(routes)} 条 | 域名: {sum(len(v) for v in domains.values())} 个')
    print(f'鉴权引用: {len(unique_auth)} 个 | 签名引用: {len(unique_sign)} 个')
    print(f'\n结果保存到: {os.path.abspath(output_dir)}/')
    print(f'  - page_source.html (原始HTML)')
    print(f'  - html_info.json / initial_state.json')
    print(f'  - js/ (所有JS + chunk)')
    if sm_ok:
        print(f'  - sourcemap_restored/ (还原的未混淆源码)')
    print(f'  - analysis_report.json (完整分析报告)')
    if md_path:
        print(f'  - {os.path.basename(md_path)} (★ 操作手册，下次直接看这个)')

    return report


# ============ 入口 ============

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python web_fetch_source.py <url> [output_dir]')
        print('示例: python web_fetch_source.py https://www.bilibili.com/ bilibili_analysis')
        sys.exit(1)

    target_url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'web_analysis'

    analyze_website(target_url, output)
