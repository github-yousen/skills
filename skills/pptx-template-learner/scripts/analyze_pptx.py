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
    """提取配色方案：优先从幻灯片实际内容(背景/形状/文本)推断，theme1.xml仅兜底"""
    colors = {
        "primary": "1E2761",
        "secondary": "CADCFC",
        "accent": "0891B2",
        "bg_dark": "1E2761",
        "bg_light": "FFFFFF",
        "text_dark": "212121",
        "text_light": "FFFFFF",
    }

    # 获取幻灯片基准尺寸(EMU)
    slide_w, slide_h = _get_slide_size_emu(zf)

    # Step 1: 提取背景色(包括覆盖全页的形状)
    bg_data = _extract_bg_colors_with_shapes(zf, slide_w, slide_h)
    dark_bgs = [c for c, area in bg_data if _is_dark_color(c)]
    light_bgs = [c for c, area in bg_data if not _is_dark_color(c)]
    if dark_bgs:
        colors["bg_dark"] = Counter(dark_bgs).most_common(1)[0][0]
    if light_bgs:
        colors["bg_light"] = Counter(light_bgs).most_common(1)[0][0]
    # 补充: 如果没有深色背景但有浅色背景,最频繁的背景色作为bg_dark
    if not dark_bgs and bg_data:
        # 所有背景色中频率最高的作为bg_dark(即使是"浅色")
        bg_counter = Counter(c for c, area in bg_data)
        colors["bg_dark"] = bg_counter.most_common(1)[0][0]

    # 初始默认值集合(脚本初始化值,用于检测某字段是否仍为初始值未被填充)
    init_defaults = {"1E2761", "CADCFC", "0891B2", "212121", "FFFFFF"}
    # OOXML默认配色方案值(Office默认主题的accent色,这些几乎不可能是设计意图,用于过滤候选色)
    ooxml_defaults = {"1F497D", "EEECE1", "4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6", "F79646", "0000FF", "800080"}
    # 合并的默认值集合(用于兼容旧逻辑)
    hardcoded_defaults = init_defaults | ooxml_defaults

    # Step 2: 提取非背景形状填充色(按面积加权,排除全页背景)
    shape_data = _extract_shape_fill_data(zf, slide_w, slide_h)
    # 排除纯黑纯白和极浅背景色,但保留bg_dark(它可能就是主色调)
    exclude = set([colors["bg_light"].upper(), "FFFFFF", "000000"])
    # 允许少量灰度但排除明显中性灰
    candidates = []
    for col, area in shape_data:
        cu = col.upper()
        if cu not in exclude and not _is_neutral_gray(cu):
            candidates.append((cu, area))

    if candidates:
        # 按面积+饱和度综合加权
        # 让高饱和度颜色获得额外权重(主色调通常是饱和颜色)
        weighted = Counter()
        for col, area in candidates:
            sat = _color_saturation(col)
            lum = _color_luminance(col)
            # 高饱和度有加成,但极暗或极亮减少权重
            weight = max(1, int(area / (slide_w * slide_h) * 100))
            if sat > 0.3:
                weight = int(weight * 1.5)
            if lum < 0.1 or lum > 0.95:
                weight = max(1, int(weight * 0.3))  # 极暗/极亮降权
            # OOXML默认配色方案值降权(这些通常不是设计意图色)
            if col in hardcoded_defaults:
                weight = max(1, int(weight * 0.1))
            weighted[col] += weight
        sorted_colors = weighted.most_common()
        # 过滤掉权重过低的OOXML默认色
        sorted_colors = [(c, w) for c, w in sorted_colors if c not in hardcoded_defaults or w > 5]
        if sorted_colors:
            colors["primary"] = sorted_colors[0][0]
        if len(sorted_colors) > 1:
            colors["secondary"] = sorted_colors[1][0]
        if len(sorted_colors) > 2:
            colors["accent"] = sorted_colors[2][0]

    # Step 2.5: 从文本颜色/形状填充色补充配色(仅在Step2结果为默认值/中性灰时)
    # 先构建schemeClr→RGB映射表,用于解析主题色引用
    scheme_map = _build_scheme_color_map(zf)

    # 综合所有实际出现的颜色(文本+形状填充),按频率+饱和度加权
    all_color_data = Counter()
    for col, freq in _extract_text_color_data(zf, scheme_map):
        cu = col.upper()
        # 排除背景色、中性灰、OOXML默认accent色
        if cu not in exclude and not _is_neutral_gray(cu) and cu not in ooxml_defaults:
            sat = _color_saturation(cu)
            weight = freq
            if sat > 0.3:
                weight = int(weight * 1.5)
            all_color_data[cu] += weight

    # 也把shape_data中的候选色加入
    for col, area in candidates:
        cu = col.upper()
        if cu not in ooxml_defaults:
            weight = max(1, int(area / (slide_w * slide_h) * 100))
            if _color_saturation(cu) > 0.3:
                weight = int(weight * 1.5)
            all_color_data[cu] += weight

    # 用综合结果补充仍然为初始默认值的字段
    if all_color_data:
        all_sorted = all_color_data.most_common()
        # 分类为深色和浅色
        dark_candidates = [(c, w) for c, w in all_sorted if _is_dark_color(c)]
        light_candidates = [(c, w) for c, w in all_sorted if not _is_dark_color(c)]

        # primary: 仅当仍为初始默认值时补充
        if colors.get("primary", "") in init_defaults:
            if dark_candidates:
                colors["primary"] = dark_candidates[0][0]
            elif all_sorted:
                colors["primary"] = all_sorted[0][0]

        # secondary: 仅当仍为初始默认值或中性灰时补充
        sec = colors.get("secondary", "")
        if sec in init_defaults or sec in ooxml_defaults or _is_neutral_gray(sec):
            if light_candidates:
                colors["secondary"] = light_candidates[0][0]
            elif len(all_sorted) > 1:
                for c, w in all_sorted:
                    if c != colors["primary"]:
                        colors["secondary"] = c
                        break

        # accent: 仅当仍为初始默认值或中性灰时补充(优先选高饱和度色)
        acc = colors.get("accent", "")
        if acc in init_defaults or acc in ooxml_defaults or _is_neutral_gray(acc):
            sat_sorted = sorted(all_sorted, key=lambda x: _color_saturation(x[0]), reverse=True)
            for c, w in sat_sorted:
                if c != colors["primary"] and c != colors["secondary"]:
                    colors["accent"] = c
                    break

    # 兜底: 如果primary仍像初始默认值,尝试回退到bg_dark
    if colors.get("primary", "") in init_defaults:
        # 如果bg_dark足够饱和,用bg_dark做主色;否则保持当前
        bg = colors.get("bg_dark", "")
        if bg and _color_saturation(bg) > 0.15:
            colors["primary"] = bg

    # 深色主题优化: 如果bg_dark是有饱和度的深色(非纯黑/深灰),则primary=bg_dark
    # 多数深色PPT的视觉主色调就是深色背景本身
    bg_d = colors.get("bg_dark", "")
    if bg_d and _color_saturation(bg_d) > 0.15 and _is_dark_color(bg_d):
        current_primary = colors.get("primary", "")
        # 当前primary如果是浅色/亮色(如金色文字FFD700),它更像是accent而非primary
        if not _is_dark_color(current_primary) or current_primary in hardcoded_defaults:
            # 把当前primary降级为accent(如果它够饱和)
            if _color_saturation(current_primary) > 0.3:
                colors["accent"] = current_primary
            colors["primary"] = bg_d

    # Step 3: 从文本颜色补充text_dark / text_light
    text_colors = _extract_text_colors(zf)
    if text_colors:
        dark_texts = [c for c in text_colors if _is_dark_color(c)]
        light_texts = [c for c in text_colors if not _is_dark_color(c)]
        if dark_texts:
            colors["text_dark"] = Counter(dark_texts).most_common(1)[0][0]
        if light_texts:
            colors["text_light"] = Counter(light_texts).most_common(1)[0][0]

    # Step 4: theme1.xml 仅作最后兜底(仅补充仍为硬编码默认值的字段)
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
                color_map = {}
                for child in scheme.childNodes:
                    if child.nodeType != child.ELEMENT_NODE:
                        continue
                    tag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
                    for sub in child.childNodes:
                        if sub.nodeType != sub.ELEMENT_NODE:
                            continue
                        sub_tag = sub.tagName.split(":")[-1] if ":" in sub.tagName else sub.tagName
                        if sub_tag == "srgbClr":
                            v = sub.getAttribute("val")
                            if v: color_map[tag] = v.upper()
                        elif sub_tag == "sysClr":
                            v = sub.getAttribute("lastClr")
                            if v: color_map[tag] = v.upper()

                # 仅当目标字段仍为硬编码默认值时,才用theme1.xml覆盖
                # 注意: theme1.xml的dk1/lt1通常就是黑/白,不应覆盖已从幻灯片提取的bg_dark/bg_light
                mapping = {"dk2": "primary", "lt2": "secondary", "accent1": "accent",
                           "accent2": "accent", "accent3": "accent", "hlink": "accent"}
                for src, dst in mapping.items():
                    current = colors.get(dst, "")
                    if src in color_map and current in hardcoded_defaults:
                        theme_val = color_map[src]
                        # 排除theme1.xml也是默认OOXML配色的值(1F497D/EEECE1/C0504D等)
                        if theme_val not in hardcoded_defaults:
                            colors[dst] = theme_val

                # text_dark/text_light: 仅当未从实际内容提取到时,用dk1/lt1补充
                if colors.get("text_dark", "") in hardcoded_defaults and "dk1" in color_map:
                    colors["text_dark"] = color_map["dk1"]
                if colors.get("text_light", "") in hardcoded_defaults and "lt1" in color_map:
                    colors["text_light"] = color_map["lt1"]
        except Exception as e:
            print(f"Warning: theme提取失败: {e}", file=sys.stderr)

    return colors


