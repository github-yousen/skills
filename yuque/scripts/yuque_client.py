# 语雀API客户端 - 供skill调用的底层工具脚本
# 用法: python yuque_client.py <command> [args...]
# 命令:
#   whoami                        - 获取当前用户信息
#   resolve-url <url>             - 由语雀文档URL直接定位 book_id/doc_id/format
#   list-books                    - 获取知识库列表
#   list-docs <book_id> [offset] [limit]  - 获取知识库文档列表
#   find-docs <keyword> [page_limit] [max_pages] - 在用户自己的所有知识库中查找文档
#   get-doc <doc_id> <book_id> [mode]     - 获取文档详情(mode=read/edit)

#   get-toc <book_id>             - 获取知识库目录结构
#   create-doc <book_id> <title> [slug] [body] - 创建文档
#   update-doc <doc_id> <book_id> [title] [--body-file <path>] [body] - 更新文档(支持从文件读取body)
#   delete-doc <doc_id> <book_id> - 删除文档
#   search <keyword> [type]       - 搜索(type=doc/book)
#   move-doc <doc_id> <book_id> <target_book_id> - 移动文档
#   get-doc-versions <doc_id> [limit] [offset]   - 获取文档版本列表
#   get-doc-version <doc_id> <version_id> [--format asl|html] - 获取历史版本内容
#   diff-versions <doc_id> <version_id_1> <version_id_2>      - 对比两个历史版本的正文差异
#   restore-version <doc_id> <book_id> <version_id> [--with-title] - 回滚到指定历史版本
#   get-doc-outline <doc_id> <book_id>           - 获取文档标题层级结构
#   replace-section <doc_id> <book_id> --heading <text> --body-file <path> - 替换指定section
#   md2lake [text] [--input-file <path>]         - Markdown 转 lake HTML
#   md2asl [text] [--input-file <path>] [--keep-blank] - Markdown 转语雀 ASL（默认折叠引用块内空行）
#   export-md <doc_id> <book_id>                 - 导出文档为语雀原生 Markdown（保真）
#
# 全局参数（可用于任何命令）:
#   --output-file <path>  - 将结果输出到文件而非 stdout
#   --body-only           - 仅用于 get-doc，输出纯 body HTML（不含 JSON 包装）
#
# 注意: update-doc 会通过 /api/docs/:id/content 接口同步更新 body 和 body_draft，
#       确保语雀前端能正确显示更新后的内容。
# 注意: 长内容建议用 --body-file 参数从文件读取，避免命令行长度限制。

import urllib.request
import urllib.parse
import ssl
import json
import os
import sys
import re
import difflib
from datetime import datetime

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

API_BASE = 'https://www.yuque.com'

# 从环境变量或配置文件读取凭证
def get_credentials():
    """获取语雀API凭证，优先从环境变量读取"""
    cookie = os.environ.get('YUQUE_COOKIE', '')
    csrf_token = os.environ.get('YUQUE_CSRF_TOKEN', '')
    x_login = os.environ.get('YUQUE_X_LOGIN', '')
    
    # 如果环境变量没设置，尝试从配置文件读取
    if not cookie:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cookie = config.get('cookie', '')
                csrf_token = config.get('csrf_token', '')
                x_login = config.get('x_login', '')
    
    return cookie, csrf_token, x_login


def api_request(method, path, params=None, data=None, cookie='', csrf_token='', x_login=''):
    """发送语雀API请求"""
    url = API_BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Content-Type': 'application/json',
        'Cookie': cookie,
        'Referer': 'https://www.yuque.com/',
        'x-csrf-token': csrf_token,
        'x-login': x_login,
        'X-Requested-With': 'XMLHttpRequest',
        'X-KL-Ajax-Request': 'Ajax_Request',
    }
    
    body = None
    if data:
        body = json.dumps(data).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
            try:
                return json.loads(raw)
            except:
                return {'_raw': raw[:5000]}
    except urllib.error.HTTPError as e:
        body_text = ''
        try:
            body_text = e.read().decode('utf-8', errors='ignore')[:1000]
        except:
            pass
        return {'_error': f'HTTP {e.code}', '_body': body_text}
    except Exception as e:
        return {'_error': str(e)}


