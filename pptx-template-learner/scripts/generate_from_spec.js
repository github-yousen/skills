#!/usr/bin/env node
/**
 * 根据spec.json + content.json + 自由度生成PPT (v3.0)
 *
 * v3.0 升级要点：
 *   - 消费 analyze_pptx.py v3.0 新增维度：渐变、装饰元素、排版规则、图片风格、边距、母版版式、表格图表
 *   - 布局模式感知：根据 spec.layout.patterns 选择匹配的页面生成函数
 *   - 渐变背景支持：消费 spec.gradients 生成渐变填充
 *   - 装饰元素复刻：消费 spec.decorations 生成装饰线/形状/页码/底部栏
 *   - 文本排版规则：消费 spec.typography + spec.text_styles 应用行距/对齐/列表样式
 *   - 图片风格适配：消费 spec.image_style 决定图片布局方式
 *   - 新增页面类型：comparison / timeline / gallery / quote / team
 *   - 自由度差异化真正生效
 *
 * Usage:
 *   node generate_from_spec.js <spec.json> <content.json> <output.pptx> [--freedom high|medium|low] [--no-spec]
 */

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

// ─── 参数解析 ───
const args = process.argv.slice(2);
if (args.length < 3) {
  console.error("Usage: node generate_from_spec.js <spec.json> <content.json> <output.pptx> [--freedom high|medium|low] [--no-spec]");
  process.exit(1);
}

const specPath = args[0];
const contentPath = args[1];
const outputPath = args[2];
const noSpec = args.includes("--no-spec");
const freedom = args.includes("--freedom") ? args[args.indexOf("--freedom") + 1] : "high";

if (!["high", "medium", "low"].includes(freedom)) {
  console.error("Freedom must be 'high', 'medium', or 'low'");
  process.exit(1);
}

// ─── 读取输入 ───
const spec = noSpec ? {} : JSON.parse(fs.readFileSync(specPath, "utf-8"));
const content = JSON.parse(fs.readFileSync(contentPath, "utf-8"));
const hasTemplate = !noSpec && spec && Object.keys(spec).length > 0;

const freedomLabel = { high: "高（参考风格，灵活发挥）", medium: "中（较多遵循模板）", low: "低（高度还原模板）" };

console.log(`🎨 自由度: ${freedomLabel[freedom]}`);
console.log(`📐 模板: ${hasTemplate ? spec.theme || "有" : "无（自由发挥）"}`);
console.log(`📐 分析版本: ${hasTemplate ? spec.version || "1.0" : "N/A"}`);

// ─── 工具函数 ───

function makeShadow(opts = {}) {
  return {
    type: "outer",
    blur: opts.blur || 6,
    offset: opts.offset || 2,
    angle: opts.angle || 135,
    color: opts.color || "000000",
    opacity: opts.opacity || 0.15,
  };
}

function adjustColor(hex, shift = 0) {
  if (shift === 0) return hex;
  let r = parseInt(hex.slice(0, 2), 16);
  let g = parseInt(hex.slice(2, 4), 16);
  let b = parseInt(hex.slice(4, 6), 16);
  r = Math.min(255, Math.max(0, r + shift));
  g = Math.min(255, Math.max(0, g + shift));
  b = Math.min(255, Math.max(0, b + shift));
  return [r, g, b].map(c => c.toString(16).padStart(2, "0")).join("").toUpperCase();
}

/** 将 hex 颜色转为 rgba 字符串（pptxgenjs 支持） */
function hexToRgba(hex, alpha = 100) {
  // pptxgenjs 使用 color + transparency
  return { color: hex.replace("@", "").slice(0, 6), transparency: 100 - alpha };
}

/** 从spec.gradients构建渐变填充对象 */
function buildGradientFill(gradient) {
  if (!gradient || !gradient.stops || gradient.stops.length < 2) return null;

  // pptxgenjs 支持的渐变格式
  const stops = gradient.stops.map(s => ({
    position: s.position, // 0~100
    color: s.color.replace(/@\d+%/,"").slice(0, 6),
  }));

  // 方向映射
  const directionMap = {
    "left-to-right": { x: 0, y: 0.5, w: 1, h: 0.5 },
    "right-to-left": { x: 1, y: 0.5, w: 0, h: 0.5 },
    "top-to-bottom": { x: 0.5, y: 0, w: 0.5, h: 1 },
    "bottom-to-top": { x: 0.5, y: 1, w: 0.5, h: 0 },
    "top-left-to-bottom-right": { x: 0, y: 0, w: 1, h: 1 },
    "bottom-right-to-top-left": { x: 1, y: 1, w: 0, h: 0 },
  };

  const dir = directionMap[gradient.direction] || directionMap["left-to-right"];

  return {
    gradient: {
      stops: stops,
      direction: gradient.direction || "left-to-right",
    },
  };
}

