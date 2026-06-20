#!/usr/bin/env python3
"""
MBTI分析脚本
用法: python analyze_mbti.py --data ~/.hermes/qzone/data/ --output ~/.hermes/qzone/analysis/

此脚本会生成分析prompt，实际分析由LLM完成
"""

import argparse
import json
import os
import sys


def load_emotions(data_dir):
    """加载说说数据"""
    filepath = os.path.join(data_dir, 'emotions.json')
    if not os.path.exists(filepath):
        print(f"错误: 说说数据文件不存在: {filepath}")
        sys.exit(1)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_profile(data_dir):
    """加载资料数据"""
    filepath = os.path.join(data_dir, 'profile.json')
    if not os.path.exists(filepath):
        print(f"警告: 资料文件不存在: {filepath}")
        return {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_emotions_for_analysis(emotions_data, max_count=200):
    """格式化说说数据用于分析"""
    emotions = emotions_data.get('emotions', [])[:max_count]
    
    formatted = []
    for i, e in enumerate(emotions, 1):
        content = e.get('content', '').strip()
        if not content:
            continue
        
        time_str = e.get('createTime', '')
        source = e.get('source', '')
        
        formatted.append(f"[{i}] [{time_str}] {content}")
    
    return '\n'.join(formatted)


def generate_mbti_prompt(emotions_data, profile_data):
    """生成MBTI分析prompt"""
    qq = emotions_data.get('qq', '未知')
    total = emotions_data.get('total', 0)
    
    # 格式化说说
    emotions_text = format_emotions_for_analysis(emotions_data)
    
    prompt = f"""你是一位专业的MBTI性格分析师。请根据以下QQ空间说说内容，对用户进行详细的MBTI人格分析。

## 用户信息
- QQ号: {qq}
- 说说总数: {total}

## 说说内容（按时间排列）

{emotions_text}

## 分析要求

请从以下四个维度进行分析，每个维度需要引用具体的说说内容作为证据：

### 1. 外向(E) vs 内向(I)
- 用户的能量来源
- 社交倾向
- 引用相关说说

### 2. 感觉(S) vs 直觉(N)
- 用户关注的信息类型
- 思维方式
- 引用相关说说

### 3. 思维(T) vs 情感(F)
- 决策方式
- 价值判断标准
- 引用相关说说

### 4. 判断(J) vs 感知(P)
- 生活方式
- 计划性
- 引用相关说说

## 输出格式

请严格按照以下格式输出：

### MBTI类型判定

**判定结果: [XXXX]**

### 维度分析

#### 1. E/I 维度
- **得分**: X% E / Y% I
- **判定**: [E或I]
- **分析**: [详细分析]
- **证据**:
  - "[引用说说1]"
  - "[引用说说2]"

#### 2. S/N 维度
（同上格式）

#### 3. T/F 维度
（同上格式）

#### 4. J/P 维度
（同上格式）

### 人格画像

[综合描述用户的人格特点，300字左右]

### 成长建议

[基于MBTI类型的发展建议，200字左右]

---

请开始分析：
"""
    return prompt


def main():
    parser = argparse.ArgumentParser(description='MBTI分析')
    parser.add_argument('--data', default=os.path.expanduser('~/.hermes/qzone/data/'),
                       help='数据目录')
    parser.add_argument('--output', default=os.path.expanduser('~/.hermes/qzone/analysis/'),
                       help='输出目录')
    args = parser.parse_args()
    
    # 加载数据
    print("加载数据...")
    emotions_data = load_emotions(args.data)
    profile_data = load_profile(args.data)
    
    # 生成prompt
    print("生成分析prompt...")
    prompt = generate_mbti_prompt(emotions_data, profile_data)
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    # 保存prompt
    prompt_file = os.path.join(args.output, 'mbti_prompt.txt')
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"\n分析prompt已生成: {prompt_file}")
    print(f"包含 {emotions_data.get('total', 0)} 条说说")
    print(f"\n请将prompt发送给LLM进行分析，或使用以下命令：")
    print(f"  hermes chat < {prompt_file}")


if __name__ == '__main__':
    main()
