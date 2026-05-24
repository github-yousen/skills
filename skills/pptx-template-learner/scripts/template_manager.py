#!/usr/bin/env python3
"""PPT模板库管理工具

支持：列出主题、查看规范、归档PPT、删除主题、更新规范

Usage:
    python template_manager.py list
    python template_manager.py show "工作汇报"
    python template_manager.py add <pptx_file> --theme "工作汇报"
    python template_manager.py remove "工作汇报"
    python template_manager.py update "工作汇报"
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# 模板库根目录
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def list_themes():
    """列出所有模板主题"""
    if not TEMPLATES_DIR.exists():
        print("模板库为空，尚无主题")
        return

    themes = sorted([d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()])
    if not themes:
        print("模板库为空，尚无主题")
        return

    print(f"📋 模板库（共{len(themes)}个主题）：")
    print("-" * 60)
    for theme in themes:
        theme_dir = TEMPLATES_DIR / theme
        source_dir = theme_dir / "source"
        spec_file = theme_dir / "spec.json"

        pptx_count = len(list(source_dir.glob("*.pptx"))) if source_dir.exists() else 0
        has_spec = spec_file.exists()

        # 读取spec摘要
        spec_info = ""
        if has_spec:
            try:
                spec = json.loads(spec_file.read_text(encoding="utf-8"))
                slide_count = spec.get("meta", {}).get("slide_count_range", ["?", "?"])
                primary_color = spec.get("colors", {}).get("primary", "?")
                spec_info = f" | 主色={primary_color} | 页数={slide_count[0]}"
            except Exception:
                spec_info = " | spec解析失败"

        print(f"  📁 {theme}")
        print(f"     PPT文件: {pptx_count}个 | 规范: {'✅' if has_spec else '❌'}{spec_info}")
    print()


def show_theme(theme_name: str):
    """显示某主题的规范详情"""
    theme_dir = TEMPLATES_DIR / theme_name
    if not theme_dir.exists():
        print(f"❌ 主题 '{theme_name}' 不存在")
        return

    spec_file = theme_dir / "spec.json"
    if not spec_file.exists():
        print(f"⚠️ 主题 '{theme_name}' 尚无规范文件，请先运行 update")
        return

    spec = json.loads(spec_file.read_text(encoding="utf-8"))

    print(f"🎨 主题：{theme_name}")
    print("=" * 60)

    # 配色
    colors = spec.get("colors", {})
    print(f"\n📐 配色方案：")
    for name, val in colors.items():
        print(f"  {name:12s} = {val}")

    # 字体
    fonts = spec.get("fonts", {})
    print(f"\n🔤 字体体系：")
    for role, info in fonts.items():
        bold_str = "粗体" if info.get("bold") else "常规"
        print(f"  {role:12s} = {info.get('name', '?')} {info.get('size', '?')}pt {bold_str}")

    # 幻灯片类型
    slide_types = spec.get("slide_types", [])
    print(f"\n📊 幻灯片类型（共{len(slide_types)}页）：")
    for st in slide_types:
        role = st.get("role", "?")
        idx = st.get("index", "?")
        text_preview = st.get("text_preview", [])
        preview = " | ".join(text_preview[:2]) if text_preview else "（无文本）"
        bg = st.get("bg_color", "默认")
        print(f"  第{idx}页 [{role:8s}] 背景={bg} | {preview}")

    # 目录结构
    toc = spec.get("toc_structure", {})
    if toc.get("has_toc"):
        print(f"\n📑 目录结构：")
        print(f"  目录位置：第{toc.get('toc_slide_position', '?')}页")
        sections = toc.get("sections", [])
        if sections:
            for i, sec in enumerate(sections, 1):
                print(f"  {i}. {sec}")

    # 动画
    anims = spec.get("animations", {})
    print(f"\n🎬 动画/转场：")
    print(f"  默认转场：{anims.get('default_transition', 'none')}")
    elem_anims = anims.get("element_animations", [])
    if elem_anims:
        for anim in elem_anims:
            print(f"  元素动画：{anim.get('type', '?')} (频率={anim.get('frequency', '?')})")
    else:
        print(f"  元素动画：无")

    # 来源
    sources = spec.get("meta", {}).get("source_files", [])
    print(f"\n📦 来源文件：{', '.join(sources)}")


def add_pptx(pptx_path: str, theme_name: str):
    """将PPT归档到模板库"""
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        print(f"❌ 文件不存在: {pptx_path}")
        return

    theme_dir = TEMPLATES_DIR / theme_name
    source_dir = theme_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    # 复制PPT文件
    dest = source_dir / pptx_path.name
    if dest.exists():
        print(f"⚠️ 文件已存在: {dest}，将覆盖")
    shutil.copy2(pptx_path, dest)

    # 分析并生成/更新规范
    print(f"🔍 正在分析 {pptx_path.name} ...")
    try:
        from analyze_pptx import analyze_pptx
        new_spec = analyze_pptx(str(pptx_path), theme_name)
    except ImportError:
        # 直接导入
        sys.path.insert(0, str(Path(__file__).parent))
        from analyze_pptx import analyze_pptx
        new_spec = analyze_pptx(str(pptx_path), theme_name)

    spec_file = theme_dir / "spec.json"
    if spec_file.exists():
        # 合并规范
        existing_spec = json.loads(spec_file.read_text(encoding="utf-8"))
        merged = _merge_specs(existing_spec, new_spec)
        spec_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已归档到主题 '{theme_name}'，规范已合并")
    else:
        spec_file.write_text(json.dumps(new_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已归档到主题 '{theme_name}'，新建规范")

    # 添加来源文件记录
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    source_files = spec.get("meta", {}).get("source_files", [])
    if pptx_path.name not in source_files:
        source_files.append(pptx_path.name)
        spec["meta"]["source_files"] = source_files
        spec_file.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"📁 位置: {theme_dir}")


def remove_theme(theme_name: str):
    """删除主题"""
    theme_dir = TEMPLATES_DIR / theme_name
    if not theme_dir.exists():
        print(f"❌ 主题 '{theme_name}' 不存在")
        return

    shutil.rmtree(theme_dir)
    print(f"🗑️ 已删除主题 '{theme_name}'")


def update_theme(theme_name: str):
    """重新分析主题下所有PPT，更新规范"""
    theme_dir = TEMPLATES_DIR / theme_name
    if not theme_dir.exists():
        print(f"❌ 主题 '{theme_name}' 不存在")
        return

    source_dir = theme_dir / "source"
    if not source_dir.exists():
        print(f"⚠️ 主题 '{theme_name}' 无source目录")
        return

    pptx_files = list(source_dir.glob("*.pptx"))
    if not pptx_files:
        print(f"⚠️ 主题 '{theme_name}' 无PPT文件")
        return

    sys.path.insert(0, str(Path(__file__).parent))
    from analyze_pptx import analyze_pptx

    specs = []
    for pf in pptx_files:
        print(f"🔍 分析 {pf.name} ...")
        spec = analyze_pptx(str(pf), theme_name)
        specs.append(spec)

    # 合并所有规范
    if len(specs) == 1:
        merged = specs[0]
    else:
        merged = specs[0]
        for s in specs[1:]:
            merged = _merge_specs(merged, s)

    merged["meta"]["source_files"] = [pf.name for pf in pptx_files]
    spec_file = theme_dir / "spec.json"
    spec_file.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 主题 '{theme_name}' 规范已更新（{len(pptx_files)}个源文件）")


def _merge_specs(existing: dict, new: dict) -> dict:
    """合并两个spec，取众数/交集"""
    merged = existing.copy()

    # 配色取众数
    for color_key in ["primary", "secondary", "accent", "bg_dark", "bg_light", "text_dark", "text_light"]:
        new_val = new.get("colors", {}).get(color_key)
        if new_val:
            # 如果不同，保留existing（先入为主）
            pass

    # 字体取众数
    for font_key in ["title", "subtitle", "body"]:
        new_font = new.get("fonts", {}).get(font_key)
        if new_font:
            existing_font = merged.get("fonts", {}).get(font_key, {})
            # 如果字号接近则保留，差异大则取平均
            new_size = new_font.get("size", 0)
            old_size = existing_font.get("size", 0)
            if old_size and abs(new_size - old_size) <= 4:
                pass  # 保持原值
            elif new_size > old_size:
                existing_font["size"] = new_size

    # 页数范围扩展
    old_range = merged.get("meta", {}).get("slide_count_range", [0, 0])
    new_range = new.get("meta", {}).get("slide_count_range", [0, 0])
    merged["meta"]["slide_count_range"] = [
        min(old_range[0], new_range[0]),
        max(old_range[1], new_range[1]),
    ]

    # slide_types 取较多的那个
    if len(new.get("slide_types", [])) > len(merged.get("slide_types", [])):
        merged["slide_types"] = new["slide_types"]

    # 动画合并
    existing_anims = merged.get("animations", {}).get("element_animations", [])
    new_anims = new.get("animations", {}).get("element_animations", [])
    merged["animations"]["element_animations"] = existing_anims + [
        a for a in new_anims if a not in existing_anims
    ]

    return merged


def main():
    parser = argparse.ArgumentParser(description="PPT模板库管理工具")
    subparsers = parser.add_subparsers(dest="command", help="操作命令")

    # list
    subparsers.add_parser("list", help="列出所有模板主题")

    # show
    show_parser = subparsers.add_parser("show", help="查看主题规范详情")
    show_parser.add_argument("theme", help="主题名称")

    # add
    add_parser = subparsers.add_parser("add", help="归档PPT到模板库")
    add_parser.add_argument("pptx_file", help="PPT文件路径")
    add_parser.add_argument("--theme", required=True, help="主题名称")

    # remove
    remove_parser = subparsers.add_parser("remove", help="删除主题")
    remove_parser.add_argument("theme", help="主题名称")

    # update
    update_parser = subparsers.add_parser("update", help="更新主题规范")
    update_parser.add_argument("theme", help="主题名称")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list":
        list_themes()
    elif args.command == "show":
        show_theme(args.theme)
    elif args.command == "add":
        add_pptx(args.pptx_file, args.theme)
    elif args.command == "remove":
        remove_theme(args.theme)
    elif args.command == "update":
        update_theme(args.theme)


if __name__ == "__main__":
    main()