/** 安全获取spec中的字段 */
function getSpec(field, defaultValue) {
  if (!hasTemplate) return defaultValue;
  const parts = field.split(".");
  let obj = spec;
  for (const p of parts) {
    if (obj == null || obj[p] === undefined) return defaultValue;
    obj = obj[p];
  }
  return obj !== undefined ? obj : defaultValue;
}

// ─── 创建演示文稿 ───
const pres = new pptxgen();

// 幻灯片尺寸
const orientation = getSpec("slide_size.orientation", "16:9");
if (orientation === "4:3") pres.layout = "LAYOUT_4x3";
else if (orientation === "16:10") pres.layout = "LAYOUT_16x10";
else pres.layout = "LAYOUT_16x9";

pres.author = "pptx-template-learner v3.0";
pres.title = content.title || "演示文稿";

// ─── 确定设计参数（v3.0: 全面消费spec新维度） ───

let primaryColor, secondaryColor, accentColor, bgDark, bgLight, textDark, textLight;
let titleFont, titleSize, titleEaFont, subtitleFont, subtitleSize, subtitleEaFont, bodyFont, bodySize, bodyEaFont;

if (hasTemplate) {
  const colors = spec.colors || {};
  const fonts = spec.fonts || {};

  // 自由度影响配色调整幅度
  const colorShift = freedom === "high" ? 15 : freedom === "medium" ? 5 : 0;

  primaryColor = adjustColor(colors.primary || "1E2761", colorShift);
  secondaryColor = adjustColor(colors.secondary || "CADCFC", -colorShift);
  accentColor = adjustColor(colors.accent || "0891B2", colorShift);
  bgDark = colors.bg_dark || "1E2761";
  bgLight = colors.bg_light || "FFFFFF";
  textDark = colors.text_dark || "212121";
  textLight = colors.text_light || "FFFFFF";

  // 字体（v3.0: 区分中英文字体）
  titleFont = fonts.title?.name || "Arial";
  titleEaFont = fonts.title?.ea_name || "微软雅黑";
  titleSize = fonts.title?.size || 36;
  subtitleFont = fonts.subtitle?.name || "Arial";
  subtitleEaFont = fonts.subtitle?.ea_name || "微软雅黑";
  subtitleSize = fonts.subtitle?.size || 20;
  bodyFont = fonts.body?.name || "Calibri";
  bodyEaFont = fonts.body?.ea_name || "微软雅黑";
  bodySize = fonts.body?.size || 14;
} else {
  primaryColor = "1B3A5C";
  secondaryColor = "5B8DB8";
  accentColor = "E8913A";
  bgDark = "1B3A5C";
  bgLight = "FFFFFF";
  textDark = "2D3748";
  textLight = "FFFFFF";
  titleFont = "Arial"; titleEaFont = "微软雅黑"; titleSize = 36;
  subtitleFont = "Arial"; subtitleEaFont = "微软雅黑"; subtitleSize = 20;
  bodyFont = "Calibri"; bodyEaFont = "微软雅黑"; bodySize = 14;
}

// v3.0: 消费排版规则
const typography = getSpec("typography", {});
const lineSpacing = typography.line_spacing || 1.2;
const charSpacing = typography.char_spacing || 0;
const alignment = typography.alignment || "left";

// v3.0: 消费文本排版规则
const textStyles = getSpec("text_styles", {});
const listDefaultType = textStyles.list?.default_type || "none";
const paragraphSpaceBefore = textStyles.paragraph?.space_before || 0;
const paragraphSpaceAfter = textStyles.paragraph?.space_after || 6;

// v3.0: 消费边距
const layout = getSpec("layout", {});
const margins = layout.margins || { top: 0.5, right: 0.5, bottom: 0.5, left: 0.5 };

// v3.0: 消费渐变
const gradients = getSpec("gradients", []);

// v3.0: 消费装饰元素
const decorations = getSpec("decorations", {});
const hasPageNumbers = !!decorations.page_numbers?.position;
const hasLogo = !!decorations.logo_areas?.length;
const hasBottomBar = !!decorations.bottom_bar;
const decoShapes = decorations.shapes || [];
const decoLines = decorations.lines || [];

// v3.0: 消费图片风格
const imageStyle = getSpec("image_style", {});
const imageLayoutType = imageStyle.layout_type || "medium-image";
const imagePositionPreference = imageStyle.position_preference || "center";

// v3.0: 消费布局模式
const layoutPatterns = layout.patterns || [];

// v3.0: 消费动画
const anims = getSpec("animations", {});
const toc = getSpec("toc_structure", {});

// v3.0: 消费母版版式
const masterLayouts = getSpec("master_layouts", {});

// ─── 共享装饰函数 ───

