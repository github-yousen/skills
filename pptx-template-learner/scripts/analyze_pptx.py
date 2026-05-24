#!/usr/bin/env python3
"""从PPTX文件中提取完整设计规范，输出spec.json

分析维度（v3.0 全面增强版）：
  1. 配色方案（含渐变填充、暗/亮页配色组）
  2. 字体体系（区分中英文字体、行距、字间距）
  3. 布局结构（自动识别布局骨架模式 — EMU→inches转换修复）
  4. 动画效果（详细提取预设、时序、触发）
  5. 转场效果
  6. 目录结构（多级章节识别）
  7. 幻灯片类型（12种角色分类）
  8. 版式比例
  9. 装饰元素体系（装饰线/形状/页码/Logo区域）
  10. 文本排版规则（行距/对齐/缩进/列表/文字效果）
  11. 图片与图标风格
  12. 边距信息（从内容区域反推）
  13. 渐变填充（完整提取schemeClr/srgbClr+shade/lumMod）
  14. 母版/版式关系
  15. 表格和图表样式

v3.0 关键修复：
  - 修复布局模式识别：_extract_elements_positions 返回 inches 而非 EMU
  - 修复渐变提取：正确处理 schemeClr + shade/lumMod/satMod 变换
  - 递归遍历 grpSp 内嵌套元素
  - 增强 _identify_layout_pattern 使用归一化坐标判断
  - 增加更多布局模式识别：timeline、comparison、gallery等
  - 字体 fallback 策略
  - 支持非标准PPT（如WPS生成的文件）

Usage:
    python analyze_pptx.py <input.pptx> <output_spec.json> [--theme "主题名"]

Examples:
    python analyze_pptx.py template.pptx spec.json --theme "工作汇报"
    python analyze_pptx.py demo.pptx spec.json
"""

import argparse
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import defusedxml.minidom

# OOXML 命名空间
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}

# EMU to inches: 1 inch = 914400 EMU
EMU_PER_INCH = 914400


def analyze_pptx(pptx_path: str, theme_name: str = None) -> dict:
    """主分析函数，从PPTX提取完整规范（v3.0）"""
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        raise FileNotFoundError(f"文件不存在: {pptx_path}")

    # 检查是否为有效zip文件
    if not zipfile.is_zipfile(pptx_path):
        raise ValueError(f"不是有效的PPTX/ZIP文件: {pptx_path}")

    with zipfile.ZipFile(pptx_path, "r") as zf:
        names = zf.namelist()
        slide_w, slide_h = _get_slide_size_emu(zf)

        # 检查是否包含slide文件
        slide_files = sorted([n for n in names if re.match(r"^ppt/slides/slide\d+\.xml$", n)])
        if not slide_files:
            raise ValueError(f"PPTX文件中没有幻灯片: {pptx_path}")

        # 1. 幻灯片尺寸
        slide_size = _extract_slide_size(zf)

        # 2. 配色方案（含渐变）
        colors = _extract_colors(zf)

        # 3. 渐变填充
        gradients = _extract_gradients(zf)

        # 4. 字体体系（含中英文字体区分、行距、字间距）
        fonts, typography = _extract_fonts_and_typography(zf)

        # 5. 文本排版规则
        text_styles = _extract_text_styles(zf)

        # 6. 装饰元素体系
        decorations = _extract_decorations(zf, slide_w, slide_h)

        # 7. 边距信息（从内容区域反推）
        margins = _extract_margins(zf, slide_w, slide_h)

        # 8. 图片与图标风格
        image_style = _extract_image_style(zf, slide_w, slide_h)

        # 9. 布局结构（含骨架模式识别）
        slide_types, toc_structure, layout_patterns = _extract_slide_structure(zf, slide_w, slide_h)

        # 10. 动画效果（详细）
        animations = _extract_animations(zf)

        # 11. 转场效果
        transitions = _extract_transitions(zf)

        # 12. 母版/版式关系
        master_layouts = _extract_master_layouts(zf)

        # 13. 表格和图表样式
        table_chart_styles = _extract_table_chart_styles(zf)

    spec = {
        "theme": theme_name or pptx_path.stem,
        "mode": "strict",
        "version": "3.0",
        "meta": {
            "analyzed_at": datetime.now().isoformat(),
            "source_files": [pptx_path.name],
            "slide_count_range": [len(slide_types), len(slide_types)],
            "analyzer_version": "3.0",
        },
        "slide_size": slide_size,
        "colors": colors,
        "gradients": gradients,
        "fonts": fonts,
        "typography": typography,
        "text_styles": text_styles,
        "layout": {
            "margins": margins,
            "patterns": layout_patterns,
        },
        "decorations": decorations,
        "image_style": image_style,
        "toc_structure": toc_structure,
        "slide_types": slide_types,
        "master_layouts": master_layouts,
        "table_chart_styles": table_chart_styles,
        "animations": {
            "default_transition": transitions.get("default", "none"),
            "transition_duration_ms": transitions.get("duration_ms", 700),
            "transition_details": transitions.get("details", []),
            "element_animations": animations,
        },
    }

    return spec


# ────────────────────── 1. 幻灯片尺寸 ──────────────────────

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
            w_in = round(cx / EMU_PER_INCH, 3)
            h_in = round(cy / EMU_PER_INCH, 3)
            ratio = round(w_in / h_in, 3) if h_in else 0
            if 1.2 < ratio < 1.4:
                orientation = "4:3"
            elif 1.7 < ratio < 1.9:
                orientation = "16:9"
            elif 1.3 <= ratio <= 1.7:
                orientation = "3:2"
            else:
                orientation = f"{ratio:.2f}"
            return {"width": w_in, "height": h_in, "orientation": orientation}
    except Exception:
        pass
    return {"width": 10, "height": 5.625, "orientation": "16:9"}


def _get_slide_size_emu(zf: zipfile.ZipFile) -> tuple:
    """获取幻灯片尺寸（EMU），用于位置归一化"""
    try:
        pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
        dom = defusedxml.minidom.parseString(pres_xml)
        sldSz_nodes = dom.getElementsByTagName("p:sldSz")
        if sldSz_nodes:
            node = sldSz_nodes[0]
            return int(node.getAttribute("cx")), int(node.getAttribute("cy"))
    except Exception:
        pass
    return 9144000, 5143500  # 默认10x5.625英寸


# ────────────────────── 2. 配色方案 ──────────────────────

def _extract_colors(zf: zipfile.ZipFile) -> dict:
    """提取配色方案（v3.0: 增加暗/亮页配色组区分）"""
    colors = {
        "primary": "1E2761",
        "secondary": "CADCFC",
        "accent": "0891B2",
        "bg_dark": "1E2761",
        "bg_light": "FFFFFF",
        "text_dark": "212121",
        "text_light": "FFFFFF",
    }

    slide_w, slide_h = _get_slide_size_emu(zf)

    # 提取背景色
    bg_data = _extract_bg_colors_with_shapes(zf, slide_w, slide_h)
    dark_bgs = [c for c, area in bg_data if _is_dark_color(c)]
    light_bgs = [c for c, area in bg_data if not _is_dark_color(c)]
    if dark_bgs:
        colors["bg_dark"] = Counter(dark_bgs).most_common(1)[0][0]
    if light_bgs:
        colors["bg_light"] = Counter(light_bgs).most_common(1)[0][0]
    if not dark_bgs and bg_data:
        bg_counter = Counter(c for c, area in bg_data)
        colors["bg_dark"] = bg_counter.most_common(1)[0][0]

    init_defaults = {"1E2761", "CADCFC", "0891B2", "212121", "FFFFFF"}
    ooxml_defaults = {"1F497D", "EEECE1", "4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6", "F79646", "0000FF", "800080"}
    hardcoded_defaults = init_defaults | ooxml_defaults

    # 形状填充色
    shape_data = _extract_shape_fill_data(zf, slide_w, slide_h)
    exclude = set([colors["bg_light"].upper(), "FFFFFF", "000000"])
    candidates = []
    for col, area in shape_data:
        cu = col.upper()
        if cu not in exclude and not _is_neutral_gray(cu):
            candidates.append((cu, area))

    if candidates:
        weighted = Counter()
        for col, area in candidates:
            sat = _color_saturation(col)
            lum = _color_luminance(col)
            weight = max(1, int(area / (slide_w * slide_h) * 100))
            if sat > 0.3:
                weight = int(weight * 1.5)
            if lum < 0.15 or lum > 0.95:
                weight = max(1, int(weight * 0.02))
            if lum > 0.98:
                weight = max(1, int(weight * 0.05))
            if col in hardcoded_defaults:
                weight = max(1, int(weight * 0.1))
            weighted[col] += weight
        sorted_colors = weighted.most_common()
        sorted_colors = [(c, w) for c, w in sorted_colors if c not in hardcoded_defaults or w > 5]
        if sorted_colors:
            candidate = sorted_colors[0][0]
            bg_d = colors.get("bg_dark", "")
            if candidate == bg_d and bg_d and _color_luminance(bg_d) < 0.15:
                for c, w in sorted_colors:
                    if c != bg_d and _color_luminance(c) > 0.5 and _color_saturation(c) > 0.2:
                        candidate = c
                        break
            colors["primary"] = candidate
        if len(sorted_colors) > 1:
            colors["secondary"] = sorted_colors[1][0]
        if len(sorted_colors) > 2:
            colors["accent"] = sorted_colors[2][0]

    # 从文本+形状颜色补充
    scheme_map = _build_scheme_color_map(zf)
    all_color_data = Counter()
    for col, freq in _extract_text_color_data(zf, scheme_map):
        cu = col.upper()
        if cu not in exclude and not _is_neutral_gray(cu) and cu not in ooxml_defaults:
            sat = _color_saturation(cu)
            weight = freq
            if sat > 0.3:
                weight = int(weight * 1.5)
            all_color_data[cu] += weight
    for col, area in candidates:
        cu = col.upper()
        if cu not in ooxml_defaults:
            weight = max(1, int(area / (slide_w * slide_h) * 100))
            if _color_saturation(cu) > 0.3:
                weight = int(weight * 1.5)
            all_color_data[cu] += weight

    if all_color_data:
        all_sorted = all_color_data.most_common()
        dark_candidates = [(c, w) for c, w in all_sorted if _is_dark_color(c)]
        light_candidates = [(c, w) for c, w in all_sorted if not _is_dark_color(c)]
        if colors.get("primary", "") in init_defaults:
            if dark_candidates:
                colors["primary"] = dark_candidates[0][0]
            elif all_sorted:
                colors["primary"] = all_sorted[0][0]
        sec = colors.get("secondary", "")
        if sec in init_defaults or sec in ooxml_defaults or _is_neutral_gray(sec):
            if light_candidates:
                colors["secondary"] = light_candidates[0][0]
            elif len(all_sorted) > 1:
                for c, w in all_sorted:
                    if c != colors["primary"]:
                        colors["secondary"] = c
                        break
        acc = colors.get("accent", "")
        if acc in init_defaults or acc in ooxml_defaults or _is_neutral_gray(acc):
            sat_sorted = sorted(all_sorted, key=lambda x: _color_saturation(x[0]), reverse=True)
            for c, w in sat_sorted:
                if c != colors["primary"] and c != colors["secondary"]:
                    colors["accent"] = c
                    break
            else:
                for c, w in all_sorted:
                    if c != colors["primary"] and c != colors["secondary"]:
                        colors["accent"] = c
                        break
                else:
                    colors["accent"] = colors["secondary"]

    if colors.get("primary", "") in init_defaults:
        bg = colors.get("bg_dark", "")
        if bg and _color_saturation(bg) > 0.15:
            colors["primary"] = bg

    bg_d = colors.get("bg_dark", "")
    if bg_d and _color_saturation(bg_d) > 0.15 and _is_dark_color(bg_d) and _color_luminance(bg_d) >= 0.15:
        current_primary = colors.get("primary", "")
        if not _is_dark_color(current_primary) or current_primary in hardcoded_defaults:
            if _color_saturation(current_primary) > 0.3:
                colors["accent"] = current_primary
            colors["primary"] = bg_d

    # 文本颜色
    text_colors = _extract_text_colors(zf)
    if text_colors:
        dark_texts = [c for c in text_colors if _is_dark_color(c)]
        light_texts = [c for c in text_colors if not _is_dark_color(c)]
        if dark_texts:
            colors["text_dark"] = Counter(dark_texts).most_common(1)[0][0]
        if light_texts:
            colors["text_light"] = Counter(light_texts).most_common(1)[0][0]

    # theme1.xml 兜底
    _apply_theme_fallback(zf, colors, hardcoded_defaults, init_defaults)

    return colors


