#!/usr/bin/env python3
"""
爬取QQ空间说说脚本
用法: python crawl_emotions.py --output ~/.hermes/qzone/data/

正确的接口: taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import ssl
import gzip

# 加载配置
CONFIG_FILE = os.path.expanduser("~/.hermes/qzone/config.json")


def load_config():
    """加载凭证配置"""
    if not os.path.exists(CONFIG_FILE):
        print("错误: 配置文件不存在，请先运行 save_credentials.py")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_cookie(config):
    """构建Cookie字符串"""
    parts = []
    for k in ['uin', 'skey', 'p_skey', 'p_uin', 'pt4_token', 'ptcz', 'RK']:
        if config.get(k):
            parts.append(f"{k}={config[k]}")
    return '; '.join(parts)


def fetch_emotions(uin, g_tk, cookie, pos=0, num=20):
    """获取说说列表"""
    url = (
        f"https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
        f"?uin={uin}"
        f"&ftype=0"
        f"&sort=0"
        f"&pos={pos}"
        f"&num={num}"
        f"&reply=0"
        f"&g_tk={g_tk}"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'Cookie': cookie,
        'Referer': f'https://user.qzone.qq.com/{uin}',
        'x-kl-ajax-request': 'Ajax_Request',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            text = raw.decode('utf-8', errors='ignore')
            
            # 解析JSONP响应: _Callback({...});
            if text.startswith('_Callback('):
                json_str = text[10:-3]
            else:
                json_str = text
            
            # 提取total
            total = 0
            import re
            total_match = re.search(r'"total":\s*(\d+)', json_str)
            if total_match:
                total = int(total_match.group(1))
            
            # 直接解析msglist数组（避免整个JSON解析失败）
            msglist = []
            start = json_str.find('"msglist":[')
            if start >= 0:
                array_start = start + len('"msglist":')
                bracket_count = 0
                i = array_start
                while i < len(json_str):
                    if json_str[i] == '[':
                        bracket_count += 1
                    elif json_str[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            array_end = i + 1
                            break
                    i += 1
                
                try:
                    msglist = json.loads(json_str[array_start:array_end])
                except json.JSONDecodeError as e:
                    print(f"  msglist解析失败: {e}")
            
            return {'msglist': msglist, 'total': total}
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def parse_emotions(data):
    """解析说说数据"""
    emotions = []
    
    if not data or 'msglist' not in data:
        return emotions
    
    msg_list = data.get('msglist', []) or []
    
    for msg in msg_list:
        # 提取文本内容
        content = msg.get('content', '').strip()
        
        # 提取评论
        comments = []
        for cmt in msg.get('commentlist', []) or []:
            comments.append({
                'name': cmt.get('name', ''),
                'content': cmt.get('content', ''),
                'time': cmt.get('createTime2', ''),
            })
        
        emotion = {
            'tid': msg.get('tid', ''),
            'content': content,
            'createTime': msg.get('createTime', ''),
            'created_time': msg.get('created_time', 0),
            'cmtnum': msg.get('cmtnum', 0),
            'comments': comments,
            'pictotal': msg.get('pictotal', 0),
            'source': msg.get('source_name', ''),
            'secret': msg.get('secret', 0),
        }
        
        emotions.append(emotion)
    
    return emotions


def main():
    parser = argparse.ArgumentParser(description='爬取QQ空间说说')
    parser.add_argument('--output', default=os.path.expanduser('~/.hermes/qzone/data/'), 
                       help='输出目录')
    parser.add_argument('--max', type=int, default=2000, help='最大爬取数量')
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    qq = config['qq']
    uin = config['uin']
    g_tk = config['g_tk']
    cookie = build_cookie(config)
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    print(f"开始爬取QQ号 {qq} 的说说...")
    
    all_emotions = []
    pos = 0
    num = 20  # 每页20条
    
    while pos < args.max:
        print(f"正在获取第 {pos + 1} - {pos + num} 条...")
        
        data = fetch_emotions(uin, g_tk, cookie, pos, num)
        
        if not data:
            print("获取失败，停止爬取")
            break
        
        emotions = parse_emotions(data)
        
        if not emotions:
            print("没有更多说说了")
            break
        
        all_emotions.extend(emotions)
        
        # 获取总数
        total = data.get('total', 0)
        
        print(f"  获取到 {len(emotions)} 条，累计 {len(all_emotions)}/{total}")
        
        pos += num
        
        # 已获取完所有
        if pos >= total:
            print("已获取所有说说")
            break
        
        # 避免请求过快
        time.sleep(0.5)
    
    # 保存结果
    output_file = os.path.join(args.output, 'emotions.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'qq': qq,
            'uin': uin,
            'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(all_emotions),
            'emotions': all_emotions
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n爬取完成！")
    print(f"总计: {len(all_emotions)} 条说说")
    print(f"保存到: {output_file}")


if __name__ == '__main__':
    main()