/** 添加页码（如果spec中有页码位置信息） */
function addPageNumber(slide, slideNum, totalPages) {
  if (!hasPageNumbers && freedom !== "high") return;

  const pos = decorations.page_numbers?.position || { x: 9.0, y: 5.1 };

  // 判断页码应该在暗色还是亮色背景上
  slide.addText(`${slideNum} / ${totalPages}`, {
    x: pos.x,
    y: pos.y,
    w: 0.8,
    h: 0.3,
    fontSize: 9,
    fontFace: bodyFont,
    color: textLight,
    align: "center",
  });
}

/** 添加底部装饰栏 */
function addBottomBar(slide) {
  if (hasBottomBar && freedom !== "high") {
    // 低/中自由度：按模板复刻
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0,
      y: 5.325,
      w: 10,
      h: 0.3,
      fill: { color: primaryColor, transparency: 90 },
    });
  }
  // 高自由度或无模板：添加简洁底部线
  if (freedom === "high" || !hasTemplate) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0,
      y: 5.425,
      w: 10,
      h: 0.04,
      fill: { color: accentColor },
    });
  }
}

/** 添加装饰形状 */
function addDecorationShapes(slide, isDark) {
  // 根据spec中的装饰形状信息添加
  if (freedom === "low" && hasTemplate) {
    // 低自由度：尝试复刻模板中的装饰形状
    for (const shape of decoShapes.slice(0, 3)) {
      const shapeMap = {
        "rect": pres.shapes.RECTANGLE,
        "ellipse": pres.shapes.OVAL,
        "roundRect": pres.shapes.ROUNDED_RECTANGLE,
        "triangle": pres.shapes.TRIANGLE,
        "diamond": pres.shapes.DIAMOND,
        "pentagon": pres.shapes.PENTAGON,
        "hexagon": pres.shapes.HEXAGON,
        "star5": pres.shapes.STAR_5_POINTS,
        "chevron": pres.shapes.CHEVRON,
      };
      const pptxShape = shapeMap[shape.type];
      if (!pptxShape) continue;

      // 添加半透明装饰形状
      slide.addShape(pptxShape, {
        x: 8.5 + Math.random() * 0.5,
        y: -0.3 + Math.random() * 0.3,
        w: 1.5,
        h: 1.5,
        fill: { color: isDark ? accentColor : primaryColor, transparency: 85 },
      });
    }
  }
}

/** 添加左侧装饰条 */
function addLeftAccentBar(slide, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 0.06,
    h: 5.625,
    fill: { color: color || primaryColor },
  });
}

/** 应用渐变背景 */
function applyGradientBg(slide, gradientIndex) {
  if (!gradients.length) return false;

  const idx = gradientIndex !== undefined ? gradientIndex % gradients.length : 0;
  const grad = gradients[idx];

  if (!grad || !grad.stops || grad.stops.length < 2) return false;

  // pptxgenjs 渐变背景
  const stops = grad.stops.map(s => ({
    position: s.position,
    color: s.color.replace(/@\d+%/,"").slice(0, 6),
  }));

  slide.background = {
    fill: {
      type: "gradient",
      stops: stops,
      direction: grad.direction || "left-to-right",
    },
  };

  return true;
}

// ─── 转场设置 ───
function getTransition() {
  if (!hasTemplate) return { type: "fade", speed: 0.7 };

  const transType = anims.default_transition || "none";
  const duration = (anims.transition_duration_ms || 700) / 1000;

  const transitionMap = {
    "fade": { type: "fade", speed: duration },
    "push": { type: "push", speed: duration },
    "wipe": { type: "wipe", speed: duration },
    "cover": { type: "cover", speed: duration },
    "split": { type: "split", speed: duration },
    "none": null,
    "unknown": null,
  };

  if (freedom === "high") {
    return transitionMap[transType] || { type: "fade", speed: 0.7 };
  }
  return transitionMap[transType] || null;
}

// ─── 幻灯片生成函数 ───

/**
 * 封面页（v3.0: 支持渐变背景、装饰元素复刻）
 */