def _apply_theme_fallback(zf, colors, hardcoded_defaults, init_defaults):
    """从theme1.xml兜底补充配色"""
    theme_path = "ppt/theme/theme1.xml"
    if theme_path not in zf.namelist():
        return
    try:
        theme_xml = zf.read(theme_path).decode("utf-8")
        dom = defusedxml.minidom.parseString(theme_xml)
        clr_schemes = dom.getElementsByTagName("a:clrScheme")
        if not clr_schemes:
            return
        scheme = clr_schemes[0]
        role_map = {
            "dk1": "text_dark", "lt1": "text_light",
            "dk2": "bg_dark", "lt2": "bg_light",
            "accent1": "primary", "accent2": "secondary", "accent3": "accent",
        }
        for child in scheme.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            role = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
            target = role_map.get(role)
            if not target:
                continue
            current = colors.get(target, "")
            if current and current not in hardcoded_defaults and current not in init_defaults:
                continue
            for srgb in child.getElementsByTagName("a:srgbClr"):
                val = srgb.getAttribute("val")
                if val and len(val) == 6:
                    colors[target] = val.upper()
                    break
            else:
                for sys_clr in child.getElementsByTagName("a:sysClr"):
                    val = sys_clr.getAttribute("lastClr")
                    if val and len(val) == 6:
                        colors[target] = val.upper()
                        break
    except Exception:
        pass


# ────────────────────── 3. 渐变填充 ──────────────────────

def _extract_gradients(zf: zipfile.ZipFile) -> list:
    """提取渐变填充信息（v3.0: 完整处理schemeClr+shade/lumMod/satMod变换）"""
    gradients = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    # 构建scheme颜色映射
    scheme_map = _build_scheme_color_map(zf)

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            for grad in dom.getElementsByTagName("a:gradFill"):
                grad_info = {"stops": [], "direction": None, "tile_rect": None}

                # 提取方向
                lin = grad.getElementsByTagName("a:lin")
                if lin:
                    ang = lin[0].getAttribute("ang")
                    if ang:
                        angle_deg = int(ang) / 60000
                        grad_info["direction"] = _angle_to_direction(angle_deg)
                        grad_info["angle_deg"] = round(angle_deg, 1)

                # 提取路径渐变
                path_el = grad.getElementsByTagName("a:path")
                if path_el:
                    path_type = path_el[0].getAttribute("path") or "shape"
                    grad_info["path_type"] = path_type

                # tileRect
                tile = grad.getElementsByTagName("a:tileRect")
                if tile:
                    tr = {}
                    for attr in ["l", "t", "r", "b"]:
                        v = tile[0].getAttribute(attr)
                        if v:
                            tr[attr] = int(v) / 1000  # 转百分比
                    if tr:
                        grad_info["tile_rect"] = tr

                # 提取停靠点
                gsLst = grad.getElementsByTagName("a:gsLst")
                if gsLst:
                    for gs in gsLst[0].getElementsByTagName("a:gs"):
                        pos = gs.getAttribute("pos")
                        pos_pct = int(pos) / 1000 if pos else None  # pos 单位是 1/1000 百分比
                        color = None

                        # 优先 srgbClr
                        for srgb in gs.getElementsByTagName("a:srgbClr"):
                            val = srgb.getAttribute("val")
                            if val:
                                color = val.upper()
                                # 检查是否有alpha
                                alpha = srgb.getElementsByTagName("a:alpha")
                                if alpha:
                                    a_val = alpha[0].getAttribute("val")
                                    if a_val:
                                        color = f"{color}@{round(int(a_val)/1000)}%"
                                break

                        # 如果没有srgbClr，尝试schemeClr
                        if not color:
                            for sclr in gs.getElementsByTagName("a:schemeClr"):
                                ref = sclr.getAttribute("val")
                                base_color = scheme_map.get(ref)
                                if base_color:
                                    color = base_color
                                    # 应用颜色变换
                                    for shade in sclr.getElementsByTagName("a:shade"):
                                        sv = shade.getAttribute("val")
                                        if sv:
                                            color = _apply_shade(color, int(sv))
                                    for lumMod in sclr.getElementsByTagName("a:lumMod"):
                                        lv = lumMod.getAttribute("val")
                                        if lv:
                                            color = _apply_lum_mod(color, int(lv))
                                    for lumOff in sclr.getElementsByTagName("a:lumOff"):
                                        lo = lumOff.getAttribute("val")
                                        if lo:
                                            color = _apply_lum_off(color, int(lo))
                                    for satMod in sclr.getElementsByTagName("a:satMod"):
                                        sm = satMod.getAttribute("val")
                                        if sm:
                                            color = _apply_sat_mod(color, int(sm))
                                    break

                        if color and pos_pct is not None:
                            grad_info["stops"].append({"position": pos_pct, "color": color})

                if grad_info["stops"]:
                    gradients.append(grad_info)
        except Exception:
            continue

    # 去重（相似渐变合并）
    unique_gradients = []
    seen_stops = set()
    for g in gradients:
        key = tuple((s["position"], s["color"]) for s in g["stops"])
        if key not in seen_stops:
            seen_stops.add(key)
            unique_gradients.append(g)

    return unique_gradients[:15]  # 最多15种


def _apply_shade(hex_color: str, shade_val: int) -> str:
    """应用shade变换（shade_val 单位 1/1000，如 51000 = 51%）"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        factor = shade_val / 100000
        r = min(255, max(0, int(r * factor)))
        g = min(255, max(0, int(g * factor)))
        b = min(255, max(0, int(b * factor)))
        return f"{r:02X}{g:02X}{b:02X}"
    except Exception:
        return hex_color


def _apply_lum_mod(hex_color: str, lum_val: int) -> str:
    """应用亮度调制（lum_val 单位 1/1000）"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        # 转HSL，调制L
        h, s, l = _rgb_to_hsl(r, g, b)
        l = l * (lum_val / 100000)
        r, g, b = _hsl_to_rgb(h, s, l)
        return f"{r:02X}{g:02X}{b:02X}"
    except Exception:
        return hex_color


def _apply_lum_off(hex_color: str, off_val: int) -> str:
    """应用亮度偏移"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        h, s, l = _rgb_to_hsl(r, g, b)
        l = min(1.0, max(0.0, l + off_val / 100000))
        r, g, b = _hsl_to_rgb(h, s, l)
        return f"{r:02X}{g:02X}{b:02X}"
    except Exception:
        return hex_color


def _apply_sat_mod(hex_color: str, sat_val: int) -> str:
    """应用饱和度调制"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        h, s, l = _rgb_to_hsl(r, g, b)
        s = min(1.0, max(0.0, s * sat_val / 100000))
        r, g, b = _hsl_to_rgb(h, s, l)
        return f"{r:02X}{g:02X}{b:02X}"
    except Exception:
        return hex_color


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple:
    """RGB转HSL"""
    r, g, b = r / 255, g / 255, b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6
    return h, s, l


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple:
    """HSL转RGB"""
    if s == 0:
        v = int(l * 255)
        return v, v, v
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def hue2rgb(pp, qq, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return pp + (qq - pp) * 6 * t
        if t < 1/2: return qq
        if t < 2/3: return pp + (qq - pp) * (2/3 - t) * 6
        return pp

    r = int(round(hue2rgb(p, q, h + 1/3) * 255))
    g = int(round(hue2rgb(p, q, h) * 255))
    b = int(round(hue2rgb(p, q, h - 1/3) * 255))
    return min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b))


