#!/usr/bin/env python3
"""
爬取QQ空间用户资料脚本
用法: python crawl_profile.py --output ~/.hermes/qzone/data/
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import ssl
import gzip

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
    if config.get('uin'):
        parts.append(f"uin={config['uin']}")
    if config.get('skey'):
        parts.append(f"skey={config['skey']}")
    if config.get('p_skey'):
        parts.append(f"p_skey={config['p_skey']}")
    if config.get('p_uin'):
        parts.append(f"p_uin={config['p_uin']}")
    if config.get('pt4_token'):
        parts.append(f"pt4_token={config['pt4_token']}")
    if config.get('ptcz'):
        parts.append(f"ptcz={config['ptcz']}")
    if config.get('RK'):
        parts.append(f"RK={config['RK']}")
    return '; '.join(parts)


def fetch_json(url, cookie, referer):
    """通用JSON请求"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookie,
        'Referer': referer,
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
            
            # 解析JSONP响应
            if text.startswith('_Callback('):
                json_str = text[10:-3]
                return json.loads(json_str)
            elif '(' in text and text.endswith(');'):
                # 其他JSONP格式
                start = text.index('(') + 1
                json_str = text[start:-2]
                return json.loads(json_str)
            else:
                return json.loads(text)
    except Exception as e:
        print(f"请求失败 {url}: {e}")
        return None


def fetch_profile(uin, g_tk, cookie):
    """获取用户主页信息"""
    url = (
        f"https://user.qzone.qq.com/proxy/domain/r.qzone.qq.com/cgi-bin/main_page_cgi"
        f"?uin={uin}"
        f"&param=3_{uin}_0%7C8_8_{uin}_0_0_0_0_1%7C16"
        f"&g_tk={g_tk}"
    )
    return fetch_json(url, cookie, f'https://user.qzone.qq.com/{uin}')


def fetch_visitor(uin, g_tk, cookie):
    """获取访客信息"""
    url = (
        f"https://user.qzone.qq.com/proxy/domain/g.qzone.qq.com/cgi-bin/friendshow/cgi_get_visitor_simple"
        f"?uin={uin}"
        f"&mask=1"
        f"&g_tk={g_tk}"
    )
    return fetch_json(url, cookie, f'https://user.qzone.qq.com/{uin}')


def fetch_friends(uin, g_tk, cookie):
    """获取好友列表"""
    url = (
        f"https://user.qzone.qq.com/proxy/domain/r.qzone.qq.com/cgi-bin/tfriend/friend_mngfrd_get.cgi"
        f"?uin={uin}"
        f"&fupdate=1"
        f"&scene=21"
        f"&g_tk={g_tk}"
    )
    return fetch_json(url, cookie, f'https://user.qzone.qq.com/{uin}')


def main():
    parser = argparse.ArgumentParser(description='爬取QQ空间用户资料')
    parser.add_argument('--output', default=os.path.expanduser('~/.hermes/qzone/data/'),
                       help='输出目录')
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    qq = config['qq']
    uin = config['uin']
    g_tk = config['g_tk']
    cookie = build_cookie(config)
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    print(f"开始获取QQ号 {qq} 的资料...")
    
    profile_data = {
        'qq': qq,
        'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    # 1. 主页信息
    print("获取主页信息...")
    main_page = fetch_profile(uin, g_tk, cookie)
    if main_page:
        profile_data['main_page'] = main_page
        print(f"  成功")
    else:
        print(f"  失败")
    
    time.sleep(0.5)
    
    # 2. 访客信息
    print("获取访客信息...")
    visitors = fetch_visitor(uin, g_tk, cookie)
    if visitors:
        profile_data['visitors'] = visitors
        print(f"  成功")
    else:
        print(f"  失败")
    
    time.sleep(0.5)
    
    # 3. 好友列表
    print("获取好友列表...")
    friends = fetch_friends(uin, g_tk, cookie)
    if friends:
        profile_data['friends'] = friends
        print(f"  成功")
    else:
        print(f"  失败")
    
    # 保存结果
    output_file = os.path.join(args.output, 'profile.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n资料获取完成！")
    print(f"保存到: {output_file}")


if __name__ == '__main__':
    main()
