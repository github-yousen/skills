# 语雀API客户端 - 供skill调用的底层工具脚本
# 用法: python yuque_client.py <command> [args...]
# 命令:
#   whoami                        - 获取当前用户信息
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
#   get-doc-versions <doc_id>     - 获取文档版本列表
#   get-doc-outline <doc_id> <book_id>           - 获取文档标题层级结构
#   replace-section <doc_id> <book_id> --heading <text> --body-file <path> - 替换指定section
#   md2lake [text] [--input-file <path>]         - Markdown 转 lake HTML
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


def cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title=None, body=None):
    """更新文档。
    
    使用两步更新策略：
    1. PUT /api/docs/:id/content — 更新 body_draft（语雀前端渲染依赖此字段）
    2. PUT /api/docs/:id — 更新 body 和 title（已发布内容）
    
    这样确保语雀网页端能立即看到更新后的内容。
    """
    result_info = {}
    
    # Step 1: 如果有 body，通过 content 接口更新 body_draft
    if body is not None:
        # 先获取 draft_version
        doc_info = api_request('GET', f'/api/docs/{doc_id}',
                               params={'book_id': book_id, 'mode': 'edit'},
                               cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in doc_info:
            return {'_error': 'Failed to get draft_version', '_detail': doc_info}
        
        draft_version = doc_info.get('data', {}).get('draft_version', 0)
        
        content_data = {
            'format': 'lake',
            'body_asl': body,
            'body_draft_asl': body,
            'save_type': 'user',
            'draft_version': draft_version,
        }
        r_content = api_request('PUT', f'/api/docs/{doc_id}/content', data=content_data,
                                cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in r_content:
            result_info['_content_warning'] = f"content接口失败: {r_content.get('_error', '')}"
        else:
            result_info['content_updated'] = True
    
    # Step 2: 用普通接口更新 body 和 title
    doc_data = {'book_id': book_id}
    if title is not None:
        doc_data['title'] = title
    if body is not None:
        doc_data['body'] = body
    
    r = api_request('PUT', f'/api/docs/{doc_id}', data=doc_data,
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return {**result_info, '_error': r.get('_error'), '_body': r.get('_body', '')}
    
    d = r.get('data', {})
    return {
        **result_info,
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
    }


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


def cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id):
    r = api_request('GET', '/api/doc_versions', params={'doc_id': doc_id},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    versions = r.get('data', [])
    result = []
    for v in versions:
        result.append({
            'id': v.get('id'),
            'title': v.get('title'),
            'draft': v.get('draft'),
            'created_at': v.get('created_at'),
            'isReleased': v.get('isReleased'),
        })
    return result


def cmd_get_doc_outline(cookie, csrf_token, x_login, doc_id, book_id):
    """获取文档标题层级结构（h1-h6 outline）"""
    doc = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit')
    if '_error' in doc:
        return doc
    body = doc.get('body', '')
    headings = re.findall(r'<h([1-6])[^>]*>.*?<span class="ne-text">(.*?)</span>.*?</h\1>', body)
    lines = []
    for level, text in headings:
        indent = '  ' * (int(level) - 1)
        lines.append(f'{indent}H{level}: {text}')
    return '\n'.join(lines)


def cmd_replace_section(cookie, csrf_token, x_login, doc_id, book_id, heading_text, new_content):
    """按 heading 文本定位 section，替换该 section 内容"""
    doc = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit')
    if '_error' in doc:
        return doc
    body = doc.get('body', '')

    # 找到匹配的 heading
    pattern = re.compile(
        r'<h([1-6])([^>]*)>.*?' + re.escape(heading_text) + r'.*?</h\1>',
        re.DOTALL
    )
    match = pattern.search(body)
    if not match:
        return {'_error': f'Heading not found: "{heading_text}"'}

    heading_level = int(match.group(1))
    section_start = match.start()

    # 找到该 heading 之前最近的 <hr>（如果紧邻），也包含进替换范围
    before_segment = body[max(0, section_start - 200):section_start]
    hr_pos = before_segment.rfind('<hr')
    if hr_pos != -1:
        # 检查 hr 和 heading 之间是否只有空白
        between = before_segment[hr_pos:]
        between_cleaned = re.sub(r'<hr[^>]*/?>[\s]*', '', between)
        if between_cleaned.strip() == '':
            section_start = max(0, section_start - 200) + hr_pos

    # 找到下一个同级或更高级 heading 的位置作为 end
    rest = body[match.end():]
    end_pattern = re.compile(r'<h([1-' + str(heading_level) + r'])[^>]*>')
    end_match = end_pattern.search(rest)
    if end_match:
        section_end = match.end() + end_match.start()
    else:
        # 没有后续同级 heading，取到文档结尾（但保留 </div> 闭合标签）
        last_div = body.rfind('</div>')
        section_end = last_div if last_div > match.end() else len(body)

    # 替换
    new_body = body[:section_start] + new_content + body[section_end:]

    # 更新文档
    result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title=None, body=new_body)
    result['section_replaced'] = heading_text
    result['original_length'] = len(body)
    result['new_length'] = len(new_body)
    return result


def md2lake(md_text):
    """将 Markdown 文本转换为语雀 lake HTML 格式。

    支持：标题、段落、加粗、斜体、行内代码、引用块、有序/无序列表、代码块、分割线、换行。
    """
    lines = md_text.split('\n')
    html_parts = []
    i = 0
    in_list = None  # 'ul' or 'ol'

    def inline_format(text):
        """处理行内格式：加粗、斜体、行内代码"""
        # 行内代码（先处理，避免内部被其他规则干扰）
        text = re.sub(r'`([^`]+)`', r'<code class="ne-code"><span class="ne-text">\1</span></code>', text)
        # 加粗
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong><span class="ne-text">\1</span></strong>', text)
        # 斜体
        text = re.sub(r'\*(.+?)\*', r'<em><span class="ne-text">\1</span></em>', text)
        # 普通文本片段包装（如果还没被包装）
        if '<span' not in text and text.strip():
            text = f'<span class="ne-text">{text}</span>'
        return text

    def close_list():
        nonlocal in_list
        if in_list == 'ul':
            html_parts.append('</ul>')
        elif in_list == 'ol':
            html_parts.append('</ol>')
        in_list = None

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
            code_content = '\n'.join(code_lines)
            html_parts.append(
                f'<pre class="ne-codeblock" data-language="{lang}">'
                f'<code>{code_content}</code></pre>'
            )
            i += 1
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
            text = heading_match.group(2)
            html_parts.append(
                f'<h{level}><span class="ne-text">{text}</span></h{level}>'
            )
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


def main():
    if len(sys.argv) < 2:
        print('用法: python yuque_client.py <command> [args...]')
        print('命令: whoami, list-books, list-docs, find-docs, get-doc, get-toc, create-doc, update-doc,')
        print('      delete-doc, search, get-doc-versions, get-doc-outline, replace-section, md2lake')

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
        # 解析剩余参数，支持 --body-file
        j = 2
        while j < len(cmd_args):
            if cmd_args[j] == '--body-file':
                j += 1
                if j < len(cmd_args):
                    file_path = cmd_args[j]
                    with open(file_path, 'r', encoding='utf-8') as f:
                        body = f.read()
                j += 1
            elif title is None:
                title = cmd_args[j]
                j += 1
            elif body is None:
                body = cmd_args[j]
                j += 1
            else:
                j += 1
        result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title, body)
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
        result = cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id)
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
    elif command == 'md2lake':
        md_text = None
        j = 0
        while j < len(cmd_args):
            if cmd_args[j] == '--input-file' and j + 1 < len(cmd_args):
                with open(cmd_args[j + 1], 'r', encoding='utf-8') as f:
                    md_text = f.read()
                j += 2
            elif md_text is None:
                md_text = cmd_args[j].replace('\\n', '\n')
                j += 1
            else:
                j += 1
        if md_text is None:
            # 从 stdin 读取
            md_text = sys.stdin.read()
        lake_html = md2lake(md_text)
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(lake_html)
            print(f'Lake HTML written to: {output_file} ({len(lake_html)} chars)')
        else:
            sys.stdout.buffer.write(lake_html.encode('utf-8'))
            sys.stdout.buffer.write(b'\n')
        return
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