def _get_slide_size_emu(zf: zipfile.ZipFile) -> tuple:
    """获取幻灯片的宽和高(EMU)"""
    try:
        pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
        dom = defusedxml.minidom.parseString(pres_xml)
        sldSz = dom.getElementsByTagName("p:sldSz")
        if sldSz:
            return int(sldSz[0].getAttribute("cx")), int(sldSz[0].getAttribute("cy"))
    except Exception:
        pass
    # 默认: 13.333 x 7.5 inches 16:9
    return 12192000, 6858000


def _extract_bg_colors_with_shapes(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> list:
    """提取背景色: 包括<p:bg>节点和覆盖全页的shape"""
    bg_data = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)
            # 真正的 p:bg 节点
            for tag in ["p:bg", "bg"]:
                for bg in dom.getElementsByTagName(tag):
                    for fill in bg.getElementsByTagName("a:solidFill"):
                        for clr in fill.getElementsByTagName("a:srgbClr"):
                            val = clr.getAttribute("val")
                            if val and len(val) == 6:
                                bg_data.append((val.upper(), slide_w * slide_h))

            # 覆盖全页的shape填充 -> 视为背景
            # 判定条件: 高度 >= slide_h*0.95, 且 x=y=0, 且宽度 >= slide_w*0.5
            # 或面积 >= slide面积的90%
            full_area = slide_w * slide_h
            for sp in dom.getElementsByTagName("p:sp"):
                xfrm = sp.getElementsByTagName("a:xfrm")
                if not xfrm:
                    continue
                off = xfrm[0].getElementsByTagName("a:off")
                ext = xfrm[0].getElementsByTagName("a:ext")
                if not off or not ext:
                    continue
                x = int(off[0].getAttribute("x") or 0)
                y = int(off[0].getAttribute("y") or 0)
                cx = int(ext[0].getAttribute("cx") or 0)
                cy = int(ext[0].getAttribute("cy") or 0)
                area = cx * cy
                # 判断是否为全页背景：x=y=0 且覆盖大部分面积
                is_full_page = (
                    x == 0 and y == 0
                    and cy >= slide_h * 0.95
                    and cx >= slide_w * 0.5
                )
                if is_full_page or area >= full_area * 0.90:
                    for spPr in sp.getElementsByTagName("p:spPr"):
                        for fill in spPr.getElementsByTagName("a:solidFill"):
                            for clr in fill.getElementsByTagName("a:srgbClr"):
                                val = clr.getAttribute("val")
                                if val and len(val) == 6:
                                    bg_data.append((val.upper(), area))

        except Exception:
            continue
    return bg_data