def _angle_to_direction(angle_deg: float) -> str:
    """将角度转换为方向描述"""
    a = angle_deg % 360
    if a < 22.5 or a >= 337.5:
        return "left-to-right"
    elif 22.5 <= a < 67.5:
        return "top-left-to-bottom-right"
    elif 67.5 <= a < 112.5:
        return "top-to-bottom"
    elif 112.5 <= a < 157.5:
        return "top-right-to-bottom-left"
    elif 157.5 <= a < 202.5:
        return "right-to-left"
    elif 202.5 <= a < 247.5:
        return "bottom-right-to-top-left"
    elif 247.5 <= a < 292.5:
        return "bottom-to-top"
    else:
        return "bottom-left-to-top-right"


# ────────────────────── 4. 字体体系 + 排版 ──────────────────────

# 字体fallback映射表（当检测到的字体不可用时使用）
FONT_FALLBACK = {
    # 西文字体
    "Arial": "Helvetica",
    "Calibri": "Arial",
    "Helvetica": "Arial",
    "Times New Roman": "Georgia",
    "Segoe UI": "Tahoma",
    "Tahoma": "Verdana",
    "Verdana": "Arial",
    "Century Gothic": "Arial",
    "Gill Sans": "Arial",
    # 中文字体
    "微软雅黑": "PingFang SC",
    "等线": "微软雅黑",
    "黑体": "SimHei",
    "SimHei": "微软雅黑",
    "宋体": "SimSun",
    "SimSun": "宋体",
    "楷体": "KaiTi",
    "仿宋": "FangSong",
    "PingFang SC": "微软雅黑",
    "华文细黑": "微软雅黑",
    "华文黑体": "微软雅黑",
    "华文楷体": "楷体",
    "Wingdings": "Arial",
    "Symbol": "Arial",
}


def _extract_fonts_and_typography(zf: zipfile.ZipFile) -> tuple:
    """提取字体体系（区分中英文字体）和排版参数（行距/字间距）"""
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    title_runs = []
    subtitle_runs = []
    body_runs = []

    # 排版统计
    line_spacing_data = []
    char_spacing_data = []
    alignment_data = []

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            for r_match in re.finditer(r'<a:r>.*?</a:r>', xml, re.DOTALL):
                r_block = r_match.group(0)
                block_start = r_match.start()
                preceding = xml[max(0, block_start - 3000):block_start]

                # placeholder type
                ph_type = None
                ph_m = re.search(r'<p:nvPr>.*?<p:ph[^>]*type="(\w+)"', preceding, re.DOTALL)
                if ph_m:
                    ph_type = ph_m.group(1)

                # 字体（区分拉丁和东亚）
                ea_m = re.search(r'<a:ea[^>]*typeface="([^"]+)"', r_block)
                latin_m = re.search(r'<a:latin[^>]*typeface="([^"]+)"', r_block)
                ea_font = ea_m.group(1) if ea_m else None
                latin_font = latin_m.group(1) if latin_m else None

                # Fallback to defRPr/endParaRPr
                if not ea_font and not latin_font:
                    for pattern in [r'<a:defRPr[^>]*>.*?</a:defRPr>', r'<a:endParaRPr[^>]*>.*?</a:endParaRPr>']:
                        m_def = re.search(pattern, preceding, re.DOTALL)
                        if m_def:
                            ea_font_m = re.search(r'<a:ea[^>]*typeface="([^"]+)"', m_def.group(0))
                            latin_font_m = re.search(r'<a:latin[^>]*typeface="([^"]+)"', m_def.group(0))
                            ea_font = ea_font_m.group(1) if ea_font_m else None
                            latin_font = latin_font_m.group(1) if latin_font_m else None
                            if ea_font or latin_font:
                                break

                # 过滤theme引用
                if ea_font and ea_font in ('+mj-ea', '+mn-ea'):
                    ea_font = None
                if latin_font and latin_font in ('+mj-lt', '+mn-lt'):
                    latin_font = None

                # 字号
                sz_m = re.search(r'<a:rPr[^>]*sz="(\d+)"', r_block)
                size = int(sz_m.group(1)) / 100 if sz_m else None
                if size is None:
                    for pattern_sz in [r'<a:defRPr[^>]*sz="(\d+)"', r'<a:endParaRPr[^>]*sz="(\d+)"']:
                        dsz = re.search(pattern_sz, preceding)
                        if dsz:
                            size = int(dsz.group(1)) / 100
                            break
                if size is None:
                    size = 18  # 默认

                # 粗体
                bold = bool(re.search(r'<a:rPr[^>]*b="1"', r_block))
                if not bold:
                    bold = bool(re.search(r'<a:defRPr[^>]*b="1"', preceding))

                # 斜体
                italic = bool(re.search(r'<a:rPr[^>]*i="1"', r_block))

                # 文本长度加权
                text_m = re.search(r'<a:t>([^<]*)</a:t>', r_block)
                weight = len(text_m.group(1)) if text_m else 1

                run = {
                    "latin_font": latin_font,
                    "ea_font": ea_font,
                    "size": size,
                    "bold": bold,
                    "italic": italic,
                    "weight": weight,
                }

                # 角色推断
                if ph_type in ('title', 'ctrTitle'):
                    title_runs.append(run)
                elif ph_type == 'body':
                    if size >= 28:
                        subtitle_runs.append(run)
                    else:
                        body_runs.append(run)
                elif ph_type == 'subTitle':
                    subtitle_runs.append(run)
                elif size >= 32:
                    title_runs.append(run)
                elif size >= 20:
                    subtitle_runs.append(run)
                elif size >= 8:
                    body_runs.append(run)

            # ── 提取行间距 ──
            for lnspc_m in re.finditer(r'<a:lnSpc>(.*?)</a:lnSpc>', xml, re.DOTALL):
                block = lnspc_m.group(1)
                pct_m = re.search(r'<a:spcPct[^>]*val="(\d+)"', block)
                if pct_m:
                    pct_val = int(pct_m.group(1))
                    line_spacing_data.append(pct_val / 100000)  # 100000 = 1.0
                pts_m = re.search(r'<a:spcPts[^>]*val="(\d+)"', block)
                if pts_m:
                    line_spacing_data.append(f"{int(pts_m.group(1))/100:.1f}pt")

            # ── 提取字间距 ──
            for spc_m in re.finditer(r'<a:rPr[^>]*spc="(-?\d+)"', xml):
                spc_val = int(spc_m.group(1))
                char_spacing_data.append(spc_val / 100)

            # ── 提取对齐方式 ──
            for algn_m in re.finditer(r'<a:pPr[^>]*algn="(\w+)"', xml):
                alignment_data.append(algn_m.group(1))

        except Exception:
            continue

    # ── 构建字体规范 ──
    def pick_font(runs, default_latin, default_ea, default_size, default_bold):
        if not runs:
            return {
                "name": default_latin,
                "ea_name": default_ea,
                "size": default_size,
                "bold": default_bold,
                "fallback": FONT_FALLBACK.get(default_latin, "Arial"),
            }

        latin_weight = Counter()
        ea_weight = Counter()
        size_weight = Counter()
        bold_weight = Counter()

        for r in runs:
            if r["latin_font"]:
                latin_weight[r["latin_font"]] += r["weight"]
            if r["ea_font"]:
                ea_weight[r["ea_font"]] += r["weight"]
            size_weight[r["size"]] += r["weight"]
            bold_weight[r["bold"]] += r["weight"]

        main_font = latin_weight.most_common(1)[0][0] if latin_weight else default_latin
        result = {
            "name": main_font,
            "size": round(size_weight.most_common(1)[0][0]),
            "bold": bold_weight.most_common(1)[0][0],
            "fallback": FONT_FALLBACK.get(main_font, "Arial"),
        }
        if ea_weight:
            ea_font = ea_weight.most_common(1)[0][0]
            result["ea_name"] = ea_font
            result["ea_fallback"] = FONT_FALLBACK.get(ea_font, "微软雅黑")
        else:
            result["ea_name"] = default_ea
            result["ea_fallback"] = FONT_FALLBACK.get(default_ea, "微软雅黑")
        return result

    fonts = {
        "title": pick_font(title_runs, "Arial", "微软雅黑", 36, True),
        "subtitle": pick_font(subtitle_runs, "Arial", "微软雅黑", 20, False),
        "body": pick_font(body_runs, "Calibri", "微软雅黑", 14, False),
    }

    # ── 构建排版规范 ──
    typography = {}

    if line_spacing_data:
        numeric_ls = [v for v in line_spacing_data if isinstance(v, (int, float))]
        if numeric_ls:
            typography["line_spacing"] = round(sum(numeric_ls) / len(numeric_ls), 2)
        else:
            typography["line_spacing"] = 1.2

    if char_spacing_data:
        typography["char_spacing"] = round(sum(char_spacing_data) / len(char_spacing_data), 1)

    if alignment_data:
        align_counter = Counter(alignment_data)
        align_map = {"l": "left", "ctr": "center", "r": "right", "just": "justify"}
        most_common = align_counter.most_common(1)[0][0]
        typography["alignment"] = align_map.get(most_common, "left")

    return fonts, typography


# ────────────────────── 5. 文本排版规则 ──────────────────────