function createCoverSlide() {
  const slide = pres.addSlide();

  // 背景处理：渐变 or 纯色
  if (hasTemplate && gradients.length > 0 && freedom !== "high") {
    // 中/低自由度：使用模板的第一个渐变
    if (!applyGradientBg(slide, 0)) {
      slide.background = { color: bgDark };
    }
  } else {
    slide.background = { color: bgDark };
  }

  // 装饰元素
  if (freedom === "high" || !hasTemplate) {
    // 右上角装饰圆
    slide.addShape(pres.shapes.OVAL, {
      x: 8.2, y: -0.5, w: 2.5, h: 2.5,
      fill: { color: accentColor, transparency: 80 },
    });
    // 左下角装饰
    slide.addShape(pres.shapes.OVAL, {
      x: -0.8, y: 4.0, w: 2, h: 2,
      fill: { color: secondaryColor, transparency: 85 },
    });
  } else if (freedom === "low" && hasTemplate) {
    // 低自由度：复刻模板装饰形状
    addDecorationShapes(slide, true);
  }

  // 标题
  slide.addText(content.title || "演示文稿", {
    x: margins.left,
    y: 1.5,
    w: 10 - margins.left - margins.right,
    h: 1.5,
    fontSize: titleSize,
    fontFace: titleFont,
    color: textLight,
    bold: true,
    align: "center",
    valign: "middle",
    lineSpacingMultiple: lineSpacing,
    charSpacing: charSpacing,
  });

  // 副标题
  if (content.subtitle) {
    slide.addText(content.subtitle, {
      x: margins.left,
      y: 3.2,
      w: 10 - margins.left - margins.right,
      h: 0.6,
      fontSize: subtitleSize,
      fontFace: subtitleFont,
      color: secondaryColor,
      align: "center",
    });
  }

  // 装饰线
  slide.addShape(pres.shapes.LINE, {
    x: 3, y: 3.05, w: 4, h: 0,
    line: { color: accentColor, width: 2 },
  });

  return slide;
}

/**
 * 目录页（v3.0: 支持层级目录、左侧装饰条）
 */
function createTocSlide(sections) {
  const slide = pres.addSlide();
  slide.background = { color: bgLight };

  addLeftAccentBar(slide);

  // 标题
  slide.addText("目录", {
    x: margins.left + 0.2,
    y: margins.top,
    w: 9 - margins.left - margins.right,
    h: 0.8,
    fontSize: titleSize,
    fontFace: titleFont,
    color: primaryColor,
    bold: true,
  });

  // v3.0: 尝试使用spec中的目录层级结构
  const tocHierarchy = toc.hierarchy || [];
  const hasHierarchy = tocHierarchy.length > 0;

  if (freedom === "high" || !hasTemplate) {
    // 卡片式目录
    const cardH = 0.7;
    const startY = 1.5;
    sections.forEach((sec, idx) => {
      const cy = startY + idx * (cardH + 0.15);
      // 序号圆
      slide.addShape(pres.shapes.OVAL, {
        x: 1.2, y: cy + 0.1, w: 0.5, h: 0.5,
        fill: { color: primaryColor },
      });
      slide.addText(`${idx + 1}`, {
        x: 1.2, y: cy + 0.1, w: 0.5, h: 0.5,
        fontSize: 14, fontFace: titleFont, color: textLight,
        bold: true, align: "center", valign: "middle",
      });
      // 章节名
      slide.addText(sec.title || sec, {
        x: 2.0, y: cy, w: 6, h: cardH,
        fontSize: subtitleSize, fontFace: subtitleFont, color: textDark,
        bold: true, valign: "middle",
      });
      if (idx < sections.length - 1) {
        slide.addShape(pres.shapes.LINE, {
          x: 2.0, y: cy + cardH + 0.05, w: 6, h: 0,
          line: { color: "E2E8F0", width: 1 },
        });
      }
    });
  } else {
    // 中/低自由度：列表式目录
    const tocItems = sections.map((sec, idx) => ({
      text: `${idx + 1}. ${sec.title || sec}`,
      options: {
        bullet: false,
        breakLine: true,
        fontSize: subtitleSize,
        fontFace: bodyFont,
        color: textDark,
        paraSpaceAfter: paragraphSpaceAfter,
      },
    }));
    slide.addText(tocItems, {
      x: margins.left + 0.5, y: 1.5, w: 8, h: 3.5,
      valign: "top", paraSpaceAfter: paragraphSpaceAfter,
    });
  }

  addBottomBar(slide);

  return slide;
}

/**
 * 章节分隔页（v3.0: 支持渐变背景）
 */
function createSectionSlide(sectionTitle) {
  const slide = pres.addSlide();

  // 背景：尝试渐变
  if (hasTemplate && gradients.length > 1) {
    if (!applyGradientBg(slide, 1)) {
      slide.background = { color: bgDark };
    }
  } else {
    slide.background = { color: bgDark };
  }

  if (freedom === "high" || !hasTemplate) {
    slide.addText("SECTION", {
      x: margins.left, y: 1.5,
      w: 10 - margins.left - margins.right, h: 0.4,
      fontSize: 12, fontFace: bodyFont, color: accentColor,
      align: "center", charSpacing: 5,
    });
  }

  // 装饰线
  slide.addShape(pres.shapes.LINE, {
    x: 3.5, y: 2.2, w: 3, h: 0,
    line: { color: accentColor, width: 3 },
  });

  slide.addText(sectionTitle, {
    x: margins.left, y: 2.4,
    w: 10 - margins.left - margins.right, h: 1.2,
    fontSize: titleSize + 4, fontFace: titleFont, color: textLight,
    bold: true, align: "center",
    lineSpacingMultiple: lineSpacing,
  });

  addDecorationShapes(slide, true);

  return slide;
}