def cmd_whoami(cookie, csrf_token, x_login):
    r = api_request('GET', '/api/mine', cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    return r.get('data', r)


def cmd_list_books(cookie, csrf_token, x_login):
    r = api_request('GET', '/api/mine/books', cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    books = r.get('data', [])
    result = []
    for b in books:
        result.append({
            'id': b.get('id'),
            'name': b.get('name'),
            'slug': b.get('slug'),
            'type': b.get('type'),
            'public': b.get('public'),
            'description': b.get('description', ''),
            'user': b.get('user', {}).get('login', ''),
            'topics_count': b.get('topics_count', 0),
            'public_topics_count': b.get('public_topics_count', 0),
        })
    return result


def cmd_list_docs(cookie, csrf_token, x_login, book_id, offset=0, limit=20):
    r = api_request('GET', f'/api/books/{book_id}/docs', 
                    params={'offset': offset, 'limit': limit},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    docs = r.get('data', [])
    result = []
    for d in docs:
        result.append({
            'id': d.get('id'),
            'title': d.get('title'),
            'slug': d.get('slug'),
            'book_id': d.get('book_id'),
            'format': d.get('format'),
            'word_count': d.get('word_count'),
            'status': d.get('status'),
            'public': d.get('public'),
            'description': d.get('description', ''),
            'created_at': d.get('created_at'),
            'updated_at': d.get('updated_at'),
            'published_at': d.get('published_at'),
        })
    return result


def cmd_find_docs(cookie, csrf_token, x_login, keyword, page_limit=100, max_pages=50):
    """在用户自己的所有知识库中查找文档，避免使用全站公开 search。"""
    keyword_norm = (keyword or '').strip().lower()
    if not keyword_norm:
        return {'_error': 'keyword is required'}

    page_limit = max(1, min(int(page_limit), 100))
    max_pages = max(1, int(max_pages))

    books = cmd_list_books(cookie, csrf_token, x_login)
    if isinstance(books, dict) and '_error' in books:
        return books

    matches = []
    errors = []
    docs_scanned = 0

    for book in books:
        book_id = book.get('id')
        if not book_id:
            continue
        offset = 0
        pages = 0
        while pages < max_pages:
            docs = cmd_list_docs(cookie, csrf_token, x_login, book_id, offset, page_limit)
            if isinstance(docs, dict) and '_error' in docs:
                errors.append({
                    'book_id': book_id,
                    'book_name': book.get('name'),
                    'error': docs,
                })
                break
            if not docs:
                break

            docs_scanned += len(docs)
            for doc in docs:
                title = str(doc.get('title') or '')
                slug = str(doc.get('slug') or '')
                description = str(doc.get('description') or '')
                haystack = f'{title}\n{slug}\n{description}'.lower()
                if keyword_norm in haystack:
                    item = dict(doc)
                    item.update({
                        'book_id': book_id,
                        'book_name': book.get('name'),
                        'book_slug': book.get('slug'),
                        'book_user': book.get('user'),
                    })
                    matches.append(item)

            if len(docs) < page_limit:
                break
            offset += page_limit
            pages += 1

    return {
        'keyword': keyword,
        'books_scanned': len(books),
        'docs_scanned': docs_scanned,
        'matches_count': len(matches),
        'matches': matches,
        'errors': errors,
    }





def parse_yuque_url(url):
    """从语雀文档 URL 解析出 user_login / book_slug / doc_slug。

    支持形式：
      https://www.yuque.com/<user>/<book>/<doc>
      https://www.yuque.com/<user>/<book>/<doc>?xxx
      www.yuque.com/<user>/<book>/<doc>
      /<user>/<book>/<doc>
    """
    if not url:
        return {'_error': 'url is required'}
    u = url.strip()
    # 去掉协议
    u = re.sub(r'^[a-zA-Z]+://', '', u)
    # 去掉域名
    u = re.sub(r'^[^/]*yuque\.com/', '', u)
    u = u.lstrip('/')
    # 去掉 query / fragment
    u = u.split('?')[0].split('#')[0]
    parts = [p for p in u.split('/') if p]
    if len(parts) < 3:
        return {'_error': f'无法解析的语雀文档 URL（需要 user/book/doc 三段）: {url}', 'parts': parts}
    return {
        'user_login': parts[0],
        'book_slug': parts[1],
        'doc_slug': parts[2],
    }


def cmd_resolve_url(cookie, csrf_token, x_login, url):
    """根据语雀文档 URL 直接定位文档：返回 book_id / doc_id / format 等关键信息。

    一步到位，避免反复 list-books / list-docs 验证。
    """
    parsed = parse_yuque_url(url)
    if '_error' in parsed:
        return parsed

    book_slug = parsed['book_slug']
    doc_slug = parsed['doc_slug']

    # 1) 在用户自己的知识库里按 slug 匹配 book_id
    books = cmd_list_books(cookie, csrf_token, x_login)
    if isinstance(books, dict) and '_error' in books:
        return books
    book = next((b for b in books if b.get('slug') == book_slug), None)

    # 2) 直接用 doc_slug 调 get-doc（语雀 /api/docs/:slug 接受 slug，需要 book_id）
    if book:
        book_id = book.get('id')
        doc = cmd_get_doc(cookie, csrf_token, x_login, doc_slug, book_id, mode='edit')
        if isinstance(doc, dict) and '_error' not in doc:
            return {
                **parsed,
                'book_id': book_id,
                'book_name': book.get('name'),
                'doc_id': doc.get('id'),
                'doc_title': doc.get('title'),
                'format': doc.get('format'),
                'word_count': doc.get('word_count'),
                'is_sheet': doc.get('format') == 'lakesheet',
                'is_board': doc.get('format') == 'lakeboard',
                'has_body': bool(doc.get('body')),
            }
        # get-doc 失败则回退到 toc 查找
        toc = cmd_get_toc(cookie, csrf_token, x_login, book_id)
        if isinstance(toc, dict) and 'toc' in toc:
            node = next((t for t in toc['toc'] if t.get('url') == doc_slug), None)
            if node:
                return {
                    **parsed,
                    'book_id': book_id,
                    'book_name': book.get('name'),
                    'doc_id': node.get('doc_id'),
                    'doc_title': node.get('title'),
                    'format': None,
                    'note': 'doc located via toc; get-doc returned error',
                    'get_doc_error': doc,
                }
        return {**parsed, 'book_id': book_id, 'book_name': book.get('name'),
                '_error': 'book 已定位，但未找到该文档（可能不属于当前用户或 slug 有误）',
                'get_doc_error': doc}

    return {**parsed,
            '_error': f'在当前用户知识库中未找到 slug 为 "{book_slug}" 的知识库；'
                      f'该 URL 可能属于他人或组织空间。'}


def cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit'):
    r = api_request('GET', f'/api/docs/{doc_id}', 
                    params={'book_id': book_id, 'mode': mode},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    d = r.get('data', {})
    result = {
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
        'format': d.get('format'),
        'word_count': d.get('word_count'),
        'status': d.get('status'),
        'public': d.get('public'),
        'description': d.get('description', ''),
        'body': d.get('body', ''),
        'body_draft': d.get('body_draft', ''),
        'body_asl': d.get('body_asl', ''),
        'body_draft_asl': d.get('body_draft_asl', ''),
        'draft_version': d.get('draft_version', 0),
        'created_at': d.get('created_at'),
        'updated_at': d.get('updated_at'),
        'published_at': d.get('published_at'),
    }
    return result


def cmd_get_toc(cookie, csrf_token, x_login, book_id):
    r = api_request('GET', f'/api/books/{book_id}/toc',
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    data = r.get('data', {})
    toc = data.get('toc', [])
    docs = data.get('docs', [])
    return {'toc': toc, 'docs': docs}


def cmd_create_doc(cookie, csrf_token, x_login, book_id, title, slug='', body=''):
    doc_data = {
        'book_id': book_id,
        'title': title,
        'format': 'lake',
    }
    if slug:
        doc_data['slug'] = slug
    if body:
        doc_data['body'] = body
    
    r = api_request('POST', '/api/docs', data=doc_data,
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    d = r.get('data', {})
    return {
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
        'format': d.get('format'),
    }


def cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title=None, body=None, body_asl=None):
    """更新文档。

    两种模式：
    - **body_asl 模式（推荐）**：传 ASL（语雀编辑器原生格式）。只通过 content 接口更新，
      其余结构保持原样，**不会破坏折叠块 / 画板等复杂结构**。
    - **body 模式（旧）**：传 HTML。会把 HTML 塞进 ASL 字段，语雀容错解析后
      可能把折叠块 `<summary>` 填满内容（视觉上变成"展开"），**不推荐**。
    """
    result_info = {}

    # 先获取 draft_version
    doc_info = api_request('GET', f'/api/docs/{doc_id}',
                           params={'book_id': book_id, 'mode': 'edit'},
                           cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in doc_info:
        return {'_error': 'Failed to get draft_version', '_detail': doc_info}
    draft_version = doc_info.get('data', {}).get('draft_version', 0)

    payload = body_asl if body_asl is not None else body
    if payload is not None:
        content_data = {
            'format': 'lake',
            'body_asl': payload,
            'body_draft_asl': payload,
            'save_type': 'user',
            'draft_version': draft_version,
        }
        r_content = api_request('PUT', f'/api/docs/{doc_id}/content', data=content_data,
                                cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in r_content:
            result_info['_content_warning'] = f"content接口失败: {r_content.get('_error', '')}"
        else:
            result_info['content_updated'] = True

    # Step 2: 更新 title（HTML 模式下才同时更新 body）
    doc_data = {'book_id': book_id}
    if title is not None:
        doc_data['title'] = title
    if body is not None and body_asl is None:
        doc_data['body'] = body

    if len(doc_data) > 1:
        r = api_request('PUT', f'/api/docs/{doc_id}', data=doc_data,
                        cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in r:
            return {**result_info, '_error': r.get('_error'), '_body': r.get('_body', '')}
        d = r.get('data', {})
        result_info.update({
            'id': d.get('id'),
            'title': d.get('title'),
            'slug': d.get('slug'),
            'book_id': d.get('book_id'),
        })

    return result_info


def cmd_delete_doc(cookie, csrf_token, x_login, doc_id, book_id):
    r = api_request('DELETE', f'/api/docs/{doc_id}', data={'book_id': book_id},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    return {'success': True, 'doc_id': doc_id}


def cmd_search(cookie, csrf_token, x_login, keyword, search_type='doc'):
    r = api_request('GET', '/api/zsearch', 
                    params={'q': keyword, 'type': search_type},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    data = r.get('data', {})
    hits = data.get('hits', [])
    result = []
    for h in hits:
        result.append({
            'id': h.get('id'),
            'title': h.get('title'),
            'slug': h.get('slug'),
            'type': h.get('type'),
            'url': h.get('url'),
            'abstract': h.get('abstract', ''),
            'book_name': h.get('book_name', ''),
        })
    return {'total': data.get('totalHits', len(result)), 'hits': result}


def cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id, limit=200, offset=0):
    """获取文档版本历史列表（按时间倒序，最新版本在最前）。"""
    r = api_request('GET', '/api/doc_versions',
                    params={'doc_id': doc_id, 'doc_type': 'Doc', 'offset': offset, 'limit': limit},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    versions = r.get('data', [])
    result = []
    for v in versions:
        user = v.get('user') or {}
        result.append({
            'id': v.get('id'),
            'title': v.get('title'),
            'created_at': v.get('created_at'),
            'author': user.get('login') or v.get('user_id'),
            'draft': v.get('draft'),
            'isReleased': v.get('isReleased'),
        })
    return {'count': len(result), 'offset': offset, 'versions': result}


def cmd_get_doc_version(cookie, csrf_token, x_login, doc_id, version_id, fmt='asl'):
    """获取单个历史版本的详情。

    fmt='asl'  : 返回 content 字段（语雀 ASL 原文，可直接回写，见 restore-version）
    fmt='html' : 返回 content_html 字段（渲染后的 HTML，适合阅读 / 转 Markdown）

    返回中的 `_content` 为正文，其余为元数据（由 main 决定写文件还是打印）。
    """
    r = api_request('GET', f'/api/doc_versions/{version_id}', params={'doc_id': doc_id},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    v = r.get('data', {})
    if not isinstance(v, dict) or not v:
        return {'_error': f'未找到版本 {version_id}（请确认 version_id 与 doc_id 是否匹配）'}
    user = v.get('user') or {}
    content = v.get('content_html' if fmt == 'html' else 'content', '') or ''
    return {
        '_content': content,
        'id': v.get('id'),
        'doc_id': v.get('doc_id'),
        'title': v.get('title'),
        'created_at': v.get('created_at'),
        'author': user.get('login') or v.get('user_id'),
        'word_count': v.get('word_count'),
        'doc_format': v.get('format'),
        'slug': v.get('slug'),
        'chars': len(content),
    }


def _blocks_to_text(lake_body):
    """把 lake ASL / HTML 拆成块级纯文本行，用于版本 diff。

    去掉文档头 meta，按块级标签断行，剥离标签与实体，丢掉空行。
    """
    import html as _html
    s = lake_body or ''
    s = re.sub(r'<!doctype[^>]*>', '', s, flags=re.I)
    s = re.sub(r'<meta[^>]*>', '', s, flags=re.I)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</(p|h[1-6]|li|tr|div|blockquote|pre|td|th|section)>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = _html.unescape(s)
    return [ln.strip() for ln in s.split('\n') if ln.strip()]


def cmd_diff_versions(cookie, csrf_token, x_login, doc_id, version_id_1, version_id_2, fmt='asl'):
    """对比两个历史版本的正文差异，输出 unified diff 文本。

    对比的是块级纯文本（已剥离标签），适合快速看“改了什么”，
    不做逐字符的富文本 diff。
    """
    a = cmd_get_doc_version(cookie, csrf_token, x_login, doc_id, version_id_1, fmt)
    if '_error' in a:
        return {'_error': f'版本 {version_id_1} 获取失败', '_detail': a}
    b = cmd_get_doc_version(cookie, csrf_token, x_login, doc_id, version_id_2, fmt)
    if '_error' in b:
        return {'_error': f'版本 {version_id_2} 获取失败', '_detail': b}

    lines_a = _blocks_to_text(a['_content'])
    lines_b = _blocks_to_text(b['_content'])
    diff = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=f'v{version_id_1} ({a.get("created_at")})',
        tofile=f'v{version_id_2} ({b.get("created_at")})',
        lineterm='', n=2,
    ))
    if not diff:
        return {'_diff': '', 'identical': True,
                'from': version_id_1, 'to': version_id_2,
                'lines': {'from': len(lines_a), 'to': len(lines_b)}}
    changed = sum(1 for ln in diff if ln.startswith(('+', '-')) and not ln.startswith(('+++', '---')))
    return {'_diff': '\n'.join(diff), 'identical': False,
            'from': version_id_1, 'to': version_id_2,
            'changed_lines': changed,
            'lines': {'from': len(lines_a), 'to': len(lines_b)}}


def cmd_restore_doc_version(cookie, csrf_token, x_login, doc_id, book_id, version_id, with_title=False):
    """回滚文档到指定历史版本（客户端回滚）。

    实现方式：取该版本的 `content`（ASL 原文，已确认与文档 body_asl 同构），
    通过 /api/docs/:id/content 写回，等价于一次普通保存。

    - 非破坏性：回滚本身也会生成一个新版本，可再次回滚回去
    - with_title=True 时同时把标题恢复为该版本标题
    """
    ver = cmd_get_doc_version(cookie, csrf_token, x_login, doc_id, version_id, fmt='asl')
    if '_error' in ver:
        return ver
    content = ver.get('_content', '')
    if not content:
        return {'_error': '该版本正文为空，无法回滚（表格 lakesheet / 画板 lakeboard 文档不支持）'}

    upd = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id,
                         title=(ver.get('title') if with_title else None),
                         body=None, body_asl=content)
    if isinstance(upd, dict) and upd.get('_error'):
        return {'_error': '回滚写入失败', '_detail': upd}

    return {
        'restored': True,
        'doc_id': doc_id,
        'from_version': version_id,
        'version_created_at': ver.get('created_at'),
        'version_title': ver.get('title'),
        'word_count': ver.get('word_count'),
        'chars': len(content),
        'title_restored': bool(with_title),
        'write_result': upd,
        'note': '回滚已生成新版本，可再次回滚到回滚前的版本',
    }


def _strip_tags(html):
    """去掉 HTML 标签并解码常见实体，得到纯文本。"""
    import html as _html
    text = re.sub(r'<[^>]+>', '', html or '')
    return _html.unescape(text).strip()


def _iter_headings(body):
    """逐个枚举文档中的真实标题元素，返回 [(level, start, end, inner_text), ...]。

    使用非贪婪逐个匹配 <hN>...</hN>，避免跨越多个标题的错误匹配。
    """
    result = []
    for m in re.finditer(r'<h([1-6])\b[^>]*>(.*?)</h\1>', body or '', re.DOTALL):
        level = int(m.group(1))
        inner = _strip_tags(m.group(2))
        result.append((level, m.start(), m.end(), inner))
    return result


def cmd_get_doc_outline(cookie, csrf_token, x_login, doc_id, book_id):
    """获取文档标题层级结构（h1-h6 outline）"""
    doc = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit')
    if '_error' in doc:
        return doc
    body = doc.get('body', '')
    lines = []
    for level, _start, _end, text in _iter_headings(body):
        indent = '  ' * (level - 1)
        lines.append(f'{indent}H{level}: {text}')
    return '\n'.join(lines)


def cmd_replace_section(cookie, csrf_token, x_login, doc_id, book_id, heading_text, new_content, asl=True):
    """按 heading 文本定位 section，替换该 section 内容。

    定位方式：逐个枚举真实标题元素，找到内部纯文本【精确等于】或【包含】
    heading_text 的标题，作为 section 起点；section 终点为下一个同级或更高级标题。
    精确匹配优先，避免跨标题误删。

    asl=True（默认，推荐）：基于 ASL 操作，只替换目标 section，
    其余结构（折叠块 / 画板等）保持原样，不会被破坏。
    asl=False：基于 HTML（旧行为，会把 HTML 塞进 ASL 字段，可能破坏复杂结构）。
    """
    doc = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit')
    if '_error' in doc:
        return doc
    body = doc.get('body_asl' if asl else 'body', '')

    headings = _iter_headings(body)
    if not headings:
        return {'_error': '文档中未找到任何标题，无法使用 replace-section'}

    target_norm = heading_text.strip()
    # 优先精确匹配，其次包含匹配
    idx = next((k for k, h in enumerate(headings) if h[3] == target_norm), None)
    if idx is None:
        idx = next((k for k, h in enumerate(headings) if target_norm in h[3]), None)
    if idx is None:
        available = '; '.join(h[3] for h in headings)
        return {'_error': f'未找到标题: "{heading_text}"', 'available_headings': available}

    heading_level, section_start, heading_end, _txt = headings[idx]

    # 如果紧邻标题前是 <hr>，连同 hr 一起替换
    before_segment = body[max(0, section_start - 200):section_start]
    hr_pos = before_segment.rfind('<hr')
    if hr_pos != -1:
        between = before_segment[hr_pos:]
        between_cleaned = re.sub(r'<hr[^>]*/?>[\s]*', '', between)
        if between_cleaned.strip() == '':
            section_start = max(0, section_start - 200) + hr_pos

    # 终点：下一个同级或更高级标题的起点
    section_end = None
    for k in range(idx + 1, len(headings)):
        if headings[k][0] <= heading_level:
            section_end = headings[k][1]
            break
    if section_end is None:
        # 没有后续同级/更高级标题，取到文档结尾（保留末尾 </div> 闭合标签）
        last_div = body.rfind('</div>')
        section_end = last_div if last_div > heading_end else len(body)

    new_body = body[:section_start] + new_content + body[section_end:]

    if asl:
        result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id,
                                title=None, body_asl=new_body)
    else:
        result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id,
                                title=None, body=new_body)
    result['section_replaced'] = heading_text
    result['original_length'] = len(body)
    result['new_length'] = len(new_body)
    result['mode'] = 'asl' if asl else 'html'
    return result


def md2lake(md_text):
    """将 Markdown 文本转换为语雀 lake HTML 格式。

    支持：标题、段落、加粗、斜体、删除线、行内代码、链接、图片、
    引用块、有序/无序列表、代码块、表格、分割线、换行。
    所有纯文本均做 HTML 转义，避免 < > & 破坏结构。
    """
    import html as _html

    def esc(s):
        return _html.escape(s, quote=True)

    lines = md_text.split('\n')
    html_parts = []
    i = 0
    in_list = None  # 'ul' or 'ol'

    def wrap_bare(s):
        """把标签之外的文本节点统一包进 <span class="ne-text">。"""
        out = []
        n = len(s)
        k = 0
        while k < n:
            if s[k] == '<':
                j = s.find('>', k)
                if j == -1:
                    out.append(s[k:])
                    break
                out.append(s[k:j + 1])
                k = j + 1
            else:
                j = s.find('<', k)
                if j == -1:
                    j = n
                seg = s[k:j]
                if seg.strip():
                    out.append(f'<span class="ne-text">{seg}</span>')
                else:
                    out.append(seg)
                k = j
        return ''.join(out)

    def inline_format(text):
        """处理行内格式：先转义，再套标签，最后包裹裸文本。"""
        text = esc(text)
        stash = []

        def _stash(frag):
            stash.append(frag)
            return f'\x00{len(stash) - 1}\x00'

        # 图片 ![alt](url)
        text = re.sub(
            r'!\[([^\]]*)\]\(([^)]+)\)',
            lambda m: _stash(f'<img src="{m.group(2)}" alt="{m.group(1)}" />'),
            text,
        )
        # 链接 [text](url)
        text = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            lambda m: _stash(f'<a href="{m.group(2)}">{m.group(1)}</a>'),
            text,
        )
        # 行内代码（先 stash，避免内部被其他规则干扰）
        text = re.sub(
            r'`([^`]+)`',
            lambda m: _stash(f'<code class="ne-code">{m.group(1)}</code>'),
            text,
        )
        # 加粗
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # 删除线
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        # 斜体
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        # 还原 stash
        for idx, frag in enumerate(stash):
            text = text.replace(f'\x00{idx}\x00', frag)
        return wrap_bare(text)

    def close_list():
        nonlocal in_list
        if in_list == 'ul':
            html_parts.append('</ul>')
        elif in_list == 'ol':
            html_parts.append('</ol>')
        in_list = None

    def is_table_sep(s):
        return bool(re.match(r'^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$', s))

    def split_row(s):
        s = s.strip()
        if s.startswith('|'):
            s = s[1:]
        if s.endswith('|'):
            s = s[:-1]
        return [c.strip() for c in s.split('|')]

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.startswith('```'):
            close_list()
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            code_content = esc('\n'.join(code_lines))
            html_parts.append(
                f'<pre class="ne-codeblock" data-language="{esc(lang)}">'
                f'<code>{code_content}</code></pre>'
            )
            i += 1
            continue

        # 表格：当前行像表头且下一行是分隔行
        if '|' in line and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            close_list()
            header = split_row(line)
            i += 2  # 跳过表头和分隔行
            rows = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append(split_row(lines[i]))
                i += 1
            ncol = len(header)
            tbl = ['<table class="ne-table"><tbody>']
            tbl.append('<tr>' + ''.join(
                f'<td><p class="ne-p">{inline_format(c)}</p></td>' for c in header
            ) + '</tr>')
            for row in rows:
                cells = (row + [''] * ncol)[:ncol]
                tbl.append('<tr>' + ''.join(
                    f'<td><p class="ne-p">{inline_format(c)}</p></td>' for c in cells
                ) + '</tr>')
            tbl.append('</tbody></table>')
            html_parts.append(''.join(tbl))
            continue

        # 分割线
        if re.match(r'^---+$', line.strip()):
            close_list()
            html_parts.append('<hr class="ne-hr" />')
            i += 1
            continue

        # 标题
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            text = inline_format(heading_match.group(2))
            html_parts.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # 引用块
        if line.startswith('> ') or line == '>':
            close_list()
            quote_lines = []
            while i < len(lines) and (lines[i].startswith('> ') or lines[i] == '>'):
                quote_lines.append(lines[i][2:] if lines[i].startswith('> ') else '')
                i += 1
            quote_html = '</p><p class="ne-p">'.join(
                inline_format(ql) for ql in quote_lines if ql.strip()
            )
            html_parts.append(
                f'<div class="ne-quote"><p class="ne-p">{quote_html}</p></div>'
            )
            continue

        # 无序列表
        ul_match = re.match(r'^[-*+]\s+(.+)$', line)
        if ul_match:
            if in_list != 'ul':
                close_list()
                html_parts.append('<ul class="ne-ul">')
                in_list = 'ul'
            content = inline_format(ul_match.group(1))
            html_parts.append(f'<li data-lake-index-type="0">{content}</li>')
            i += 1
            continue

        # 有序列表
        ol_match = re.match(r'^\d+\.\s+(.+)$', line)
        if ol_match:
            if in_list != 'ol':
                close_list()
                html_parts.append('<ol class="ne-ol">')
                in_list = 'ol'
            content = inline_format(ol_match.group(1))
            html_parts.append(f'<li data-lake-index-type="0">{content}</li>')
            i += 1
            continue

        # 空行
        if not line.strip():
            close_list()
            html_parts.append('<p class="ne-p"><br></p>')
            i += 1
            continue

        # 普通段落
        close_list()
        content = inline_format(line)
        html_parts.append(f'<p class="ne-p">{content}</p>')
        i += 1

    close_list()
    return ''.join(html_parts)


def _lid():
    """生成语雀风格的 data-lake-id（u + 8位十六进制）。"""
    import random
    return 'u' + ''.join(random.choice('0123456789abcdef') for _ in range(8))


def _asl_span(text):
    """把一个纯文本片段包成 ASL span。"""
    i = _lid()
    return f'<span data-lake-id="{i}" id="{i}">{text}</span>'


def _asl_inline(text):
    """把 markdown 行内文本转成 ASL 片段序列（strong / code / 普通文本）。"""
    import html as _html

    def esc(s):
        return _html.escape(s, quote=False)

    out = []
    pattern = re.compile(r'(\*\*.+?\*\*|`[^`]+`)')
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append(_asl_span(esc(text[pos:m.start()])))
        tok = m.group(0)
        if tok.startswith('**'):
            out.append('<strong>' + _asl_span(esc(tok[2:-2])) + '</strong>')
        else:  # 行内代码
            i = _lid()
            out.append(f'<code data-lake-id="{i}" id="{i}">' + _asl_span(esc(tok[1:-1])) + '</code>')
        pos = m.end()
    if pos < len(text):
        out.append(_asl_span(esc(text[pos:])))
    return ''.join(out) if out else '<br>'


def _normalize_quote_lines(quotes):
    """规范化引用块内的空行，避免 markdown 的语法空行变成可见空段落。

    markdown 里空行只是分隔符（渲染不出空行），语雀里空段落是真实内容（渲染成空行）。
    默认做三件事：
    1. 连续空行折叠为最多 1 个空段落
    2. 列表项之间的空行丢弃（markdown 列表的常规写法，不应产生视觉间隔）
    3. 引用块开头 / 末尾的空行丢弃
    """
    def is_item(s):
        return bool(re.match(r'^(\d+\.|[-*+])\s+', (s or '').strip()))

    out = []
    for idx, q in enumerate(quotes):
        if q.strip():
            out.append(q)
            continue
        nxt = next((x for x in quotes[idx + 1:] if x.strip()), None)
        if nxt is None:                      # 末尾空行
            continue
        prev = out[-1] if out else None
        if prev is None:                     # 开头空行
            continue
        if not prev.strip():                 # 连续空行
            continue
        if is_item(prev) and is_item(nxt):   # 列表项之间
            continue
        out.append('')
    return out


def md2asl(md_text, keep_blank=False):
    """将 Markdown 转换为语雀 ASL 格式（编辑器真实存储格式，含 data-lake-id）。

    与 md2lake 的区别：ASL 是语雀编辑器的原生格式，用它提交能**保持折叠块等复杂结构不被破坏**。

    keep_blank=False（默认）：引用块内的语法空行会被折叠（连续空行→1 个、列表项之间→0 个、
    首尾→0 个），避免 markdown 空行被物化成可见空段落导致「间隔变大」。
    keep_blank=True：完全按字面保留每个空行（旧行为）。
    """
    lines = md_text.split('\n')
    parts = []
    i = 0
    in_list = None       # 'ul' / 'ol'
    list_id = None
    list_items = []

    def flush_list():
        nonlocal in_list, list_id, list_items
        if in_list and list_items:
            lis = []
            for it in list_items:
                li_id = _lid()
                lis.append(f'<li fid="{list_id}" data-lake-id="{li_id}" id="{li_id}">'
                           + _asl_inline(it) + '</li>')
            parts.append(f'<{in_list} list="{list_id}">' + ''.join(lis) + f'</{in_list}>')
        in_list = None
        list_id = None
        list_items = []

    while i < len(lines):
        line = lines[i]

        # 表格：当前行像表头，且下一行是分隔行
        if '|' in line and i + 1 < len(lines) and re.match(
            r'^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$', lines[i + 1]
        ):
            flush_list()

            def _cells(s):
                s = s.strip()
                if s.startswith('|'):
                    s = s[1:]
                if s.endswith('|'):
                    s = s[:-1]
                return [c.strip() for c in s.split('|')]

            rows = [_cells(line)]
            i += 2  # 跳过表头 + 分隔行
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1
            tid = _lid()
            trs = []
            for row in rows:
                tds = []
                for cell in row:
                    td_id, p_id = _lid(), _lid()
                    tds.append(f'<td data-lake-id="{td_id}" id="{td_id}">'
                               f'<p data-lake-id="{p_id}" id="{p_id}">{_asl_inline(cell)}</p></td>')
                tr_id = _lid()
                trs.append(f'<tr data-lake-id="{tr_id}" id="{tr_id}">' + ''.join(tds) + '</tr>')
            parts.append(f'<table data-lake-id="{tid}" id="{tid}"><tbody>'
                         + ''.join(trs) + '</tbody></table>')
            continue

        # 标题
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            flush_list()
            lv = len(m.group(1))
            bid = _lid()
            parts.append(f'<h{lv} data-lake-id="{bid}" id="{bid}">'
                         + _asl_inline(m.group(2)) + f'</h{lv}>')
            i += 1
            continue

        # 引用块
        if line.startswith('>'):
            flush_list()
            quotes = []
            while i < len(lines) and lines[i].startswith('>'):
                quotes.append(lines[i][1:].lstrip())
                i += 1
            bid = _lid()
            inner = []
            for q in (quotes if keep_blank else _normalize_quote_lines(quotes)):
                pid = _lid()
                inner.append(f'<p data-lake-id="{pid}" id="{pid}">'
                             + (_asl_inline(q) if q.strip() else '<br>') + '</p>')
            parts.append(f'<blockquote data-lake-id="{bid}" id="{bid}">'
                         + ''.join(inner) + '</blockquote>')
            continue

        # 无序列表
        m = re.match(r'^[-*+]\s+(.+)$', line)
        if m:
            if in_list != 'ul':
                flush_list()
                in_list, list_id, list_items = 'ul', _lid(), []
            list_items.append(m.group(1))
            i += 1
            continue

        # 有序列表
        m = re.match(r'^\d+\.\s+(.+)$', line)
        if m:
            if in_list != 'ol':
                flush_list()
                in_list, list_id, list_items = 'ol', _lid(), []
            list_items.append(m.group(1))
            i += 1
            continue

        # 空行
        if not line.strip():
            flush_list()
            i += 1
            continue

        # 普通段落
        flush_list()
        bid = _lid()
        parts.append(f'<p data-lake-id="{bid}" id="{bid}">' + _asl_inline(line) + '</p>')
        i += 1

    flush_list()
    return ''.join(parts)


def raw_get(url, cookie='', csrf_token='', x_login='', referer='https://www.yuque.com/'):
    """发送 GET 请求并返回完整字节内容（不截断、不解析 JSON）。"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cookie': cookie,
        'Referer': referer,
        'Upgrade-Insecure-Requests': '1',
    }
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=120) as resp:
        return resp.read()


def cmd_export_md(cookie, csrf_token, x_login, doc_id, book_id):
    """导出文档为语雀原生 Markdown（保真度高于自行解析 lake HTML）。

    步骤：
      1. GET /api/docs/{doc_id}?book_id=&mode=edit  → 取 doc slug
      2. list-books                                 → 由 book_id 取 book slug
      3. GET /{user}/{book}/{doc}/markdown?attachment=true&latexcode=true
             &anchor=true&linebreak=true&useMdai=true  → 返回完整 Markdown 文本
    """
    doc = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit')
    if isinstance(doc, dict) and '_error' in doc:
        return doc
    doc_slug = doc.get('slug')
    if not doc_slug:
        return {'_error': '无法获取文档 slug'}

    books = cmd_list_books(cookie, csrf_token, x_login)
    if isinstance(books, dict) and '_error' in books:
        return books
    book = next((b for b in books if b.get('id') == int(book_id)), None)
    if not book:
        return {'_error': f'未找到 book_id={book_id} 对应的知识库'}
    book_slug = book.get('slug')
    user_login = x_login or book.get('user') or ''

    params = urllib.parse.urlencode({
        'attachment': 'true',
        'latexcode': 'true',
        'anchor': 'true',
        'linebreak': 'true',
        'useMdai': 'true',
    })
    url = f'{API_BASE}/{user_login}/{book_slug}/{doc_slug}/markdown?{params}'
    referer = f'{API_BASE}/{user_login}/{book_slug}/{doc_slug}'

    try:
        raw = raw_get(url, cookie=cookie, csrf_token=csrf_token, x_login=x_login, referer=referer)
    except urllib.error.HTTPError as e:
        return {'_error': f'HTTP {e.code}', '_url': url}
    except Exception as e:
        return {'_error': str(e), '_url': url}

    text = raw.decode('utf-8', errors='replace')
    return {
        '_markdown': text,
        'doc_id': doc_id,
        'book_id': book_id,
        'doc_slug': doc_slug,
        'book_slug': book_slug,
        'user_login': user_login,
        'url': url,
        'chars': len(text),
    }


def main():
    if len(sys.argv) < 2:
        print('用法: python yuque_client.py <command> [args...]')
        print('命令: whoami, list-books, list-docs, find-docs, get-doc, get-toc, create-doc, update-doc,')
        print('      delete-doc, search, get-doc-outline, replace-section, md2lake, md2asl, export-md,')
        print('      get-doc-versions, get-doc-version, diff-versions, restore-version')

        print('全局参数: --output-file <path>, --body-only')
        sys.exit(1)

    # 提取全局参数
    args = sys.argv[1:]
    output_file = None
    body_only = False
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == '--output-file' and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == '--body-only':
            body_only = True
            i += 1
        else:
            filtered_args.append(args[i])
            i += 1

    if not filtered_args:
        print('错误: 未指定命令')
        sys.exit(1)

    cookie, csrf_token, x_login = get_credentials()
    if not cookie:
        print('错误: 未设置凭证。请设置环境变量 YUQUE_COOKIE, YUQUE_CSRF_TOKEN, YUQUE_X_LOGIN 或创建 credentials.json')
        sys.exit(1)

    command = filtered_args[0]
    cmd_args = filtered_args[1:]

    if command == 'whoami':
        result = cmd_whoami(cookie, csrf_token, x_login)
    elif command == 'list-books':
        result = cmd_list_books(cookie, csrf_token, x_login)
    elif command == 'resolve-url':
        url = cmd_args[0]
        result = cmd_resolve_url(cookie, csrf_token, x_login, url)
    elif command == 'list-docs':
        book_id = int(cmd_args[0])
        offset = int(cmd_args[1]) if len(cmd_args) > 1 else 0
        limit = int(cmd_args[2]) if len(cmd_args) > 2 else 20
        result = cmd_list_docs(cookie, csrf_token, x_login, book_id, offset, limit)
    elif command == 'find-docs':
        keyword = cmd_args[0]
        page_limit = int(cmd_args[1]) if len(cmd_args) > 1 else 100
        max_pages = int(cmd_args[2]) if len(cmd_args) > 2 else 50
        result = cmd_find_docs(cookie, csrf_token, x_login, keyword, page_limit, max_pages)
    elif command == 'get-doc':

        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        mode = cmd_args[2] if len(cmd_args) > 2 else 'edit'
        result = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode)
        # --body-only: 只输出 body HTML
        if body_only and isinstance(result, dict) and 'body' in result:
            output = result['body']
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f'Body written to: {output_file} ({len(output)} chars)')
            else:
                sys.stdout.buffer.write(output.encode('utf-8'))
            return
    elif command == 'get-toc':
        book_id = int(cmd_args[0])
        result = cmd_get_toc(cookie, csrf_token, x_login, book_id)
    elif command == 'create-doc':
        book_id = int(cmd_args[0])
        title = cmd_args[1]
        slug = cmd_args[2] if len(cmd_args) > 2 else ''
        body = cmd_args[3] if len(cmd_args) > 3 else ''
        result = cmd_create_doc(cookie, csrf_token, x_login, book_id, title, slug, body)
    elif command == 'update-doc':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        title = None
        body = None
        body_asl = None
        # 解析剩余参数，支持 --body-file（HTML）/ --asl-file（ASL，推荐）
        j = 2
        while j < len(cmd_args):
            if cmd_args[j] == '--body-file':
                j += 1
                if j < len(cmd_args):
                    file_path = cmd_args[j]
                    with open(file_path, 'r', encoding='utf-8') as f:
                        body = f.read()
                j += 1
            elif cmd_args[j] == '--asl-file':
                j += 1
                if j < len(cmd_args):
                    with open(cmd_args[j], 'r', encoding='utf-8') as f:
                        body_asl = f.read()
                j += 1
            elif title is None:
                title = cmd_args[j]
                j += 1
            elif body is None and body_asl is None:
                body = cmd_args[j]
                j += 1
            else:
                j += 1
        result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title, body, body_asl)
    elif command == 'delete-doc':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        result = cmd_delete_doc(cookie, csrf_token, x_login, doc_id, book_id)
    elif command == 'search':
        keyword = cmd_args[0]
        search_type = cmd_args[1] if len(cmd_args) > 1 else 'doc'
        result = cmd_search(cookie, csrf_token, x_login, keyword, search_type)
    elif command == 'get-doc-versions':
        doc_id = int(cmd_args[0])
        limit = int(cmd_args[1]) if len(cmd_args) > 1 else 200
        offset = int(cmd_args[2]) if len(cmd_args) > 2 else 0
        result = cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id, limit, offset)
    elif command == 'get-doc-version':
        doc_id = cmd_args[0]
        version_id = cmd_args[1]
        fmt = 'asl'
        j = 2
        while j < len(cmd_args):
            if cmd_args[j] == '--format' and j + 1 < len(cmd_args):
                fmt = cmd_args[j + 1].lower()
                j += 2
            else:
                j += 1
        if fmt not in ('asl', 'html'):
            print('错误: --format 只支持 asl（默认）或 html')
            sys.exit(1)
        result = cmd_get_doc_version(cookie, csrf_token, x_login, doc_id, version_id, fmt)
        if isinstance(result, dict) and '_content' in result:
            content = result.pop('_content')
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'{fmt.upper()} content written to: {output_file} ({len(content)} chars)')
                return
            if body_only:
                sys.stdout.buffer.write(content.encode('utf-8'))
                sys.stdout.buffer.write(b'\n')
                return
            # 未指定输出方式时只打印元数据，避免正文撑爆终端
            result['_hint'] = '正文未输出：加 --body-only 打印，或 --output-file <path> 写入文件'
    elif command == 'diff-versions':
        doc_id = cmd_args[0]
        version_id_1 = cmd_args[1]
        version_id_2 = cmd_args[2]
        fmt = 'asl'
        if len(cmd_args) > 4 and cmd_args[3] == '--format':
            fmt = cmd_args[4].lower()
        result = cmd_diff_versions(cookie, csrf_token, x_login, doc_id, version_id_1, version_id_2, fmt)
        if isinstance(result, dict) and '_diff' in result:
            diff_text = result.pop('_diff')
            if not diff_text:
                print(f'两个版本正文一致（v{version_id_1} vs v{version_id_2}，各 {result["lines"]["from"]} 行）')
            elif output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(diff_text)
                print(f'Diff written to: {output_file} ({len(diff_text)} chars, '
                      f'{result.get("changed_lines", 0)} 行变更)')
            else:
                sys.stdout.buffer.write(diff_text.encode('utf-8'))
                sys.stdout.buffer.write(b'\n')
            return
    elif command == 'restore-version':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        version_id = cmd_args[2]
        with_title = '--with-title' in cmd_args[3:]
        result = cmd_restore_doc_version(cookie, csrf_token, x_login, doc_id, book_id, version_id, with_title)
    elif command == 'get-doc-outline':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        result = cmd_get_doc_outline(cookie, csrf_token, x_login, doc_id, book_id)
        # outline 直接输出文本格式
        if isinstance(result, str):
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f'Outline written to: {output_file}')
            else:
                print(result)
            return
    elif command == 'replace-section':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        heading_text = None
        new_content = None
        j = 2
        while j < len(cmd_args):
            if cmd_args[j] == '--heading' and j + 1 < len(cmd_args):
                heading_text = cmd_args[j + 1]
                j += 2
            elif cmd_args[j] == '--body-file' and j + 1 < len(cmd_args):
                with open(cmd_args[j + 1], 'r', encoding='utf-8') as f:
                    new_content = f.read()
                j += 2
            else:
                j += 1
        if not heading_text:
            print('错误: replace-section 需要 --heading 参数')
            sys.exit(1)
        if new_content is None:
            print('错误: replace-section 需要 --body-file 参数')
            sys.exit(1)
        result = cmd_replace_section(cookie, csrf_token, x_login, doc_id, book_id, heading_text, new_content)
    elif command in ('md2lake', 'md2asl'):
        md_text = None
        keep_blank = '--keep-blank' in cmd_args
        j = 0
        while j < len(cmd_args):
            if cmd_args[j] == '--input-file' and j + 1 < len(cmd_args):
                with open(cmd_args[j + 1], 'r', encoding='utf-8') as f:
                    md_text = f.read()
                j += 2
            elif cmd_args[j] in ('--keep-blank', '--input-file'):
                j += 1
            elif md_text is None:
                md_text = cmd_args[j].replace('\\n', '\n')
                j += 1
            else:
                j += 1
        if md_text is None:
            # 从 stdin 读取
            md_text = sys.stdin.read()
        out_text = md2asl(md_text, keep_blank=keep_blank) if command == 'md2asl' else md2lake(md_text)
        label = 'ASL' if command == 'md2asl' else 'Lake HTML'
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(out_text)
            print(f'{label} written to: {output_file} ({len(out_text)} chars)')
        else:
            sys.stdout.buffer.write(out_text.encode('utf-8'))
            sys.stdout.buffer.write(b'\n')
        return
    elif command == 'export-md':
        doc_id = cmd_args[0]
        book_id = int(cmd_args[1])
        result = cmd_export_md(cookie, csrf_token, x_login, doc_id, book_id)
        if isinstance(result, dict) and '_markdown' in result:
            md_text = result.pop('_markdown')
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(md_text)
                print(f'Markdown written to: {output_file} ({len(md_text)} chars)')
            else:
                sys.stdout.buffer.write(md_text.encode('utf-8'))
                sys.stdout.buffer.write(b'\n')
            return
        # 失败时走统一 JSON 输出
    else:
        print(f'未知命令: {command}')
        sys.exit(1)

    # 输出结果
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f'Output written to: {output_file} ({len(output)} chars)')
    else:
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode('utf-8', errors='replace'))
            sys.stdout.buffer.write(b'\n')


if __name__ == '__main__':
    # 设置stdout编码
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