def _extract_text_styles(zf: zipfile.ZipFile) -> dict:
    """提取文本排版规则：行距、段间距、对齐、缩进、列表样式、文字效果"""
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    styles = {
        "paragraph": {},
        "list": {},
        "text_effects": [],
    }

    para_space_before = []
    para_space_after = []
    indent_levels = []
    bullet_types = []
    text_effects = Counter()

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")

            # 段间距
            for spc_m in re.finditer(r'<a:spcBef>.*?<a:spcPts[^>]*val="(\d+)"', xml, re.DOTALL):
                para_space_before.append(int(spc_m.group(1)) / 100)
            for spc_m in re.finditer(r'<a:spcAft>.*?<a:spcPts[^>]*val="(\d+)"', xml, re.DOTALL):
                para_space_after.append(int(spc_m.group(1)) / 100)

            # 缩进
            for indent_m in re.finditer(r'<a:pPr[^>]*indent="(\d+)"', xml):
                indent_val = int(indent_m.group(1)) / EMU_PER_INCH
                indent_levels.append(round(indent_val, 2))
            for mar_m in re.finditer(r'<a:pPr[^>]*marL="(\d+)"', xml):
                mar_val = int(mar_m.group(1)) / EMU_PER_INCH
                indent_levels.append(round(mar_val, 2))

            # 项目符号类型
            if '<a:buChar' in xml:
                for bu_m in re.finditer(r'<a:buChar[^>]*char="([^"]+)"', xml):
                    bullet_types.append(bu_m.group(1))
            if '<a:buNone' in xml:
                bullet_types.append("none")
            if '<a:buAutoNum' in xml:
                bullet_types.append("numbered")

            # 文字效果
            if re.search(r'<a:effectLst>', xml):
                if re.search(r'<a:outerShdw', xml):
                    text_effects["shadow"] += 1
                if re.search(r'<a:reflection', xml):
                    text_effects["reflection"] += 1
                if re.search(r'<a:glow', xml):
                    text_effects["glow"] += 1
                if re.search(r'<a:3dFormat>', xml):
                    text_effects["3d"] += 1
                if re.search(r'<a:innerShdw', xml):
                    text_effects["inner_shadow"] += 1
                if re.search(r'<a:softEdge', xml):
                    text_effects["soft_edge"] += 1

            # 渐变文字填充
            if re.search(r'<a:gradFill', xml):
                # 检查是否在文本范围内
                for grad_text_m in re.finditer(r'<a:r>.*?<a:gradFill.*?</a:r>', xml, re.DOTALL):
                    text_effects["gradient_fill"] += 1
                    break

            # 文本框内边距
            for ins_m in re.finditer(r'<a:bodyPr[^>]*', xml):
                attrs = ins_m.group(0)
                for attr_name in ['lIns', 'tIns', 'rIns', 'bIns']:
                    val_m = re.search(f'{attr_name}="(-?\\d+)"', attrs)
                    if val_m:
                        val_inches = int(val_m.group(1)) / EMU_PER_INCH
                        if not styles["paragraph"].get("padding"):
                            styles["paragraph"]["padding"] = {}
                        styles["paragraph"]["padding"][attr_name] = round(val_inches, 3)

        except Exception:
            continue

    # 汇总
    if para_space_before:
        styles["paragraph"]["space_before"] = round(sum(para_space_before) / len(para_space_before), 1)
    if para_space_after:
        styles["paragraph"]["space_after"] = round(sum(para_space_after) / len(para_space_after), 1)
    if indent_levels:
        unique_indents = sorted(set(indent_levels))
        styles["paragraph"]["indent_levels"] = unique_indents[:5]

    if bullet_types:
        bt_counter = Counter(bullet_types)
        styles["list"]["default_type"] = bt_counter.most_common(1)[0][0]
        styles["list"]["types"] = dict(bt_counter.most_common(5))

    if text_effects:
        styles["text_effects"] = [{"type": t, "frequency": c} for t, c in text_effects.most_common(5)]

    return styles


# ────────────────────── 6. 装饰元素体系 ──────────────────────

