#!/usr/bin/env python3
"""
九型人格分析脚本
用法: python analyze_enneagram.py --data ~/.hermes/qzone/data/ --output ~/.hermes/qzone/analysis/

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
        
        formatted.append(f"[{i}] [{time_str}] {content}")
    
    return '\n'.join(formatted)


def generate_enneagram_prompt(emotions_data, profile_data):
    """生成九型人格分析prompt"""
    qq = emotions_data.get('qq', '未知')
    total = emotions_data.get('total', 0)
    
    # 格式化说说
    emotions_text = format_emotions_for_analysis(emotions_data)
    
    prompt = f"""你是一位专业的九型人格(Enneagram)分析师。请根据以下QQ空间说说内容，对用户进行详细的九型人格分析。

## 用户信息
- QQ号: {qq}
- 说说总数: {total}

## 说说内容（按时间排列）

{emotions_text}

## 九型人格基础知识

九型人格将人分为9种基本类型：
1. **完美主义者** - 追求完美，有原则，自律
2. **助人者** - 乐于助人，关注他人需求
3. **成就者** - 追求成功，注重形象
4. **自我主义者** - 追求独特，情感丰富
5. **观察者** - 追求知识，独立思考
6. **忠诚者** - 追求安全，忠诚可靠
7. **享乐主义者** - 追求快乐，乐观开朗
8. **挑战者** - 追求力量，直接果断
9. **和平缔造者** - 追求和谐，随和包容

每个类型还有翼型（相邻类型的影响）和健康层级之分。

## 分析要求

请从以下方面进行分析，每个方面需要引用具体的说说内容作为证据：

### 1. 主型判定
- 分析用户的核心动机和恐惧
- 确定最可能的主型
- 引用相关说说作为证据

### 2. 翼型分析
- 分析相邻类型的影响
- 确定翼型（如4w3或4w5）

### 3. 三元组分析
- **情感三元组**（2,3,4）：关注形象和认可
- **行动三元组**（5,6,7）：关注安全和计划
- **本能三元组**（8,9,1）：关注控制和愤怒

### 4. 健康层级
- 分析用户处于健康、一般还是不健康状态

### 5. 发展方向
- 整合方向（向健康方向发展）
- 解离方向（压力下的退化方向）

## 输出格式

请严格按照以下格式输出：

### 九型人格判定

**主型: [X号] - [类型名称]**
**翼型: [XwY]**
**三元组: [所属三元组]**

### 主型分析

#### 核心动机
[用户的核心追求]

#### 核心恐惧
[用户最害怕的事情]

#### 分析
[详细分析]

#### 证据
- "[引用说说1]"
- "[引用说说2]"
- "[引用说说3]"

### 翼型分析

[翼型的详细分析和证据]

### 三元组分析

[所属三元组的特点和表现]

### 健康层级

**当前状态: [健康/一般/不健康]**

[详细分析]

### 发展方向

#### 整合方向
[向健康方向发展的建议]

#### 解离方向
[压力下需要注意的问题]

### 人格画像

[综合描述用户的人格特点，300字左右]

### 成长建议

[基于九型人格的发展建议，200字左右]

---

请开始分析：
"""
    return prompt


def main():
    parser = argparse.ArgumentParser(description='九型人格分析')
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
    prompt = generate_enneagram_prompt(emotions_data, profile_data)
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    # 保存prompt
    prompt_file = os.path.join(args.output, 'enneagram_prompt.txt')
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"\n分析prompt已生成: {prompt_file}")
    print(f"包含 {emotions_data.get('total', 0)} 条说说")
    print(f"\n请将prompt发送给LLM进行分析，或使用以下命令：")
    print(f"  hermes chat < {prompt_file}")


if __name__ == '__main__':
    main()