def _extract_shape_fill_data(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> list:
    """提取非背景形状的填充色及其面积"""
    data = []
    full_area = slide_w * slide_h
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)
            # 收集所有带srgbClr的solidFill位置,排除属于p:bg和全页背景的
            for sp in dom.getElementsByTagName("p:sp"):
                xfrm = sp.getElementsByTagName("a:xfrm")
                area = 0
                if xfrm:
                    ext = xfrm[0].getElementsByTagName("a:ext")
                    off = xfrm[0].getElementsByTagName("a:off")
                    if ext and off:
                        cx = int(ext[0].getAttribute("cx") or 0)
                        cy = int(ext[0].getAttribute("cy") or 0)
                        x = int(off[0].getAttribute("x") or 0)
                        y = int(off[0].getAttribute("y") or 0)
                        area = cx * cy

                for spPr in sp.getElementsByTagName("p:spPr"):
                    for fill in spPr.getElementsByTagName("a:solidFill"):
                        for clr in fill.getElementsByTagName("a:srgbClr"):
                            val = clr.getAttribute("val")
                            if val and len(val) == 6:
                                data.append((val.upper(), max(area, 1)))
        except Exception:
            continue
    return data


def _is_neutral_gray(hex_color: str) -> bool:
    """判断是否接近中性灰(饱和度极低，R≈G≈B)"""
    return _color_saturation(hex_color) < 0.12