def _extract_decorations(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> dict:
    """提取装饰元素：装饰线/形状/页码/Logo区域"""
    decorations = {
        "lines": [],
        "shapes": [],
        "page_numbers": {},
        "logo_areas": [],
        "bottom_bar": None,
    }

    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    line_colors = Counter()
    line_widths = Counter()
    deco_shapes = Counter()
    page_num_positions = []
    logo_candidates = []
    bottom_bar_candidates = []

    slide_w_in = slide_w / EMU_PER_INCH
    slide_h_in = slide_h / EMU_PER_INCH

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 查找连接线/装饰线（cxnSp）
            for cxn in dom.getElementsByTagName("p:cxnSp"):
                spPr = cxn.getElementsByTagName("p:spPr")
                if not spPr:
                    # 也可能在 spPr 没有命名空间前缀
                    spPr = cxn.getElementsByTagName("a:spPr")
                line_el = None
                for pr in spPr:
                    ln_nodes = pr.getElementsByTagName("a:ln")
                    if ln_nodes:
                        line_el = ln_nodes[0]
                        break
                if line_el:
                    w = line_el.getAttribute("w")
                    if w:
                        line_widths[int(w)] += 1
                    for srgb in line_el.getElementsByTagName("a:srgbClr"):
                        val = srgb.getAttribute("val")
                        if val:
                            line_colors[val.upper()] += 1

            # 查找装饰形状（p:sp，无文本且面积较小）
            for sp in dom.getElementsByTagName("p:sp"):
                t_nodes = sp.getElementsByTagName("a:t")
                has_text = any(t.firstChild and t.firstChild.nodeValue.strip() for t in t_nodes)

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
                total_area = slide_w * slide_h

                x_in = x / EMU_PER_INCH
                y_in = y / EMU_PER_INCH
                w_in = cx / EMU_PER_INCH
                h_in = cy / EMU_PER_INCH

                # 小面积无文本形状 → 装饰
                if not has_text and area > 0 and area < total_area * 0.5:
                    prstGeom = sp.getElementsByTagName("a:prstGeom")
                    shape_type = "unknown"
                    if prstGeom:
                        shape_type = prstGeom[0].getAttribute("prst") or "unknown"
                    deco_shapes[shape_type] += 1

                    # Logo检测：角落，尺寸0.3~2inch
                    is_corner = (x_in < 2 or x_in > slide_w_in - 2) and (y_in < 2 or y_in > slide_h_in - 2)
                    is_logo_size = 0.3 < w_in < 2 and 0.3 < h_in < 2
                    if is_corner and is_logo_size:
                        logo_candidates.append({
                            "x": round(x_in, 2), "y": round(y_in, 2),
                            "w": round(w_in, 2), "h": round(h_in, 2),
                        })

                # 底部信息栏检测
                if has_text and y_in > slide_h_in * 0.85 and h_in < 0.5:
                    text = " ".join(t.firstChild.nodeValue.strip() for t in t_nodes if t.firstChild)
                    if text:
                        bottom_bar_candidates.append({
                            "text": text[:50],
                            "y": round(y_in, 2),
                        })

                # 页码检测
                if has_text:
                    text = " ".join(t.firstChild.nodeValue.strip() for t in t_nodes if t.firstChild)
                    if re.match(r'^\d{1,3}$', text.strip()):
                        page_num_positions.append({
                            "x": round(x_in, 2),
                            "y": round(y_in, 2),
                        })

        except Exception:
            continue

    # 汇总
    if line_colors:
        decorations["lines"] = [{
            "color": c, "frequency": f
        } for c, f in line_colors.most_common(5)]
    if line_widths:
        avg_w = round(sum(w * f for w, f in line_widths.items()) / max(1, sum(line_widths.values())))
        decorations["lines"].append({"avg_width_emu": avg_w})
    if deco_shapes:
        decorations["shapes"] = [{"type": s, "count": c} for s, c in deco_shapes.most_common(10)]
    if page_num_positions:
        pp_counter = Counter((p["x"], p["y"]) for p in page_num_positions)
        most_common_pos = pp_counter.most_common(1)[0][0]
        decorations["page_numbers"] = {
            "position": {"x": most_common_pos[0], "y": most_common_pos[1]},
            "count": len(page_num_positions),
        }
    if logo_candidates:
        pos_counter = Counter((l["x"], l["y"]) for l in logo_candidates)
        most_common = pos_counter.most_common(1)[0][0]
        decorations["logo_areas"] = [{
            "position": {"x": most_common[0], "y": most_common[1]},
            "frequency": pos_counter[(most_common[0], most_common[1])],
        }]
    if bottom_bar_candidates:
        bb_counter = Counter(b["text"] for b in bottom_bar_candidates)
        most_common = bb_counter.most_common(1)[0][0]
        decorations["bottom_bar"] = {
            "text_preview": most_common[:50],
            "frequency": len(bottom_bar_candidates),
        }

    return decorations


# ────────────────────── 7. 边距信息 ──────────────────────

def _extract_margins(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> dict:
    """从内容区域反推实际边距"""
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    min_x_values = []
    min_y_values = []
    max_x_right = []
    max_y_bottom = []

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 递归遍历所有形状
            _collect_content_positions(dom, slide_w, slide_h,
                                       min_x_values, min_y_values,
                                       max_x_right, max_y_bottom)

        except Exception:
            continue

    margins = {}
    if min_x_values:
        sorted_x = sorted(min_x_values)
        idx = max(0, len(sorted_x) // 4)
        margins["left"] = round(sorted_x[idx] / EMU_PER_INCH, 2)
    else:
        margins["left"] = 0.5

    if min_y_values:
        sorted_y = sorted(min_y_values)
        idx = max(0, len(sorted_y) // 4)
        margins["top"] = round(sorted_y[idx] / EMU_PER_INCH, 2)
    else:
        margins["top"] = 0.5

    if max_x_right:
        sorted_xr = sorted(max_x_right)
        idx = max(0, len(sorted_xr) // 4)
        margins["right"] = round(sorted_xr[idx] / EMU_PER_INCH, 2)
    else:
        margins["right"] = 0.5

    if max_y_bottom:
        sorted_yb = sorted(max_y_bottom)
        idx = max(0, len(sorted_yb) // 4)
        margins["bottom"] = round(sorted_yb[idx] / EMU_PER_INCH, 2)
    else:
        margins["bottom"] = 0.5

    return margins


def _collect_content_positions(dom, slide_w, slide_h, min_x, min_y, max_x_right, max_y_bottom):
    """递归收集有文本内容元素的位置信息"""
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

        # 忽略全页背景形状（面积>80%）
        if area > slide_w * slide_h * 0.8:
            continue

        # 忽略极小装饰（面积<0.01%）
        if area < slide_w * slide_h * 0.0001:
            continue

        # 必须有文本内容才算内容元素
        t_nodes = sp.getElementsByTagName("a:t")
        has_text = any(t.firstChild and t.firstChild.nodeValue.strip() for t in t_nodes)
        if not has_text:
            continue

        if x > 0:
            min_x.append(x)
        if y > 0:
            min_y.append(y)
        right = x + cx
        bottom = y + cy
        if right < slide_w:
            max_x_right.append(slide_w - right)
        if bottom < slide_h:
            max_y_bottom.append(slide_h - bottom)


# ────────────────────── 8. 图片与图标风格 ──────────────────────

def _extract_image_style(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> dict:
    """提取图片风格：面积占比、位置偏好、形状裁剪"""
    style = {
        "avg_area_ratio": 0,
        "position_preference": "unknown",
        "shapes": [],
        "count": 0,
        "layout_type": "unknown",
        "image_per_slide": 0,
    }

    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    area_ratios = []
    positions = []
    crop_shapes = Counter()
    images_per_slide = []

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            slide_image_count = 0

            for pic in dom.getElementsByTagName("p:pic"):
                xfrm = pic.getElementsByTagName("a:xfrm")
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
                total = slide_w * slide_h

                if area > 0:
                    area_ratios.append(area / total)
                    positions.append((x / max(1, slide_w), y / max(1, slide_h)))

                # 裁剪形状
                prstGeom = pic.getElementsByTagName("a:prstGeom")
                if prstGeom:
                    shape = prstGeom[0].getAttribute("prst") or "rect"
                    crop_shapes[shape] += 1

                # 图片裁剪信息
                clipGeom = pic.getElementsByTagName("a:clipGeom")
                if clipGeom:
                    crop_shapes["clipped"] += 1

                style["count"] += 1
                slide_image_count += 1

            images_per_slide.append(slide_image_count)

        except Exception:
            continue

    if area_ratios:
        style["avg_area_ratio"] = round(sum(area_ratios) / len(area_ratios), 3)

    if positions:
        avg_x = sum(p[0] for p in positions) / len(positions)
        avg_y = sum(p[1] for p in positions) / len(positions)

        if avg_x < 0.3:
            style["position_preference"] = "left"
        elif avg_x > 0.6:
            style["position_preference"] = "right"
        else:
            style["position_preference"] = "center"

        avg_ratio = sum(area_ratios) / len(area_ratios) if area_ratios else 0
        if avg_ratio > 0.4:
            style["layout_type"] = "full-image-background"
        elif avg_ratio > 0.15:
            style["layout_type"] = "large-image"
        elif avg_ratio > 0.03:
            style["layout_type"] = "medium-image"
        else:
            style["layout_type"] = "icon-accent"

    if images_per_slide:
        style["image_per_slide"] = round(sum(images_per_slide) / len(images_per_slide), 1)

    if crop_shapes:
        style["shapes"] = [{"type": s, "count": c} for s, c in crop_shapes.most_common(5)]

    return style


# ────────────────────── 9. 布局结构（含骨架模式识别） ──────────────────────

def _extract_slide_structure(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> tuple:
    """提取幻灯片类型、目录结构、布局骨架模式"""
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    slide_types = []
    toc_structure = {"has_toc": False, "toc_slide_position": None, "sections": [], "hierarchy": []}
    sections = []
    layout_patterns = []
    seen_patterns = set()

    # 读取 slideLayout 类型
    layout_type_map = _read_slide_layout_types(zf)

    for idx, sf in enumerate(slide_files):
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 提取文本
            texts = []
            for t_node in dom.getElementsByTagName("a:t"):
                if t_node.firstChild and t_node.firstChild.nodeValue:
                    texts.append(t_node.firstChild.nodeValue.strip())

            # ★ 关键修复：提取元素位置，使用归一化坐标（inches）
            elements = _extract_elements_positions_normalized(dom, slide_w, slide_h)

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

            # 读取 slideLayout 关系
            sld_layout_type = _get_slide_layout_type(zf, sf, layout_type_map)

            # ★ 关键修复：使用归一化坐标识别布局模式
            layout_pattern = _identify_layout_pattern(elements, slide_w, slide_h, idx)

            # 分类
            role = _classify_slide(idx, len(slide_files), texts, bg_color, elements, sld_layout_type)

            slide_info = {
                "role": role,
                "index": idx + 1,
                "layout_pattern": layout_pattern,
                "text_preview": texts[:5] if texts else [],
                "element_count": len(elements),
                "bg_color": bg_color,
                "slide_layout_type": sld_layout_type,
                "elements": elements[:20] if elements else [],
            }

            # 目录检测
            if role == "toc":
                toc_structure["has_toc"] = True
                toc_structure["toc_slide_position"] = idx + 1
                for t in texts:
                    t_clean = t.strip()
                    if (len(t_clean) > 1 and len(t_clean) < 30 and
                        t_clean not in ("目录", "Contents", "大纲", "Outline", "议程", "Agenda")):
                        sections.append(t_clean)

            # 章节检测
            if role == "section" and texts:
                section_name = texts[0] if texts else f"章节{idx+1}"
                if section_name not in sections and len(section_name) < 30:
                    sections.append(section_name)

            # 记录布局模式
            if layout_pattern not in seen_patterns:
                seen_patterns.add(layout_pattern)
                layout_patterns.append({
                    "name": layout_pattern,
                    "used_in_roles": [role],
                    "description": _layout_pattern_description(layout_pattern),
                })
            else:
                for lp in layout_patterns:
                    if lp["name"] == layout_pattern and role not in lp["used_in_roles"]:
                        lp["used_in_roles"].append(role)

            slide_types.append(slide_info)

        except Exception as e:
            slide_types.append({
                "role": "content",
                "index": idx + 1,
                "layout_pattern": "unknown",
                "text_preview": [],
                "element_count": 0,
                "elements": [],
            })

    # 多级章节识别
    hierarchy = _build_section_hierarchy(sections)
    toc_structure["sections"] = sections[:10]
    toc_structure["hierarchy"] = hierarchy

    return slide_types, toc_structure, layout_patterns


def _extract_elements_positions_normalized(dom, slide_w: int, slide_h: int) -> list:
    """★ v3.0核心修复：从spTree中提取元素位置信息，返回归一化的inches坐标

    之前版本返回EMU原始值，导致布局模式识别全部失败。
    现在返回inches值，并递归遍历grpSp内嵌套元素。
    """
    elements = []
    sp_trees = dom.getElementsByTagName("p:spTree")
    if not sp_trees:
        return elements

    sp_tree = sp_trees[0]
    _traverse_sp_tree(sp_tree, elements, slide_w, slide_h)
    return elements


def _traverse_sp_tree(node, elements: list, slide_w: int, slide_h: int):
    """递归遍历spTree，提取所有元素位置（包括grpSp内的嵌套元素）"""
    for child in node.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue

        tag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName

        if tag == "grpSp":
            # 递归遍历组合形状内部
            _traverse_sp_tree(child, elements, slide_w, slide_h)
            continue

        if tag not in ("sp", "pic", "graphicFrame", "cxnSp"):
            continue

        elem = {"type": tag}

        xfrm_nodes = child.getElementsByTagName("a:xfrm")
        if xfrm_nodes:
            xfrm = xfrm_nodes[0]
            off = xfrm.getElementsByTagName("a:off")
            ext = xfrm.getElementsByTagName("a:ext")
            if off:
                x_emu = int(off[0].getAttribute("x") or 0)
                y_emu = int(off[0].getAttribute("y") or 0)
                elem["x"] = round(x_emu / EMU_PER_INCH, 3)  # ★ 转inches
                elem["y"] = round(y_emu / EMU_PER_INCH, 3)
            if ext:
                w_emu = int(ext[0].getAttribute("cx") or 0)
                h_emu = int(ext[0].getAttribute("cy") or 0)
                elem["w"] = round(w_emu / EMU_PER_INCH, 3)  # ★ 转inches
                elem["h"] = round(h_emu / EMU_PER_INCH, 3)

            # 归一化坐标 (0~1)，方便布局模式判断
            if slide_w > 0 and slide_h > 0:
                elem["nx"] = round(x_emu / slide_w, 3) if x_emu else 0
                elem["ny"] = round(y_emu / slide_h, 3) if y_emu else 0
                elem["nw"] = round(w_emu / slide_w, 3) if w_emu else 0
                elem["nh"] = round(h_emu / slide_h, 3) if h_emu else 0

        # 文本内容（拼接所有a:t节点）
        t_nodes = child.getElementsByTagName("a:t")
        texts = []
        for t_node in t_nodes:
            if t_node.firstChild and t_node.firstChild.nodeValue:
                texts.append(t_node.firstChild.nodeValue.strip())
        if texts:
            combined = " ".join(texts)
            elem["text"] = combined[:80]  # 增加长度限制

        # 形状类型
        prstGeom = child.getElementsByTagName("a:prstGeom")
        if prstGeom:
            elem["shape"] = prstGeom[0].getAttribute("prst") or "rect"

        # 是否有图片
        if tag == "pic":
            elem["has_image"] = True

        # placeholder类型
        nvPr = child.getElementsByTagName("p:nvPr")
        if not nvPr:
            nvPr = child.getElementsByTagName("nvPr")
        if nvPr:
            ph = nvPr[0].getElementsByTagName("p:ph")
            if not ph:
                ph = nvPr[0].getElementsByTagName("ph")
            if ph:
                ph_type = ph[0].getAttribute("type")
                if ph_type:
                    elem["placeholder"] = ph_type

        elements.append(elem)


def _read_slide_layout_types(zf: zipfile.ZipFile) -> dict:
    """读取所有 slideLayout 的类型名称"""
    layout_map = {}
    layout_pattern = re.compile(r"^ppt/slideLayouts/slideLayout(\d+)\.xml$")
    for name in zf.namelist():
        m = layout_pattern.match(name)
        if m:
            try:
                xml = zf.read(name).decode("utf-8")
                name_m = re.search(r'<p:cSld\s+name="([^"]*)"', xml)
                layout_type = name_m.group(1) if name_m else f"layout{m.group(1)}"
                layout_map[int(m.group(1))] = layout_type
            except Exception:
                pass
    return layout_map


def _get_slide_layout_type(zf: zipfile.ZipFile, slide_file: str, layout_type_map: dict) -> str:
    """获取幻灯片使用的 slideLayout 类型"""
    try:
        slide_num_m = re.search(r'slide(\d+)\.xml', slide_file)
        if not slide_num_m:
            return None
        slide_num = slide_num_m.group(1)
        rels_path = f"ppt/slides/_rels/slide{slide_num}.xml.rels"
        if rels_path not in zf.namelist():
            return None
        rels_xml = zf.read(rels_path).decode("utf-8")
        layout_m = re.search(r'Target="\.\./slideLayouts/slideLayout(\d+)\.xml"', rels_xml)
        if layout_m:
            layout_num = int(layout_m.group(1))
            return layout_type_map.get(layout_num, f"layout{layout_num}")
    except Exception:
        pass
    return None


def _identify_layout_pattern(elements: list, slide_w: int, slide_h: int, slide_idx: int) -> str:
    """★ v3.0核心修复：根据元素位置关系识别布局骨架模式

    使用归一化坐标（0~1）进行判断，修复之前EMU值导致所有模式识别失败的问题。
    """
    if not elements:
        return "empty"

    slide_w_in = slide_w / EMU_PER_INCH
    slide_h_in = slide_h / EMU_PER_INCH

    # 分类元素
    text_elements = [e for e in elements if e.get("text")]
    pic_elements = [e for e in elements if e.get("type") == "pic" or e.get("has_image")]
    shape_elements = [e for e in elements if not e.get("text") and e.get("type") in ("sp", "cxnSp")]
    # 有placeholder属性的元素
    title_elements = [e for e in elements if e.get("placeholder") in ('title', 'ctrTitle')]
    body_elements = [e for e in elements if e.get("placeholder") == 'body']
    subtitle_elements = [e for e in elements if e.get("placeholder") == 'subTitle']

    # 没有内容只有装饰/图片
    if not text_elements and not pic_elements:
        if shape_elements:
            return "decoration-only"
        return "empty"

    # 只有图片没有文字
    if pic_elements and not text_elements:
        if len(pic_elements) >= 3:
            return "gallery"
        return "image-only"

    # ★ 使用归一化坐标(nx, ny, nw, nh)进行判断
    # 归一化中心点
    def elem_center(e):
        nx = e.get("nx", e.get("x", 0) / slide_w_in)
        ny = e.get("ny", e.get("y", 0) / slide_h_in)
        nw = e.get("nw", e.get("w", 0) / slide_w_in)
        nh = e.get("nh", e.get("h", 0) / slide_h_in)
        return nx + nw / 2, ny + nh / 2, nx, ny, nw, nh

    # 只有一个居中大标题
    if len(text_elements) == 1 and not pic_elements:
        e = text_elements[0]
        cx, cy, nx, ny, nw, nh = elem_center(e)
        # 居中判断：中心在页面中间区域
        if 0.25 < cx < 0.75 and 0.2 < cy < 0.8:
            return "centered-title"

    # ★ 判断上标题+下内容模式
    if text_elements:
        # 按y坐标排序
        sorted_by_y = sorted(text_elements, key=lambda e: e.get("ny", e.get("y", 0) / slide_h_in))
        top = sorted_by_y[0]
        top_ny = top.get("ny", top.get("y", 0) / slide_h_in)
        top_nh = top.get("nh", top.get("h", 0) / slide_h_in)

        # 标题在上方（y < 30% 或 placeholder=title）
        is_title_top = top_ny < 0.3 or top.get("placeholder") in ('title', 'ctrTitle')

        if is_title_top and len(text_elements) >= 2:
            # 检查是否有左右分区
            content_elements = [e for e in text_elements if e is not top]
            # 排除标题后的元素
            content_left = [e for e in content_elements if elem_center(e)[0] < 0.45]
            content_right = [e for e in content_elements if elem_center(e)[0] >= 0.55]

            if content_left and content_right:
                # 左右分栏
                has_left_image = any(e.get("type") == "pic" or e.get("has_image")
                                   for e in elements if elem_center(e)[0] < 0.45)
                has_right_image = any(e.get("type") == "pic" or e.get("has_image")
                                    for e in elements if elem_center(e)[0] >= 0.55)
                if has_left_image and not has_right_image:
                    return "left-image-right-text"
                elif has_right_image and not has_left_image:
                    return "left-text-right-image"
                else:
                    return "two-column"

            # 检查是否是多列/多卡片
            if len(content_elements) >= 3:
                x_positions = [elem_center(e)[0] for e in content_elements]
                x_spread = max(x_positions) - min(x_positions) if x_positions else 0
                if x_spread > 0.3:
                    return "multi-card"

            # 检查图片+文字模式
            if pic_elements:
                pic_top = min(elem_center(p)[1] for p in pic_elements)
                text_top = min(elem_center(e)[1] for e in content_elements if e.get("text"))
                if pic_top < text_top:
                    return "top-image-bottom-text"
                else:
                    return "top-title-bottom-content"
            else:
                return "top-title-bottom-content"

        # 标题不在上方，但有左右分区
        left_elements = [e for e in text_elements if elem_center(e)[0] < 0.45]
        right_elements = [e for e in text_elements if elem_center(e)[0] >= 0.55]

        if left_elements and right_elements:
            has_left_image = any(e.get("type") == "pic" or e.get("has_image")
                               for e in elements if elem_center(e)[0] < 0.45)
            has_right_image = any(e.get("type") == "pic" or e.get("has_image")
                                for e in elements if elem_center(e)[0] >= 0.55)
            if has_left_image and not has_right_image:
                return "left-image-right-text"
            elif has_right_image and not has_left_image:
                return "left-text-right-image"
            else:
                return "two-column"

    # 图片展示页
    if pic_elements and len(pic_elements) >= 2 and len(text_elements) <= 2:
        return "gallery"

    # 标题居中在顶部
    if title_elements:
        return "header-content"

    # 默认
    return "free-form"


def _layout_pattern_description(pattern: str) -> str:
    """布局模式描述"""
    descriptions = {
        "centered-title": "居中大标题，通常用于封面/章节页",
        "top-title-bottom-content": "上方标题+下方内容，最常见的布局",
        "header-content": "顶部标题栏+内容区",
        "left-image-right-text": "左图右文，适合图文混排",
        "left-text-right-image": "左文右图，适合图文混排",
        "top-image-bottom-text": "上图下文，图片为主",
        "two-column": "左右双栏内容",
        "multi-card": "多卡片/多列展示",
        "gallery": "图片展示页/画廊",
        "image-only": "纯图片页",
        "decoration-only": "纯装饰页",
        "empty": "空白页",
        "free-form": "自由布局",
        "comparison": "对比/对照布局",
        "timeline": "时间轴/历程布局",
    }
    return descriptions.get(pattern, pattern)


def _classify_slide(idx: int, total: int, texts: list, bg_color: str, elements: list, sld_layout_type: str = None) -> str:
    """分类幻灯片类型（v3.0: 12种类型）"""
    # 封面
    if idx == 0:
        return "cover"

    # 结尾
    if idx == total - 1:
        ending_keywords = ["谢谢", "感谢", "thank", "thanks", "Q&A", "问答", "结束", "THE END", "谢谢聆听", "感谢聆听", "thanks!", "thank you"]
        combined = " ".join(texts).lower()
        if any(kw.lower() in combined for kw in ending_keywords):
            return "ending"
        return "content"

    # 目录页
    toc_keywords = ["目录", "contents", "大纲", "outline", "议程", "agenda", "概览", "overview", "目录页", "content"]
    combined = " ".join(texts).lower()
    if any(kw.lower() in combined for kw in toc_keywords):
        return "toc"

    # 对比页
    comparison_keywords = ["对比", "比较", "vs", "versus", "差异", "优劣", "区别", "对照", "comparison"]
    if any(kw in combined for kw in comparison_keywords):
        return "comparison"

    # 时间轴页
    timeline_keywords = ["时间线", "发展历程", "里程碑", "timeline", "历程", "演进", "路线图", "roadmap", "大事记", "发展脉络"]
    if any(kw in combined for kw in timeline_keywords):
        return "timeline"

    # 引用页
    quote_keywords = ["名言", "引用", "quote", "说:", "说过", "——"]
    if any(kw in combined for kw in quote_keywords) and len(texts) <= 3:
        return "quote"

    # 团队介绍页
    team_keywords = ["团队", "成员", "team", "创始人", "核心成员", "团队介绍"]
    if any(kw in combined for kw in team_keywords):
        return "team"

    # 章节分隔页：暗背景+少量文字
    if bg_color and _is_dark_color(bg_color) and len(texts) <= 3:
        return "section"

    # 数据展示
    has_chart = any(e.get("type") in ("graphicFrame", "chart") for e in elements)
    if has_chart:
        return "data"

    # 使用 slideLayout 类型辅助判断
    if sld_layout_type:
        lt = sld_layout_type.lower()
        if "section" in lt:
            return "section"
        if "title" in lt and len(texts) <= 2:
            return "section"
        if "comparison" in lt:
            return "comparison"
        if "picture" in lt:
            return "gallery"
        if "blank" in lt and len(texts) <= 2:
            return "section"

    # 图片展示页
    pic_count = sum(1 for e in elements if e.get("type") == "pic" or e.get("has_image"))
    if pic_count >= 2 and len(texts) <= 3:
        return "gallery"

    return "content"


def _build_section_hierarchy(sections: list) -> list:
    """从章节名列表构建层级结构"""
    if not sections:
        return []

    hierarchy = []
    for sec in sections:
        level = 0
        if re.match(r'^\d+\.\d+', sec):
            level = 1  # 二级章节
        elif re.match(r'^\d+[\.、\s]', sec) or re.match(r'^[第]\d+[章]', sec) or re.match(r'^[一二三四五六七八九十]+[章、]', sec):
            level = 0  # 一级章节
        hierarchy.append({"name": sec, "level": level})

    return hierarchy


# ────────────────────── 10. 动画效果（详细） ──────────────────────

def _extract_animations(zf: zipfile.ZipFile) -> list:
    """提取动画效果（v3.0: 详细提取预设、时序、触发、路径）"""
    animations = []
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    anim_counter = Counter()
    trigger_counter = Counter()
    duration_values = []
    delay_values = []
    motion_paths = []
    anim_details = []  # 详细动画信息

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")

            if "<p:timing>" not in xml and "<timing>" not in xml:
                continue

            dom = defusedxml.minidom.parseString(xml)
            timing_nodes = dom.getElementsByTagName("p:timing")
            if not timing_nodes:
                continue

            # 提取 animEffect 的 prstTransition（具体预设效果名）
            for prst_m in re.finditer(r'<p:animEffect[^>]*prstTransition="([^"]*)"', xml):
                anim_counter[prst_m.group(1)] += 1

            # 提取 transition (in/out)
            for trans_m in re.finditer(r'<p:animEffect[^>]*transition="([^"]*)"', xml):
                anim_counter[f"transition:{trans_m.group(1)}"] += 1

            # 提取 anim 节点（属性动画）
            for anim_m in re.finditer(r'<p:anim[^>]*>(.*?)</p:anim>', xml, re.DOTALL):
                block = anim_m.group(0)
                attrName_m = re.search(r'attrName="([^"]*)"', block)
                if attrName_m:
                    anim_counter[f"anim:{attrName_m.group(1)}"] += 1
                dur_m = re.search(r'dur="(\d+)"', block)
                if dur_m:
                    duration_values.append(int(dur_m.group(1)))

            # 提取 animMotion（路径动画）
            for motion_m in re.finditer(r'<p:animMotion[^>]*path="([^"]*)"', xml):
                motion_paths.append(motion_m.group(1)[:100])
                anim_counter["motion"] += 1

            # 提取 animRot（旋转动画）
            for rot_m in re.finditer(r'<p:animRot[^>]*>(.*?)</p:animRot>', xml, re.DOTALL):
                anim_counter["rotation"] += 1

            # 提取 animScale（缩放动画）
            for scale_m in re.finditer(r'<p:animScale[^>]*>(.*?)</p:animScale>', xml, re.DOTALL):
                anim_counter["scale"] += 1

            # 提取 animClr（颜色动画）
            for clr_m in re.finditer(r'<p:animClr[^>]*>(.*?)</p:animClr>', xml, re.DOTALL):
                anim_counter["color"] += 1

            # 提取触发方式
            if '<p:click' in xml:
                trigger_counter["on_click"] += 1
            if 'afterPrevious' in xml:
                trigger_counter["after_previous"] += 1
            if 'withPrevious' in xml:
                trigger_counter["with_previous"] += 1

            # 提取延迟
            for delay_m in re.finditer(r'delay="(\d+)"', xml):
                delay_values.append(int(delay_m.group(1)))

        except Exception:
            continue

    # 汇总
    for anim_type, count in anim_counter.most_common(10):
        animations.append({
            "type": anim_type,
            "frequency": count,
        })

    if trigger_counter:
        trigger_info = dict(trigger_counter.most_common())
        animations.append({"_meta_trigger": trigger_info})
    if duration_values:
        avg_dur = sum(duration_values) / len(duration_values)
        animations.append({"_meta_avg_duration_ms": round(avg_dur)})
    if delay_values:
        avg_delay = sum(delay_values) / len(delay_values)
        animations.append({"_meta_avg_delay_ms": round(avg_delay)})
    if motion_paths:
        animations.append({"_meta_motion_paths": len(motion_paths)})

    return animations


# ────────────────────── 11. 转场效果 ──────────────────────

def _extract_transitions(zf: zipfile.ZipFile) -> dict:
    """提取转场效果"""
    transitions = []
    slide_files = sorted([n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)])

    trans_counter = Counter()
    speed_counter = Counter()
    has_advance_time = False
    advance_time_values = []

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            for tag in ["p:transition", "transition"]:
                nodes = dom.getElementsByTagName(tag)
                for node in nodes:
                    trans_type = "unknown"
                    speed = "med"

                    for child in node.childNodes:
                        if child.nodeType != child.ELEMENT_NODE:
                            continue
                        ctag = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
                        trans_type = ctag

                    speed_attr = node.getAttribute("spd")
                    if speed_attr:
                        speed = speed_attr
                    speed_counter[speed] += 1
                    trans_counter[trans_type] += 1

                    # 自动换片时间
                    advTm = node.getAttribute("advTm")
                    if advTm:
                        has_advance_time = True
                        advance_time_values.append(int(advTm))

        except Exception:
            continue

    result = {"details": [], "default": "none", "duration_ms": 700}

    if trans_counter:
        result["default"] = trans_counter.most_common(1)[0][0]
        for t, c in trans_counter.most_common(5):
            result["details"].append({"type": t, "count": c})

    if speed_counter:
        most_common_speed = speed_counter.most_common(1)[0][0]
        speed_ms = {"slow": 1500, "med": 700, "fast": 300}
        result["duration_ms"] = speed_ms.get(most_common_speed, 700)

    if advance_time_values:
        avg_advance = sum(advance_time_values) / len(advance_time_values)
        result["auto_advance_ms"] = round(avg_advance)

    return result


# ────────────────────── 12. 母版/版式关系 ──────────────────────

def _extract_master_layouts(zf: zipfile.ZipFile) -> dict:
    """提取母版和版式信息"""
    result = {
        "masters": [],
        "layouts": [],
    }

    # 提取 slideMaster 信息
    master_pattern = re.compile(r"^ppt/slideMasters/slideMaster(\d+)\.xml$")
    for name in zf.namelist():
        m = master_pattern.match(name)
        if m:
            try:
                xml = zf.read(name).decode("utf-8")
                placeholders = []
                for ph_m in re.finditer(r'<p:ph[^>]*type="([^"]*)"[^>]*idx="(\d+)"', xml):
                    placeholders.append({"type": ph_m.group(1), "idx": int(ph_m.group(2))})
                # 也检查只有type没有idx的
                for ph_m in re.finditer(r'<p:ph[^>]*type="([^"]*)"', xml):
                    ph_type = ph_m.group(1)
                    if not any(p["type"] == ph_type for p in placeholders):
                        placeholders.append({"type": ph_type, "idx": -1})
                result["masters"].append({
                    "index": int(m.group(1)),
                    "placeholders": placeholders[:10],
                })
            except Exception:
                pass

    # 提取 slideLayout 信息（包含占位符位置）
    layout_pattern = re.compile(r"^ppt/slideLayouts/slideLayout(\d+)\.xml$")
    for name in zf.namelist():
        m = layout_pattern.match(name)
        if m:
            try:
                xml = zf.read(name).decode("utf-8")
                name_m = re.search(r'<p:cSld\s+name="([^"]*)"', xml)
                layout_name = name_m.group(1) if name_m else f"Layout {m.group(1)}"
                placeholders = []
                for ph_m in re.finditer(r'<p:ph[^>]*type="([^"]*)"[^>]*idx="(\d+)"', xml):
                    ph_info = {"type": ph_m.group(1), "idx": int(ph_m.group(2))}
                    placeholders.append(ph_info)
                # 提取占位符位置
                dom = defusedxml.minidom.parseString(xml)
                for sp in dom.getElementsByTagName("p:sp"):
                    ph_nodes = sp.getElementsByTagName("p:ph")
                    if ph_nodes:
                        ph_type = ph_nodes[0].getAttribute("type") or "body"
                        xfrm = sp.getElementsByTagName("a:xfrm")
                        if xfrm:
                            off = xfrm[0].getElementsByTagName("a:off")
                            ext = xfrm[0].getElementsByTagName("a:ext")
                            if off and ext:
                                x = int(off[0].getAttribute("x") or 0)
                                y = int(off[0].getAttribute("y") or 0)
                                cx = int(ext[0].getAttribute("cx") or 0)
                                cy = int(ext[0].getAttribute("cy") or 0)
                                for p in placeholders:
                                    if p["type"] == ph_type:
                                        p["position"] = {
                                            "x_in": round(x / EMU_PER_INCH, 2),
                                            "y_in": round(y / EMU_PER_INCH, 2),
                                            "w_in": round(cx / EMU_PER_INCH, 2),
                                            "h_in": round(cy / EMU_PER_INCH, 2),
                                        }
                                        break

                result["layouts"].append({
                    "index": int(m.group(1)),
                    "name": layout_name,
                    "placeholders": placeholders[:10],
                })
            except Exception:
                pass

    return result


# ────────────────────── 13. 表格和图表样式 ──────────────────────

def _extract_table_chart_styles(zf: zipfile.ZipFile) -> dict:
    """提取表格和图表样式"""
    result = {
        "tables": [],
        "charts": [],
    }

    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)

            # 查找表格 (a:tbl)
            for tbl in dom.getElementsByTagName("a:tbl"):
                table_info = {"rows": 0, "cols": 0, "style": {}}

                rows = tbl.getElementsByTagName("a:tr")
                table_info["rows"] = len(rows)
                if rows:
                    cols = rows[0].getElementsByTagName("a:tc")
                    table_info["cols"] = len(cols)

                tblPr = tbl.getElementsByTagName("a:tblPr")
                if tblPr:
                    bandRow = tblPr[0].getAttribute("bandRow")
                    table_info["style"]["bandRow"] = bandRow == "1" if bandRow else False
                    bandCol = tblPr[0].getAttribute("bandCol")
                    table_info["style"]["bandCol"] = bandCol == "1" if bandCol else False
                    firstRow = tblPr[0].getAttribute("firstRow")
                    table_info["style"]["firstRow"] = firstRow == "1" if firstRow else False

                # 表格边框颜色
                for tcStyle in tbl.getElementsByTagName("a:tcStyle"):
                    for border in ["a:tcBdr", "a:tblBdr"]:
                        for bdr in tcStyle.getElementsByTagName(border):
                            for srgb in bdr.getElementsByTagName("a:srgbClr"):
                                val = srgb.getAttribute("val")
                                if val:
                                    table_info["style"]["border_color"] = val.upper()

                # 交替行颜色
                row_colors = []
                for tc in tbl.getElementsByTagName("a:tc"):
                    for fill in tc.getElementsByTagName("a:solidFill"):
                        for srgb in fill.getElementsByTagName("a:srgbClr"):
                            val = srgb.getAttribute("val")
                            if val:
                                row_colors.append(val.upper())
                if row_colors:
                    # 去重保留前5种
                    table_info["style"]["row_colors"] = list(dict.fromkeys(row_colors))[:5]

                result["tables"].append(table_info)

            # 查找图表 (通过 graphicFrame + chart relationship)
            for gf in dom.getElementsByTagName("p:graphicFrame"):
                has_tbl = len(gf.getElementsByTagName("a:tbl")) > 0
                if not has_tbl:
                    # 检查是否有图表数据
                    graphicData = gf.getElementsByTagName("a:graphicData")
                    if graphicData:
                        uri = graphicData[0].getAttribute("uri") or ""
                        if "chart" in uri.lower():
                            result["charts"].append({"type": "chart", "slide": sf})
                        elif "diagram" in uri.lower():
                            result["charts"].append({"type": "smartart", "slide": sf})

        except Exception:
            continue

    return result


# ────────────────────── 辅助函数 ──────────────────────

def _extract_elements_positions(dom) -> list:
    """从spTree中提取元素位置信息（EMU原始值，用于兼容）"""
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
        xfrm_nodes = sp.getElementsByTagName("a:xfrm")
        if xfrm_nodes:
            xfrm = xfrm_nodes[0]
            off = xfrm.getElementsByTagName("a:off")
            ext = xfrm.getElementsByTagName("a:ext")
            if off:
                elem["x"] = int(off[0].getAttribute("x") or 0)
                elem["y"] = int(off[0].getAttribute("y") or 0)
            if ext:
                elem["w"] = int(ext[0].getAttribute("cx") or 0)
                elem["h"] = int(ext[0].getAttribute("cy") or 0)

        t_nodes = sp.getElementsByTagName("a:t")
        if t_nodes and t_nodes[0].firstChild:
            text = t_nodes[0].firstChild.nodeValue
            if text and len(text.strip()) > 0:
                elem["text"] = text.strip()[:50]

        elements.append(elem)

    return elements


def _extract_bg_colors_with_shapes(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> list:
    """提取背景色"""
    bg_data = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)
            for tag in ["p:bg", "bg"]:
                for bg in dom.getElementsByTagName(tag):
                    for fill in bg.getElementsByTagName("a:solidFill"):
                        for clr in fill.getElementsByTagName("a:srgbClr"):
                            val = clr.getAttribute("val")
                            if val and len(val) == 6:
                                bg_data.append((val.upper(), slide_w * slide_h))

            # 也检查渐变背景
            for tag in ["p:bg", "bg"]:
                for bg in dom.getElementsByTagName(tag):
                    for grad in bg.getElementsByTagName("a:gradFill"):
                        gsLst = grad.getElementsByTagName("a:gsLst")
                        if gsLst:
                            for gs in gsLst[0].getElementsByTagName("a:gs"):
                                for srgb in gs.getElementsByTagName("a:srgbClr"):
                                    val = srgb.getAttribute("val")
                                    if val and len(val) == 6:
                                        bg_data.append((val.upper(), slide_w * slide_h // 2))

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
                if area < full_area * 0.8:
                    continue
                for fill_tag in ["a:solidFill"]:
                    for fill in sp.getElementsByTagName(fill_tag):
                        for clr in fill.getElementsByTagName("a:srgbClr"):
                            val = clr.getAttribute("val")
                            if val and len(val) == 6:
                                bg_data.append((val.upper(), area))
        except Exception:
            continue

    return bg_data


def _extract_shape_fill_data(zf: zipfile.ZipFile, slide_w: int, slide_h: int) -> list:
    """提取形状填充色数据"""
    data = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            dom = defusedxml.minidom.parseString(xml)
            for sp in dom.getElementsByTagName("p:sp"):
                xfrm = sp.getElementsByTagName("a:xfrm")
                if not xfrm:
                    continue
                ext = xfrm[0].getElementsByTagName("a:ext")
                if not ext:
                    continue
                cx = int(ext[0].getAttribute("cx") or 0)
                cy = int(ext[0].getAttribute("cy") or 0)
                area = cx * cy
                for fill in sp.getElementsByTagName("a:solidFill"):
                    for clr in fill.getElementsByTagName("a:srgbClr"):
                        val = clr.getAttribute("val")
                        if val and len(val) == 6:
                            data.append((val.upper(), area))
        except Exception:
            continue

    return data


def _is_neutral_gray(hex_color: str) -> bool:
    """判断是否为中性灰色（饱和度极低）"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        mx, mn = max(r, g, b), min(r, g, b)
        if mx - mn <= 15:
            return True
        return False
    except Exception:
        return False


def _build_scheme_color_map(zf: zipfile.ZipFile) -> dict:
    """从theme1.xml构建scheme颜色映射表（v3.0: 支持sysClr的lastClr）"""
    scheme_map = {}
    theme_path = "ppt/theme/theme1.xml"
    if theme_path not in zf.namelist():
        return scheme_map
    try:
        theme_xml = zf.read(theme_path).decode("utf-8")
        dom = defusedxml.minidom.parseString(theme_xml)
        clr_schemes = dom.getElementsByTagName("a:clrScheme")
        if not clr_schemes:
            return scheme_map
        scheme = clr_schemes[0]
        for child in scheme.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            role = child.tagName.split(":")[-1] if ":" in child.tagName else child.tagName
            for srgb in child.getElementsByTagName("a:srgbClr"):
                val = srgb.getAttribute("val")
                if val and len(val) == 6:
                    scheme_map[role] = val.upper()
                    break
            else:
                for sys_clr in child.getElementsByTagName("a:sysClr"):
                    val = sys_clr.getAttribute("lastClr")
                    if val and len(val) == 6:
                        scheme_map[role] = val.upper()
                        break
    except Exception:
        pass
    return scheme_map


def _color_saturation(hex_color: str) -> float:
    """计算颜色饱和度"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == 0:
            return 0.0
        return (mx - mn) / mx
    except Exception:
        return 0.0


def _color_luminance(hex_color: str) -> float:
    """计算颜色亮度"""
    try:
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255
    except Exception:
        return 0.5


def _extract_text_color_data(zf: zipfile.ZipFile, scheme_map: dict = None) -> list:
    """提取文本颜色数据"""
    data = []
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    slide_files = sorted([n for n in zf.namelist() if slide_pattern.match(n)])

    for sf in slide_files:
        try:
            xml = zf.read(sf).decode("utf-8")
            for r_match in re.finditer(r'<a:r>.*?</a:r>', xml, re.DOTALL):
                block = r_match.group(0)
                # srgbClr
                for srgb_m in re.finditer(r'<a:srgbClr[^>]*val="([^"]*)"', block):
                    val = srgb_m.group(1)
                    if val and len(val) == 6:
                        data.append((val.upper(), 1))
                # schemeClr
                if scheme_map:
                    for sclr_m in re.finditer(r'<a:schemeClr[^>]*val="([^"]*)"', block):
                        ref = sclr_m.group(1)
                        color = scheme_map.get(ref)
                        if color:
                            data.append((color, 1))
        except Exception:
            continue
    return data


def _extract_text_colors(zf: zipfile.ZipFile) -> list:
    """提取文本颜色列表"""
    colors = []
    scheme_map = _build_scheme_color_map(zf)
    for col, freq in _extract_text_color_data(zf, scheme_map):
        colors.append(col)
    return colors


def _is_dark_color(hex_color: str) -> bool:
    """判断是否为深色"""
    return _color_luminance(hex_color) < 0.5


def main():
    parser = argparse.ArgumentParser(description="从PPTX提取设计规范 (v3.0)")
    parser.add_argument("input", help="输入PPTX文件路径")
    parser.add_argument("output", help="输出spec.json路径")
    parser.add_argument("--theme", help="主题名称", default=None)
    args = parser.parse_args()

    try:
        spec = analyze_pptx(args.input, args.theme)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出摘要
    print(f"✅ 分析完成: {args.input}")
    print(f"   主题: {spec['theme']}")
    print(f"   版本: {spec.get('version', '1.0')}")
    print(f"   页数: {spec['meta']['slide_count_range'][0]}")
    print(f"   配色: 主色={spec['colors']['primary']}, 辅色={spec['colors']['secondary']}, 强调色={spec['colors']['accent']}")
    fonts = spec.get('fonts', {})
    title_font = fonts.get('title', {})
    body_font = fonts.get('body', {})
    print(f"   字体: 标题={title_font.get('name', '?')}({title_font.get('ea_name', '?')}) {title_font.get('size', '?')}pt, 正文={body_font.get('name', '?')}({body_font.get('ea_name', '?')}) {body_font.get('size', '?')}pt")
    layout_pats = spec.get('layout', {}).get('patterns', [])
    print(f"   布局模式: {', '.join(lp['name'] for lp in layout_pats)}")
    print(f"   渐变: {len(spec.get('gradients', []))}种")
    deco = spec.get('decorations', {})
    print(f"   装饰元素: {len(deco.get('shapes', []))}种形状, 页码={'有' if deco.get('page_numbers') else '无'}, Logo={'有' if deco.get('logo_areas') else '无'}")
    img_style = spec.get('image_style', {})
    print(f"   图片: {img_style.get('count', 0)}张, 风格={img_style.get('layout_type', '?')}, 位置偏好={img_style.get('position_preference', '?')}")
    print(f"   目录: {'有' if spec['toc_structure']['has_toc'] else '无'}")
    print(f"   转场: {spec['animations']['default_transition']}")
    print(f"   动画: {len(spec['animations']['element_animations'])}种")
    print(f"   边距: {spec.get('layout', {}).get('margins', {})}")
    print(f"   排版: 行距={spec.get('typography', {}).get('line_spacing', '?')}, 对齐={spec.get('typography', {}).get('alignment', '?')}")
    ts = spec.get('text_styles', {})
    print(f"   列表: {ts.get('list', {}).get('default_type', '?')}")
    print(f"   文字效果: {len(ts.get('text_effects', []))}种")
    ml = spec.get('master_layouts', {})
    print(f"   母版: {len(ml.get('masters', []))}个, 版式: {len(ml.get('layouts', []))}种")
    tc = spec.get('table_chart_styles', {})
    print(f"   表格: {len(tc.get('tables', []))}个, 图表: {len(tc.get('charts', []))}个")
    print(f"   输出: {args.output}")


if __name__ == "__main__":
    main()