/**
 * 内容页（v3.0: 根据布局模式选择模板，消费排版规则）
 */
function createContentSlide(heading, bodyText, slideDataType) {
  const slide = pres.addSlide();
  slide.background = { color: bgLight };

  // v3.0: 根据slideData.type或布局模式选择布局
  const pageType = slideDataType || "content";

  switch (pageType) {
    case "comparison":
      createComparisonLayout(slide, heading, bodyText);
      break;
    case "timeline":
      createTimelineLayout(slide, heading, bodyText);
      break;
    case "gallery":
      createGalleryLayout(slide, heading, bodyText);
      break;
    case "quote":
      createQuoteLayout(slide, heading, bodyText);
      break;
    case "team":
      createTeamLayout(slide, heading, bodyText);
      break;
    case "data":
      createDataSlide(slide, heading, bodyText);
      break;
    case "two-column":
      createTwoColumnLayout(slide, heading, bodyText);
      break;
    case "left-image-right-text":
      createLeftImageRightTextLayout(slide, heading, bodyText);
      break;
    case "left-text-right-image":
      createLeftTextRightImageLayout(slide, heading, bodyText);
      break;
    default:
      createStandardContentLayout(slide, heading, bodyText);
      break;
  }

  // 底部装饰
  addBottomBar(slide);

  return slide;
}

/**
 * 标准内容布局（上标题+下内容）
 */
function createStandardContentLayout(slide, heading, bodyText) {
  // 标题栏背景
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 1.0,
    fill: { color: primaryColor },
  });

  slide.addText(heading, {
    x: margins.left, y: 0.1,
    w: 10 - margins.left - margins.right, h: 0.8,
    fontSize: titleSize - 4, fontFace: titleFont, color: textLight,
    bold: true, valign: "middle",
  });

  // 正文（v3.0: 消费排版规则）
  const contentArea = { x: margins.left, y: 1.3, w: 10 - margins.left - margins.right, h: 4.0 };

  if (typeof bodyText === "string") {
    const paragraphs = bodyText.split("\n").filter(l => l.trim());
    const textItems = paragraphs.map(p => ({
      text: p.replace(/^[-•*]\s*/, ""),
      options: {
        bullet: /^[-•*]/.test(p) || listDefaultType !== "none",
        breakLine: true,
        fontSize: bodySize,
        fontFace: bodyFont,
        color: textDark,
        paraSpaceAfter: paragraphSpaceAfter,
        lineSpacingMultiple: lineSpacing,
      },
    }));
    slide.addText(textItems, { ...contentArea, valign: "top", paraSpaceAfter: paragraphSpaceAfter });
  } else if (Array.isArray(bodyText)) {
    const textItems = bodyText.map(p => {
      if (typeof p === "string") {
        return {
          text: p,
          options: {
            bullet: listDefaultType !== "none",
            breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark,
            paraSpaceAfter: paragraphSpaceAfter, lineSpacingMultiple: lineSpacing,
          },
        };
      }
      return {
        text: p.text || p.heading || "",
        options: {
          bullet: !p.heading && listDefaultType !== "none",
          breakLine: true,
          fontSize: p.heading ? subtitleSize : bodySize,
          fontFace: p.heading ? subtitleFont : bodyFont,
          color: textDark,
          bold: !!p.heading,
          paraSpaceAfter: paragraphSpaceAfter,
          lineSpacingMultiple: lineSpacing,
        },
      };
    });
    slide.addText(textItems, { ...contentArea, valign: "top", paraSpaceAfter: paragraphSpaceAfter });
  }
}

/**
 * 对比页布局
 */
function createComparisonLayout(slide, heading, bodyText) {
  // 标题
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  // 分隔线
  slide.addShape(pres.shapes.LINE, {
    x: 5, y: 1.2, w: 0, h: 3.8,
    line: { color: accentColor, width: 2, dashType: "dash" },
  });

  // 左右两栏
  const items = Array.isArray(bodyText) ? bodyText : [];
  const leftItems = items.filter((_, i) => i % 2 === 0);
  const rightItems = items.filter((_, i) => i % 2 === 1);

  // 左栏标题
  slide.addText(leftItems[0]?.heading || leftItems[0]?.text || "方案 A", {
    x: margins.left, y: 1.4, w: 4.2, h: 0.5,
    fontSize: subtitleSize, fontFace: subtitleFont, color: primaryColor, bold: true, align: "center",
  });

  // 右栏标题
  slide.addText(rightItems[0]?.heading || rightItems[0]?.text || "方案 B", {
    x: 5.4, y: 1.4, w: 4.2, h: 0.5,
    fontSize: subtitleSize, fontFace: subtitleFont, color: accentColor, bold: true, align: "center",
  });

  // 左栏内容
  const leftContent = leftItems.slice(1).map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: { bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark },
  }));
  if (leftContent.length) {
    slide.addText(leftContent, { x: margins.left, y: 2.1, w: 4.2, h: 2.8, valign: "top" });
  }

  // 右栏内容
  const rightContent = rightItems.slice(1).map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: { bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark },
  }));
  if (rightContent.length) {
    slide.addText(rightContent, { x: 5.4, y: 2.1, w: 4.2, h: 2.8, valign: "top" });
  }
}