def _build_scheme_color_map(zf: zipfile.ZipFile) -> dict:
    """从theme1.xml构建schemeClr名称到RGB颜色的映射表"""
    scheme_map = {}
    theme_path = "ppt/theme/theme1.xml"
    if theme_path not in zf.namelist():
        return scheme_map
    try:
        theme_xml = zf.read(theme_path).decode("utf-8")
        dom = defusedxml.minidom.parseString(theme_xml)
        schemes = dom.getElementsByTagName("a:clrScheme")
        if not schemes:
            schemes = dom.getElementsByTagName("clrScheme")
        if not schemes:
            return scheme_map
        scheme = schemes[0]
        for child in scheme.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            tag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
            for sub in child.childNodes:
                if sub.nodeType != sub.ELEMENT_NODE:
                    continue
                sub_tag = sub.tagName.split(":")[-1] if ":" in sub.tagName else sub.tagName
                if sub_tag == "srgbClr":
                    v = sub.getAttribute("val")
                    if v:
                        scheme_map[tag] = v.upper()
                elif sub_tag == "sysClr":
                    v = sub.getAttribute("lastClr")
                    if v:
                        scheme_map[tag] = v.upper()
    except Exception:
        pass
    return scheme_map


def _color_saturation(hex_color: str) -> float:
    """计算颜色饱和度(0~1)"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        maxc, minc = max(r, g, b), min(r, g, b)
        if maxc == 0:
            return 0.0
        return (maxc - minc) / maxc
    except Exception:
        return 0.0


def _color_luminance(hex_color: str) -> float:
    """计算颜色亮度(0~1)"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255
    except Exception:
        return 0.5


