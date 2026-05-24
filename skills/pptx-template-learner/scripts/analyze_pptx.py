#!/usr/bin/env python3
"""从PPTX文件中提取完整设计规范，输出spec.json

分析维度：配色、字体、布局、动画、转场、目录结构、幻灯片类型

Usage:
    python analyze_pptx.py <input.pptx> <output_spec.json> [--theme "主题名"]

Examples:
    python analyze_pptx.py template.pptx spec.json --theme "工作汇报"
    python analyze_pptx.py demo.pptx spec.json
"""

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import defusedxml.minidom

# OOXML 命名空间
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def analyze_pptx(pptx_path: str, theme_name: str = None) -> dict:
    """主分析函数，从PPTX提取完整规范"""
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        raise FileNotFoundError(f"文件不存在: {pptx_path}")

    with zipfile.ZipFile(pptx_path, "r") as zf:
        names = zf.namelist()

        # 1. 幻灯片尺寸
        slide_size = _extract_slide_size(zf)

        # 2. 配色方案
        colors = _extract_colors(zf)

        # 3. 字体体系
        fonts = _extract_fonts(zf)

        # 4. 转场效果
        transitions = _extract_transitions(zf)

        # 5. 动画效果
        animations = _extract_animations(zf)

        # 6. 幻灯片布局分析
        slide_types, toc_structure = _extract_slide_structure(zf)

    spec = {
        "theme": theme_name or pptx_path.stem,
        "mode": "strict",
        "meta": {
            "analyzed_at": datetime.now().isoformat(),
            "source_files": [pptx_path.name],
            "slide_count_range": [len(slide_types), len(slide_types)],
        },
        "slide_size": slide_size,
        "colors": colors,
        "fonts": fonts,
        "layout": {
            "margins": {"top": 0.5, "right": 0.5, "bottom": 0.5, "left": 0.5}
        },
        "toc_structure": toc_structure,
        "slide_types": slide_types,
        "animations": {
            "default_transition": transitions.get("default", "none"),
            "transition_duration_ms": transitions.get("duration_ms", 700),
            "element_animations": animations,
        },
    }

    return spec


def _extract_slide_size(zf: zipfile.ZipFile) -> dict:
    """提取幻灯片尺寸"""
    try:
        pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
        dom = defusedxml.minidom.parseString(pres_xml)

        sldSz_nodes = dom.getElementsByTagName("p:sldSz")
        if sldSz_nodes:
            node = sldSz_nodes[0]
            cx = int(node.getAttribute("cx"))
            cy = int(node.getAttribute("cy"))
            # EMU to inches: 1 inch = 914400 EMU
            w_in = round(cx / 914400, 3)
            h_in = round(cy / 914400, 3)
            ratio = f"{w_in/h_in:.2f}" if h_in else "16:9"
            return {"w": w_in, "h": h_in, "ratio": ratio}
    except Exception:
        pass

    return {"w": 10, "h": 5.625, "ratio": "16:9"}