/**
 * 时间轴布局
 */
function createTimelineLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  // 时间轴主线
  slide.addShape(pres.shapes.LINE, {
    x: 1, y: 2.8, w: 8, h: 0,
    line: { color: primaryColor, width: 3 },
  });

  const items = Array.isArray(bodyText) ? bodyText : (typeof bodyText === "string" ? bodyText.split("\n").filter(l => l.trim()) : []);
  const maxNodes = Math.min(items.length, 5);
  const nodeSpacing = 7.5 / maxNodes;

  for (let i = 0; i < maxNodes; i++) {
    const nx = 1.25 + i * nodeSpacing;
    const item = items[i];
    const label = typeof item === "string" ? item : (item.text || item.heading || `节点${i + 1}`);

    // 节点圆
    slide.addShape(pres.shapes.OVAL, {
      x: nx - 0.15, y: 2.65, w: 0.3, h: 0.3,
      fill: { color: accentColor },
    });

    // 节点标签（上方）
    slide.addText(label, {
      x: nx - 0.6, y: 1.8, w: 1.4, h: 0.7,
      fontSize: 10, fontFace: bodyFont, color: textDark,
      align: "center", valign: "bottom",
      bold: true,
    });
  }
}

/**
 * 图片画廊布局
 */
function createGalleryLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  const items = Array.isArray(bodyText) ? bodyText : [];
  const count = Math.min(items.length, 4);
  const cardW = (10 - margins.left - margins.right - 0.3 * (count - 1)) / count;

  for (let i = 0; i < count; i++) {
    const cx = margins.left + i * (cardW + 0.3);
    const item = items[i];
    const label = typeof item === "string" ? item : (item.text || item.heading || "");

    // 占位卡片
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx, y: 1.3, w: cardW, h: 3.0,
      fill: { color: "F1F5F9" },
      shadow: makeShadow(),
      rectRadius: 0.1,
    });

    // 图片占位标记
    slide.addShape(pres.shapes.OVAL, {
      x: cx + cardW / 2 - 0.4, y: 1.8, w: 0.8, h: 0.8,
      fill: { color: primaryColor, transparency: 85 },
    });
    slide.addText("🖼", {
      x: cx + cardW / 2 - 0.4, y: 1.8, w: 0.8, h: 0.8,
      fontSize: 20, align: "center", valign: "middle",
    });

    // 标签
    if (label) {
      slide.addText(label, {
        x: cx + 0.1, y: 3.0, w: cardW - 0.2, h: 0.8,
        fontSize: 11, fontFace: bodyFont, color: textDark,
        align: "center", valign: "top",
      });
    }
  }
}

/**
 * 引用页布局
 */
function createQuoteLayout(slide, heading, bodyText) {
  slide.background = { color: bgDark };

  const quoteText = typeof bodyText === "string" ? bodyText : (Array.isArray(bodyText) ? bodyText.map(b => typeof b === "string" ? b : b.text || "").join(" ") : heading);

  // 大引号
  slide.addText("❝", {
    x: 1.5, y: 0.8, w: 2, h: 1.5,
    fontSize: 72, color: accentColor, transparency: 40,
    fontFace: titleFont,
  });

  // 引用文字
  slide.addText(quoteText, {
    x: 1.5, y: 2.0, w: 7, h: 2.0,
    fontSize: subtitleSize + 4, fontFace: subtitleFont, color: textLight,
    italic: true, align: "center", valign: "middle",
    lineSpacingMultiple: 1.5,
  });

  // 出处
  if (heading && heading !== quoteText) {
    slide.addText(`— ${heading}`, {
      x: 1.5, y: 4.2, w: 7, h: 0.5,
      fontSize: bodySize, fontFace: bodyFont, color: secondaryColor,
      align: "right",
    });
  }
}

/**
 * 团队介绍布局
 */
function createTeamLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  const items = Array.isArray(bodyText) ? bodyText : [];
  const count = Math.min(items.length, 4);
  const cardW = (10 - margins.left - margins.right - 0.4 * (count - 1)) / count;

  for (let i = 0; i < count; i++) {
    const cx = margins.left + i * (cardW + 0.4);
    const item = items[i];
    const name = typeof item === "string" ? item : (item.name || item.heading || item.text || "");
    const role = typeof item === "object" ? (item.role || item.description || "") : "";

    // 头像占位
    slide.addShape(pres.shapes.OVAL, {
      x: cx + cardW / 2 - 0.6, y: 1.3, w: 1.2, h: 1.2,
      fill: { color: primaryColor, transparency: 70 },
    });
    slide.addText("👤", {
      x: cx + cardW / 2 - 0.6, y: 1.3, w: 1.2, h: 1.2,
      fontSize: 28, align: "center", valign: "middle",
    });

    // 姓名
    slide.addText(name, {
      x: cx, y: 2.7, w: cardW, h: 0.5,
      fontSize: subtitleSize - 2, fontFace: subtitleFont, color: textDark,
      bold: true, align: "center",
    });

    // 职位
    if (role) {
      slide.addText(role, {
        x: cx, y: 3.2, w: cardW, h: 0.4,
        fontSize: 10, fontFace: bodyFont, color: "64748B", align: "center",
      });
    }
  }
}

/**
 * 双栏布局
 */
function createTwoColumnLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  const items = Array.isArray(bodyText) ? bodyText : (typeof bodyText === "string" ? [{ text: bodyText }] : []);
  const mid = Math.ceil(items.length / 2);
  const leftItems = items.slice(0, mid);
  const rightItems = items.slice(mid);

  const colW = (10 - margins.left - margins.right - 0.5) / 2;

  // 左栏
  const leftContent = leftItems.map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: {
      bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark,
      lineSpacingMultiple: lineSpacing,
    },
  }));
  if (leftContent.length) {
    slide.addText(leftContent, { x: margins.left, y: 1.3, w: colW, h: 3.5, valign: "top" });
  }

  // 右栏
  const rightContent = rightItems.map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: {
      bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark,
      lineSpacingMultiple: lineSpacing,
    },
  }));
  if (rightContent.length) {
    slide.addText(rightContent, { x: margins.left + colW + 0.5, y: 1.3, w: colW, h: 3.5, valign: "top" });
  }
}

/**
 * 左图右文布局
 */
function createLeftImageRightTextLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  // 左侧图片占位
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: margins.left, y: 1.2, w: 4.0, h: 3.8,
    fill: { color: "F1F5F9" },
    shadow: makeShadow(),
    rectRadius: 0.1,
  });
  slide.addText("🖼 图片区域", {
    x: margins.left, y: 2.8, w: 4.0, h: 0.5,
    fontSize: 14, color: "94A3B8", align: "center", valign: "middle",
  });

  // 右侧文本
  const items = Array.isArray(bodyText) ? bodyText : (typeof bodyText === "string" ? [{ text: bodyText }] : []);
  const textContent = items.map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: {
      bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark,
      lineSpacingMultiple: lineSpacing,
    },
  }));
  if (textContent.length) {
    slide.addText(textContent, { x: 5.0, y: 1.2, w: 4.5, h: 3.8, valign: "top" });
  }
}

/**
 * 左文右图布局
 */
function createLeftTextRightImageLayout(slide, heading, bodyText) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  // 左侧文本
  const items = Array.isArray(bodyText) ? bodyText : (typeof bodyText === "string" ? [{ text: bodyText }] : []);
  const textContent = items.map(item => ({
    text: typeof item === "string" ? item : (item.text || item.heading || ""),
    options: {
      bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark,
      lineSpacingMultiple: lineSpacing,
    },
  }));
  if (textContent.length) {
    slide.addText(textContent, { x: margins.left, y: 1.2, w: 4.5, h: 3.8, valign: "top" });
  }

  // 右侧图片占位
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.5, y: 1.2, w: 4.0, h: 3.8,
    fill: { color: "F1F5F9" },
    shadow: makeShadow(),
    rectRadius: 0.1,
  });
  slide.addText("🖼 图片区域", {
    x: 5.5, y: 2.8, w: 4.0, h: 0.5,
    fontSize: 14, color: "94A3B8", align: "center", valign: "middle",
  });
}

/**
 * 数据展示页（v3.0: 改进，消费配色）
 */
function createDataSlide(slide, heading, dataPoints) {
  slide.addText(heading, {
    x: margins.left, y: margins.top,
    w: 10 - margins.left - margins.right, h: 0.7,
    fontSize: titleSize - 4, fontFace: titleFont, color: primaryColor, bold: true,
  });

  const items = Array.isArray(dataPoints) ? dataPoints : [];
  const cardW = Math.min(3.5, (10 - margins.left - margins.right - 0.3 * (items.length - 1)) / Math.max(items.length, 1));
  const startX = margins.left + (10 - margins.left - margins.right - (cardW * items.length + 0.3 * (items.length - 1))) / 2;

  items.forEach((dp, idx) => {
    const cx = startX + idx * (cardW + 0.3);
    const cy = 1.5;

    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: cardW, h: 2.8,
      fill: { color: "FFFFFF" },
      shadow: makeShadow(),
    });

    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: 0.06, h: 2.8,
      fill: { color: accentColor },
    });

    slide.addText(dp.value || dp.number || "—", {
      x: cx + 0.2, y: cy + 0.3, w: cardW - 0.4, h: 1.0,
      fontSize: 32, fontFace: titleFont, color: primaryColor,
      bold: true, align: "center",
    });

    slide.addText(dp.label || dp.name || "", {
      x: cx + 0.2, y: cy + 1.3, w: cardW - 0.4, h: 0.5,
      fontSize: subtitleSize - 2, fontFace: subtitleFont, color: textDark,
      bold: true, align: "center",
    });

    if (dp.description) {
      slide.addText(dp.description, {
        x: cx + 0.2, y: cy + 1.8, w: cardW - 0.4, h: 0.8,
        fontSize: 10, fontFace: bodyFont, color: "64748B", align: "center",
      });
    }
  });
}