def _extract_text_color_data(zf: zipfile.ZipFile, scheme_map: dict = None) -> list:
    """从文本运行中提取颜色及其出现频率,返回 [(color, freq), ...]
    支持解析schemeClr引用(如accent1/lt1/dk1等)到实际RGB颜色"""
    color_counter = Counter()
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            # 提取 <a:solidFill> 内的 <a:srgbClr val="...">
            rpr_blocks = re.findall(r'<a:rPr[^>]*>(.*?)</a:rPr>', xml, re.DOTALL)
            for block in rpr_blocks:
                matches = re.findall(r'<a:srgbClr\s+val="([A-Fa-f0-9]{6})"', block)
                for m in matches:
                    color_counter[m.upper()] += 1
                # 也提取 schemeClr 引用
                if scheme_map:
                    scheme_refs = re.findall(r'<a:schemeClr\s+val="([^"]+)"', block)
                    for ref in scheme_refs:
                        rgb = scheme_map.get(ref)
                        if rgb:
                            color_counter[rgb] += 1

            # 也提取形状 spPr 中的 solidFill 颜色
            sp_blocks = re.findall(r'<p:sp>(.*?)</p:sp>', xml, re.DOTALL)
            for block in sp_blocks:
                fills = re.findall(r'<a:solidFill>\s*<a:srgbClr\s+val="([A-Fa-f0-9]{6})"', block)
                for m in fills:
                    color_counter[m.upper()] += 1
                # schemeClr 引用
                if scheme_map:
                    scheme_fills = re.findall(r'<a:solidFill[^>]*>.*?<a:schemeClr\s+val="([^"]+)"', block, re.DOTALL)
                    for ref in scheme_fills:
                        rgb = scheme_map.get(ref)
                        if rgb:
                            color_counter[rgb] += 1

            # 全局 schemeClr 提取(spTree中的所有非rPr场景)
            if scheme_map:
                # 提取 <a:solidFill> 内的 schemeClr (不限于rPr)
                all_scheme = re.findall(r'<a:solidFill[^>]*>.*?<a:schemeClr\s+val="([^"]+)"', xml, re.DOTALL)
                for ref in all_scheme:
                    rgb = scheme_map.get(ref)
                    if rgb:
                        color_counter[rgb] += 1
        except Exception:
            continue

    return color_counter.most_common(30)


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


def _is_dark_color(hex_color: str) -> bool:
    """判断颜色是否偏暗"""
    return _color_luminance(hex_color) < 0.5


def _color_luminance(hex_color: str) -> float:
    """计算颜色亮度(0-1)"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255
    except Exception:
        return 0.5


def _build_scheme_color_map(zf: zipfile.ZipFile) -> dict:
    """从theme1.xml构建schemeClr名称到RGB颜色的映射表"""
    scheme_map = {}
    theme_path = "ppt/theme/theme1.xml"
    if theme_path not in zf.namelist():
        return scheme_map
    try:
        theme_xml = zf.read(theme_path).decode("utf-8")
        dom = defusedxml.minidom.parseString(theme_xml)
        schemes = dom.getElementsByTagName("a:clrScheme")
        if not schemes:
            schemes = dom.getElementsByTagName("clrScheme")
        if not schemes:
            return scheme_map
        scheme = schemes[0]
        for child in scheme.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            tag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
            for sub in child.childNodes:
                if sub.nodeType != sub.ELEMENT_NODE:
                    continue
                sub_tag = sub.tagName.split(":")[-1] if ":" in sub.tagName else sub.tagName
                if sub_tag == "srgbClr":
                    v = sub.getAttribute("val")
                    if v:
                        scheme_map[tag] = v.upper()
                elif sub_tag == "sysClr":
                    v = sub.getAttribute("lastClr")
                    if v:
                        scheme_map[tag] = v.upper()
    except Exception:
        pass
    return scheme_map


def _color_saturation(hex_color: str) -> float:
    """计算颜色饱和度(0-1)"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        maxc, minc = max(r, g, b), min(r, g, b)
        return 0.0 if maxc == 0 else (maxc - minc) / maxc
    except Exception:
        return 0.0


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
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(slide_pattern.pattern)])
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    anim_types = Counter()

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")

            # 检查是否有 timing 节点
            if "<p:timing>" not in xml and "<timing>" not in xml:
                continue

            # 提取动画类型
            # 常见动画标签: anim, animEffect, animMotion, set
            effects = re.findall(r'<p:animEffect[^>]*transition="([^"]*)"', xml)
            for eff in effects:
                anim_types[eff] += 1

            # 提取触发方式
            click_triggers = xml.count('p:click') + xml.count('advTm')
            after_triggers = xml.count('afterPrevious')

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

    # 章节分隔页：暗背景+少量文字
    if bg_color and _is_dark_color(bg_color) and len(texts) <= 3:
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
