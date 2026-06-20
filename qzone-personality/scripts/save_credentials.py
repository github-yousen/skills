#!/usr/bin/env python3
"""
保存QQ空间凭证脚本
用法: python save_credentials.py --cookie "完整cookie字符串"
"""

import argparse
import json
import os
import re
import sys

CONFIG_DIR = os.path.expanduser("~/.hermes/qzone")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def extract_cookie_fields(cookie_str):
    """从Cookie字符串提取关键字段"""
    fields = {}
    
    # 提取各字段
    patterns = {
        'uin': r'uin=([^;]+)',
        'skey': r'skey=([^;]+)',
        'p_skey': r'p_skey=([^;]+)',
        'p_uin': r'p_uin=([^;]+)',
        'pt4_token': r'pt4_token=([^;]+)',
        'ptcz': r'ptcz=([^;]+)',
        'RK': r'RK=([^;]+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, cookie_str)
        if match:
            fields[key] = match.group(1)
    
    return fields


def calc_gtk(skey):
    """计算g_tk参数"""
    hash_val = 5381
    for char in skey:
        hash_val += (hash_val << 5) + ord(char)
    return hash_val & 2147483647


def main():
    parser = argparse.ArgumentParser(description='保存QQ空间凭证')
    parser.add_argument('--cookie', required=True, help='完整的Cookie字符串')
    parser.add_argument('--qq', help='QQ号（可选，会自动从cookie提取）')
    args = parser.parse_args()
    
    # 提取字段
    fields = extract_cookie_fields(args.cookie)
    
    if 'uin' not in fields:
        print("错误: Cookie中未找到uin字段")
        sys.exit(1)
    
    if 'skey' not in fields:
        print("错误: Cookie中未找到skey字段")
        sys.exit(1)
    
    # 提取QQ号
    qq = args.qq or fields['uin'].lstrip('o')
    
    # 计算g_tk
    gtk = calc_gtk(fields['skey'])
    
    # 构建配置
    config = {
        'qq': qq,
        'uin': fields['uin'],
        'skey': fields['skey'],
        'p_skey': fields.get('p_skey', ''),
        'p_uin': fields.get('p_uin', ''),
        'pt4_token': fields.get('pt4_token', ''),
        'ptcz': fields.get('ptcz', ''),
        'RK': fields.get('RK', ''),
        'g_tk': gtk,
        'raw_cookie': args.cookie
    }
    
    # 创建目录
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    # 保存配置
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"凭证已保存到: {CONFIG_FILE}")
    print(f"QQ号: {qq}")
    print(f"g_tk: {gtk}")
    print(f"提取的字段: {', '.join(fields.keys())}")


if __name__ == '__main__':
    main()