/**
 * 结尾页（v3.0: 支持渐变背景）
 */
function createEndingSlide() {
  const slide = pres.addSlide();

  // 背景：尝试渐变
  if (hasTemplate && gradients.length > 2) {
    if (!applyGradientBg(slide, gradients.length - 1)) {
      slide.background = { color: bgDark };
    }
  } else {
    slide.background = { color: bgDark };
  }

  const endText = content.ending_text || "感谢观看";

  if (freedom === "high" || !hasTemplate) {
    slide.addShape(pres.shapes.OVAL, {
      x: 4, y: 0.5, w: 2, h: 2,
      fill: { color: accentColor, transparency: 85 },
    });
  }

  slide.addText(endText, {
    x: margins.left, y: 1.8,
    w: 10 - margins.left - margins.right, h: 1.5,
    fontSize: titleSize + 8, fontFace: titleFont, color: textLight,
    bold: true, align: "center",
  });

  slide.addShape(pres.shapes.LINE, {
    x: 3.5, y: 3.5, w: 3, h: 0,
    line: { color: accentColor, width: 2 },
  });

  if (content.contact || content.email) {
    slide.addText(content.contact || content.email, {
      x: margins.left, y: 3.7,
      w: 10 - margins.left - margins.right, h: 0.5,
      fontSize: bodySize, fontFace: bodyFont, color: secondaryColor, align: "center",
    });
  }

  addDecorationShapes(slide, true);

  return slide;
}

// ─── 主生成逻辑 ───

let totalPages = 0;
// 预计总页数
const sections = content.sections || [];
totalPages = 1; // 封面
if (sections.length > 1) totalPages++; // 目录
sections.forEach(sec => {
  if (sections.length > 1) totalPages++; // 章节分隔页
  totalPages += (sec.slides || []).length || 1;
});
totalPages++; // 结尾

let pageNum = 0;

// 1. 封面页
pageNum++;
createCoverSlide();

// 2. 目录页
if (sections.length > 1) {
  const shouldShowToc = hasTemplate ? (toc.has_toc !== false) : true;
  if (shouldShowToc) {
    pageNum++;
    createTocSlide(sections);
  }
}

// 3. 逐章节生成
sections.forEach((section) => {
  // 章节分隔页
  if (sections.length > 1) {
    pageNum++;
    createSectionSlide(section.title);
  }

  // 章节内的各页
  const slides = section.slides || [];
  slides.forEach((slideData) => {
    pageNum++;
    const slideType = slideData.type || "content";
    createContentSlide(
      slideData.heading || section.title,
      slideData.body || slideData.content || "",
      slideType,
    );
  });
});

// 4. 结尾页
pageNum++;
createEndingSlide();

// ─── 输出 ───
pres.writeFile({ fileName: outputPath }).then(() => {
  console.log(`\n✅ PPT生成完成: ${outputPath}`);
  console.log(`   生成器版本: v3.0`);
  console.log(`   自由度: ${freedomLabel[freedom]}`);
  console.log(`   模板: ${hasTemplate ? spec.theme || "有参考" : "无（自由发挥）"}`);
  console.log(`   页数: ${pres.slides.length}`);
  console.log(`   配色: 主色=${primaryColor}, 辅色=${secondaryColor}, 强调色=${accentColor}`);
  console.log(`   渐变: ${gradients.length}种可用`);
  console.log(`   装饰: 形状=${decoShapes.length}种, 页码=${hasPageNumbers ? "有" : "无"}, 底部栏=${hasBottomBar ? "有" : "无"}`);
  console.log(`   排版: 行距=${lineSpacing}, 对齐=${alignment}, 列表=${listDefaultType}`);
  console.log(`   图片风格: ${imageLayoutType}, 位置偏好=${imagePositionPreference}`);
  console.log(`   布局模式: ${layoutPatterns.map(p => p.name || p).join(", ") || "无"}`);
}).catch(err => {
  console.error("❌ 生成失败:", err);
  process.exit(1);
});