def _extract_colors(zf: zipfile.ZipFile) -> dict:
    """提取配色方案：优先从幻灯片实际设计提取，theme1.xml仅作兜底
    
    核心逻辑：
    1. 先从幻灯片背景提取真实背景色
    2. 再从文本颜色提取真实文字色
    3. 从形状填充提取主色/强调色
    4. theme1.xml的clrScheme仅作为兜底（Office默认主题不代表实际设计）
    """
    colors = {
        "primary": "1E2761",
        "secondary": "CADCFC",
        "accent": "0891B2",
        "bg_dark": "1E2761",
        "bg_light": "FFFFFF",
        "text_dark": "212121",
        "text_light": "FFFFFF",
    }

    # ===== 第1步：从幻灯片背景提取真实背景色（优先级最高）=====
    bg_colors = _extract_bg_colors(zf)
    if bg_colors:
        dark_bgs = [c for c in bg_colors if _is_dark_color(c)]
        light_bgs = [c for c in bg_colors if not _is_dark_color(c)]
        if dark_bgs:
            colors["bg_dark"] = Counter(dark_bgs).most_common(1)[0][0]
        if light_bgs:
            colors["bg_light"] = Counter(light_bgs).most_common(1)[0][0]

    # ===== 第2步：从文本颜色提取真实文字色 =====
    text_colors = _extract_text_colors(zf)
    if text_colors:
        dark_texts = [c for c in text_colors if _is_dark_color(c)]
        light_texts = [c for c in text_colors if not _is_dark_color(c)]
        if dark_texts:
            colors["text_dark"] = Counter(dark_texts).most_common(1)[0][0]
        if light_texts:
            colors["text_light"] = Counter(light_texts).most_common(1)[0][0]

    # ===== 第3步：从形状填充提取主色/强调色 =====
    shape_colors = _extract_shape_fill_colors(zf)
    
    def _saturation(hex_c):
        """计算颜色饱和度（0-1），灰色接近0，鲜艳色接近1"""
        r, g, b = int(hex_c[:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
        mx, mn = max(r, g, b), min(r, g, b)
        return 0 if mx == 0 else (mx - mn) / mx
    
    if shape_colors:
        # 只排除纯通用色（纯白/纯黑/纯深灰），不排除bg_light/bg_dark
        # 因为彩色背景可能就是主题主色（如00D4FF既是章节背景色也是主色）
        exclude = {"FFFFFF", "000000"}
        # 排除低饱和度灰色（饱和度<0.15的中间灰不算主题色）
        candidates = [(c, cnt) for c, cnt in Counter(shape_colors).most_common(15)
                      if c not in exclude and _saturation(c) >= 0.15]
        if candidates:
            colors["primary"] = candidates[0][0]
        if len(candidates) > 1:
            colors["accent"] = candidates[1][0]
        if len(candidates) > 2:
            colors["secondary"] = candidates[2][0]
    
    # 如果形状填充色没提取到候选者，从文本颜色中找非通用色作为主色
    if colors["primary"] == "1E2761" and text_colors:
        text_counter = Counter(text_colors)
        exclude = {"FFFFFF", "000000", "333333", "666666", "999999"}
        text_candidates = [(c, cnt) for c, cnt in text_counter.most_common(10)
                          if c not in exclude and _saturation(c) >= 0.15]
        if text_candidates:
            colors["primary"] = text_candidates[0][0]
            if len(text_candidates) > 1:
                colors["accent"] = text_candidates[1][0]

    # ===== 第4步：theme1.xml 仅作兜底补充（只填充仍为默认值的字段）=====
    theme_path = "ppt/theme/theme1.xml"
    if theme_path in [n for n in zf.namelist()]:
        try:
            theme_xml = zf.read(theme_path).decode("utf-8")
            dom = defusedxml.minidom.parseString(theme_xml)

            clr_schemes = dom.getElementsByTagName("a:clrScheme")
            if not clr_schemes:
                clr_schemes = dom.getElementsByTagName("clrScheme")

            if clr_schemes:
                scheme = clr_schemes[0]
                theme_color_map = {}
                for child in scheme.childNodes:
                    if child.nodeType != child.ELEMENT_NODE:
                        continue
                    tag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
                    for sub in child.childNodes:
                        if sub.nodeType != sub.ELEMENT_NODE:
                            continue
                        sub_tag = sub.tagName.split(":")[-1] if ":" in sub.tagName else sub.tagName
                        if sub_tag == "srgbClr":
                            val = sub.getAttribute("val")
                            if val:
                                theme_color_map[tag] = val
                        elif sub_tag == "sysClr":
                            val = sub.getAttribute("lastClr")
                            if val:
                                theme_color_map[tag] = val

                # 仅对仍为默认值的字段做兜底
                default_vals = {"primary": "1E2761", "secondary": "CADCFC", "accent": "0891B2",
                                "bg_dark": "1E2761", "bg_light": "FFFFFF", "text_dark": "212121", "text_light": "FFFFFF"}
                mapping = {"dk2": "primary", "lt2": "secondary", "accent1": "accent",
                           "dk1": "bg_dark", "lt1": "bg_light"}
                for src, dst in mapping.items():
                    if src in theme_color_map and colors[dst] == default_vals[dst]:
                        colors[dst] = theme_color_map[src]

        except Exception as e:
            print(f"Warning: theme提取失败: {e}", file=sys.stderr)

    return colors


def _extract_bg_colors(zf: zipfile.ZipFile) -> list:
    """从幻灯片背景提取颜色"""
    colors = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 查找 bgPr/bgRef
            for tag in ["p:bg", "bg"]:
                bgs = dom.getElementsByTagName(tag)
                for bg in bgs:
                    for sub_tag in ["a:solidFill", "solidFill"]:
                        fills = bg.getElementsByTagName(sub_tag)
                        for fill in fills:
                            for clr_tag in ["a:srgbClr", "srgbClr"]:
                                clrs = fill.getElementsByTagName(clr_tag)
                                for clr in clrs:
                                    val = clr.getAttribute("val")
                                    if val and len(val) == 6:
                                        colors.append(val.upper())
        except Exception:
            continue

    return colors


def _extract_text_colors(zf: zipfile.ZipFile) -> list:
    """从文本运行中提取颜色"""
    colors = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files[:5]:  # 只检查前5页避免太慢
        try:
            xml = zf.read(sf).decode("utf-8")
            # 用正则提取 srgbClr val（比DOM快）
            matches = re.findall(r'<a:srgbClr\s+val="([A-Fa-f0-9]{6})"', xml)
            colors.extend([m.upper() for m in matches])
        except Exception:
            continue

    return colors


def _extract_shape_fill_colors(zf: zipfile.ZipFile) -> list:
    """从形状填充中提取颜色（用于识别主色和强调色）
    
    注意：python-pptx生成的形状用<p:spPr>而非<a:spPr>，需兼容两种标签
    """
    colors = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            # 使用正则提取所有形状填充色（兼容 a:spPr 和 p:spPr）
            fills = re.findall(
                r'<(?:a|p):spPr>.*?<a:solidFill>\s*<a:srgbClr\s+val="([A-Fa-f0-9]{6})"',
                xml, re.DOTALL
            )
            colors.extend([f.upper() for f in fills])
        except Exception:
            continue

    return colors


def _is_dark_color(hex_color: str) -> bool:
    """判断颜色是否偏暗"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5
    except Exception:
        return False


def _extract_fonts(zf: zipfile.ZipFile) -> dict:
    """提取字体体系：统计频率最高的字体组合"""
    font_counter = Counter()  # (fontname, size, bold) -> count
    size_counter = Counter()  # fontsize -> count

    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            # 提取 <a:rPr> 中的字体信息
            # Latin字体
            latin_fonts = re.findall(r'<a:latin\s+typeface="([^"]+)"', xml)
            # East Asian字体
            ea_fonts = re.findall(r'<a:ea\s+typeface="([^"]+)"', xml)
            # 字号 (sz单位是1/100磅)
            sizes = re.findall(r'<a:rPr[^>]*sz="(\d+)"', xml)
            # 粗体
            bolds = re.findall(r'<a:rPr[^>]*b="1"', xml)

            for font in latin_fonts + ea_fonts:
                font_counter[font] += 1

            for sz in sizes:
                size_counter[int(sz)] += 1

        except Exception:
            continue

    # 按频率取top字体
    top_fonts = [f for f, _ in font_counter.most_common(10)]
    top_sizes = sorted(size_counter.keys(), reverse=True)

    # 分类：标题/副标题/正文
    result = {
        "title": {"name": "Arial", "size": 36, "bold": True},
        "subtitle": {"name": "Arial", "size": 20, "bold": False},
        "body": {"name": "Calibri", "size": 14, "bold": False},
    }

    if top_fonts:
        # 第一个高频字体作为标题和正文
        result["title"]["name"] = top_fonts[0]
        result["subtitle"]["name"] = top_fonts[0] if len(top_fonts) == 1 else top_fonts[min(1, len(top_fonts) - 1)]
        result["body"]["name"] = top_fonts[min(1, len(top_fonts) - 1)]

    if top_sizes:
        # 最大的字号作为标题，最小的作为正文
        result["title"]["size"] = max(round(top_sizes[0] / 100), 24)
        result["body"]["size"] = max(round(top_sizes[-1] / 100), 10)
        if len(top_sizes) > 1:
            result["subtitle"]["size"] = max(round(top_sizes[len(top_sizes) // 2] / 100), 14)

    return result


def _extract_transitions(zf: zipfile.ZipFile) -> dict:
    """提取转场效果"""
    transitions = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(slide_pattern.pattern)])

    # 重新获取slide文件列表
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            for tag in ["p:transition", "transition"]:
                nodes = dom.getElementsByTagName(tag)
                for node in nodes:
                    trans_type = "unknown"
                    duration = None

                    for child in node.childNodes:
                        if child.nodeType != child.ELEMENT_NODE:
                            continue
                        ctag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
                        trans_type = ctag  # fade, push, wipe, etc.

                    advTm = node.getAttribute("advTm")
                    spd = node.getAttribute("spd")

                    transitions.append({
                        "type": trans_type,
                        "speed": spd or "med",
                    })
        except Exception:
            continue

    if not transitions:
        return {"default": "none", "duration_ms": 700}

    # 取众数作为默认转场
    type_counter = Counter(t["type"] for t in transitions)
    default = type_counter.most_common(1)[0][0]

    return {"default": default, "duration_ms": 700}


def _extract_animations(zf: zipfile.ZipFile) -> list:
    """提取动画效果"""
    animations = []
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    anim_types = Counter()

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")

            # 检查是否有 timing 节点
            if "<p:timing>" not in xml and "<timing>" not in xml:
                continue

            # 提取 animEffect 类型（如 fade, wipe 等）
            effects = re.findall(r'<p:animEffect[^>]*transition="([^"]*)"', xml)
            for eff in effects:
                anim_types[f"effect:{eff}"] += 1

            # 提取 animMotion（路径动画）
            motions = re.findall(r'<p:animMotion[^>]*>', xml)
            if motions:
                anim_types["motion_path"] += len(motions)

            # 提取 presetID 对应的动画类型（出现、消失、强调等）
            # presetClass: entr(进入), exit(退出), emph(强调), motion(路径)
            preset_map = {"entr": "enter", "exit": "exit", "emph": "emphasize", "motion": "motion_path"}
            presets = re.findall(r'presetClass="(\w+)"', xml)
            for p in presets:
                if p in preset_map:
                    anim_types[preset_map[p]] += 1

            # 提取 <p:set> 动画（出现/隐藏动画最常见的形式）
            set_count = xml.count("<p:set>")
            if set_count > 0:
                anim_types["appear/disappear"] += set_count

            # 提取 <p:anim> 数值动画（缩放、旋转、透明度等）
            anim_count = xml.count("<p:anim")
            if anim_count > 0:
                anim_types["value_animation"] += anim_count

        except Exception:
            continue

    # 汇总动画模式
    for anim_type, count in anim_types.most_common(5):
        animations.append({
            "type": anim_type,
            "applies_to": "elements",
            "frequency": count,
        })

    return animations


def _extract_slide_structure(zf: zipfile.ZipFile) -> tuple:
    """提取幻灯片类型和目录结构"""
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    slide_types = []
    toc_structure = {"has_toc": False, "toc_slide_position": None, "sections": []}
    sections = []

    for idx, sf in enumerate(slide_files):
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 提取文本内容
            texts = []
            for t_node in dom.getElementsByTagName("a:t"):
                if t_node.firstChild and t_node.firstChild.nodeValue:
                    texts.append(t_node.firstChild.nodeValue.strip())

            # 提取元素位置信息
            elements = _extract_elements_positions(dom)

            # 提取背景色
            bg_color = None
            for tag in ["p:bg", "bg"]:
                bgs = dom.getElementsByTagName(tag)
                for bg in bgs:
                    for fill_tag in ["a:solidFill", "solidFill"]:
                        fills = bg.getElementsByTagName(fill_tag)
                        for fill in fills:
                            for clr_tag in ["a:srgbClr", "srgbClr"]:
                                clrs = fill.getElementsByTagName(clr_tag)
                                for clr in clrs:
                                    val = clr.getAttribute("val")
                                    if val:
                                        bg_color = val.upper()

            # 判断幻灯片类型
            role = _classify_slide(idx, len(slide_files), texts, bg_color, elements)

            slide_info = {
                "role": role,
                "index": idx + 1,
                "text_preview": texts[:5] if texts else [],
                "element_count": len(elements),
                "bg_color": bg_color,
                "elements": elements[:10] if elements else [],  # 最多保存10个元素
            }

            # 检测目录页
            if role == "toc":
                toc_structure["has_toc"] = True
                toc_structure["toc_slide_position"] = idx + 1
                # 尝试从文本提取章节名
                for t in texts:
                    if len(t) > 1 and len(t) < 30:
                        sections.append(t)

            # 检测章节页
            if role == "section" and texts:
                section_name = texts[0] if texts else f"章节{idx+1}"
                if section_name not in sections and len(section_name) < 30:
                    sections.append(section_name)

            slide_types.append(slide_info)

        except Exception as e:
            slide_types.append({
                "role": "content",
                "index": idx + 1,
                "text_preview": [],
                "element_count": 0,
                "elements": [],
            })

    toc_structure["sections"] = sections[:10]  # 最多10个章节
    return slide_types, toc_structure


def _extract_elements_positions(dom) -> list:
    """从spTree中提取元素位置信息"""
    elements = []
    sp_trees = dom.getElementsByTagName("p:spTree")
    if not sp_trees:
        return elements

    sp_tree = sp_trees[0]

    for sp in sp_tree.childNodes:
        if sp.nodeType != sp.ELEMENT_NODE:
            continue

        tag = sp.tagName.split(":")[-1] if ":" in sp.tagName else sp.tagName
        if tag not in ("sp", "pic", "graphicFrame", "cxnSp", "grpSp"):
            continue

        elem = {"type": tag}

        # 位置信息
        xfrm_nodes = sp.getElementsByTagName("a:xfrm")
        if xfrm_nodes:
            xfrm = xfrm_nodes[0]
            off = xfrm.getElementsByTagName("a:off")
            ext = xfrm.getElementsByTagName("a:ext")
            if off:
                elem["x"] = round(int(off[0].getAttribute("x")) / 914400, 2)
                elem["y"] = round(int(off[0].getAttribute("y")) / 914400, 2)
            if ext:
                elem["w"] = round(int(ext[0].getAttribute("cx")) / 914400, 2)
                elem["h"] = round(int(ext[0].getAttribute("cy")) / 914400, 2)

        # 文本内容
        t_nodes = sp.getElementsByTagName("a:t")
        if t_nodes and t_nodes[0].firstChild:
            text = t_nodes[0].firstChild.nodeValue
            if text and len(text.strip()) > 0:
                elem["text"] = text.strip()[:50]

        elements.append(elem)

    return elements


def _classify_slide(idx: int, total: int, texts: list, bg_color: str, elements: list) -> str:
    """分类幻灯片类型"""
    # 封面：第一页
    if idx == 0:
        return "cover"

    # 结尾：最后一页
    if idx == total - 1:
        ending_keywords = ["谢谢", "感谢", "thank", "thanks", "Q&A", "问答", "结束", "THE END"]
        combined = " ".join(texts).lower()
        if any(kw.lower() in combined for kw in ending_keywords):
            return "ending"
        return "content"

    # 目录页检测
    toc_keywords = ["目录", "contents", "大纲", "outline", "议程", "agenda", "概览", "overview"]
    combined = " ".join(texts).lower()
    if any(kw.lower() in combined for kw in toc_keywords):
        return "toc"

    # 章节分隔页：少量文字 + 背景色与前后页明显不同（不限于暗色）
    if bg_color and len(texts) <= 3:
        # 暗背景+少量文字 → 章节
        if _is_dark_color(bg_color):
            return "section"
        # 亮色/强调色背景+少量文字+有正文标题感 → 也是章节（如暗色科技风的亮色章节页）
        if len(texts) >= 1 and len(texts[0]) <= 20:
            return "section"

    # 数据展示：有图表元素
    has_chart = any(e.get("type") == "graphicFrame" for e in elements)
    if has_chart:
        return "data"

    # 默认：内容页
    return "content"


def main():
    parser = argparse.ArgumentParser(description="从PPTX提取设计规范")
    parser.add_argument("input", help="输入PPTX文件路径")
    parser.add_argument("output", help="输出spec.json路径")
    parser.add_argument("--theme", help="主题名称", default=None)
    args = parser.parse_args()

    spec = analyze_pptx(args.input, args.theme)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出摘要
    print(f"✅ 分析完成: {args.input}")
    print(f"   主题: {spec['theme']}")
    print(f"   页数: {spec['meta']['slide_count_range'][0]}")
    print(f"   配色: 主色={spec['colors']['primary']}, 辅色={spec['colors']['secondary']}, 强调色={spec['colors']['accent']}")
    print(f"   字体: 标题={spec['fonts']['title']['name']} {spec['fonts']['title']['size']}pt, 正文={spec['fonts']['body']['name']} {spec['fonts']['body']['size']}pt")
    print(f"   目录: {'有' if spec['toc_structure']['has_toc'] else '无'}")
    print(f"   转场: {spec['animations']['default_transition']}")
    print(f"   动画: {len(spec['animations']['element_animations'])}种")
    print(f"   输出: {args.output}")


if __name__ == "__main__":
    main()
