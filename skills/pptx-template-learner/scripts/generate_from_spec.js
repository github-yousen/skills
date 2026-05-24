#!/usr/bin/env node
/**
 * 根据spec.json + content.json + 自由度生成PPT
 * 
 * 核心逻辑：有模板参考风格，无模板自由发挥。模板是参考底色，不是紧箍咒。
 * 
 * Usage:
 *   node generate_from_spec.js <spec.json> <content.json> <output.pptx> [--freedom high|medium|low] [--no-spec]
 * 
 * Examples:
 *   node generate_from_spec.js spec.json content.json output.pptx --freedom high
 *   node generate_from_spec.js spec.json content.json output.pptx --freedom low
 *   node generate_from_spec.js {} content.json output.pptx --no-spec
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

// ─── 工具函数 ───
function makeShadow() {
  return { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.15 };
}

// 自由度影响下的配色调整
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

// ─── 创建演示文稿 ───
const pres = new pptxgen();

// 幻灯片尺寸
if (hasTemplate && spec.slide_size) {
  const ratio = spec.slide_size.ratio;
  if (ratio === "4:3") pres.layout = "LAYOUT_4x3";
  else if (ratio === "16:10") pres.layout = "LAYOUT_16x10";
  else pres.layout = "LAYOUT_16x9";
} else {
  pres.layout = "LAYOUT_16x9";
}

pres.author = "pptx-template-learner";
pres.title = content.title || "演示文稿";

// ─── 确定设计参数（根据模板+自由度） ───

let primaryColor, secondaryColor, accentColor, bgDark, bgLight, textDark, textLight;
let titleFont, titleSize, subtitleFont, subtitleSize, bodyFont, bodySize;

if (hasTemplate) {
  const colors = spec.colors || {};
  const fonts = spec.fonts || {};

  // 自由度影响配色调整幅度
  // 高自由度：允许较大色相偏移；低自由度：原样使用
  const colorShift = freedom === "high" ? 15 : freedom === "medium" ? 5 : 0;

  primaryColor = adjustColor(colors.primary || "1E2761", colorShift);
  secondaryColor = adjustColor(colors.secondary || "CADCFC", -colorShift);
  accentColor = adjustColor(colors.accent || "0891B2", colorShift);
  bgDark = colors.bg_dark || "1E2761";
  bgLight = colors.bg_light || "FFFFFF";
  textDark = colors.text_dark || "212121";
  textLight = colors.text_light || "FFFFFF";

  // 自由度影响字体选择
  if (freedom === "low") {
    // 低自由度：严格使用模板字体
    titleFont = fonts.title?.name || "Arial";
    titleSize = fonts.title?.size || 36;
    subtitleFont = fonts.subtitle?.name || "Arial";
    subtitleSize = fonts.subtitle?.size || 20;
    bodyFont = fonts.body?.name || "Calibri";
    bodySize = fonts.body?.size || 14;
  } else if (freedom === "medium") {
    // 中自由度：标题照搬，正文可换
    titleFont = fonts.title?.name || "Arial";
    titleSize = fonts.title?.size || 36;
    subtitleFont = fonts.subtitle?.name || "Arial";
    subtitleSize = fonts.subtitle?.size || 20;
    bodyFont = "Calibri";
    bodySize = fonts.body?.size || 14;
  } else {
    // 高自由度：保持气质即可
    titleFont = fonts.title?.name || "Arial";
    titleSize = fonts.title?.size || 36;
    subtitleFont = fonts.subtitle?.name || "Arial";
    subtitleSize = fonts.subtitle?.size || 20;
    bodyFont = "Calibri";
    bodySize = fonts.body?.size || 14;
  }
} else {
  // 无模板：自由发挥，选用专业好看的默认配色
  primaryColor = "1B3A5C";
  secondaryColor = "5B8DB8";
  accentColor = "E8913A";
  bgDark = "1B3A5C";
  bgLight = "FFFFFF";
  textDark = "2D3748";
  textLight = "FFFFFF";
  titleFont = "Arial";
  titleSize = 36;
  subtitleFont = "Arial";
  subtitleSize = 20;
  bodyFont = "Calibri";
  bodySize = 14;
}

const layout = hasTemplate ? (spec.layout || {}) : {};
const margins = layout.margins || { top: 0.5, right: 0.5, bottom: 0.5, left: 0.5 };
const anims = hasTemplate ? (spec.animations || {}) : {};
const toc = hasTemplate ? (spec.toc_structure || {}) : {};

// ─── 转场设置 ───
function getTransition() {
  if (!hasTemplate) {
    return { type: "fade", speed: 0.7 };
  }

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
    // 高自由度：参考模板转场类型，但可调整速度
    return transitionMap[transType] || { type: "fade", speed: 0.7 };
  }

  // 中/低自由度：照搬模板转场
  return transitionMap[transType] || null;
}

// ─── 幻灯片生成函数 ───

/**
 * 封面页
 */
function createCoverSlide() {
  const slide = pres.addSlide();
  slide.background = { color: bgDark };

  // 装饰元素（高自由度可加更多装饰）
  if (freedom === "high" || !hasTemplate) {
    // 右上角装饰圆
    slide.addShape(pres.shapes.OVAL, {
      x: 8.2,
      y: -0.5,
      w: 2.5,
      h: 2.5,
      fill: { color: accentColor, transparency: 80 },
    });
    // 左下角装饰
    slide.addShape(pres.shapes.OVAL, {
      x: -0.8,
      y: 4.0,
      w: 2,
      h: 2,
      fill: { color: secondaryColor, transparency: 85 },
    });
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
    x: 3,
    y: 3.05,
    w: 4,
    h: 0,
    line: { color: accentColor, width: 2 },
  });

  return slide;
}

/**
 * 目录页
 */
function createTocSlide(sections) {
  const slide = pres.addSlide();
  slide.background = { color: bgLight };

  // 左侧装饰条
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 0.08,
    h: 5.625,
    fill: { color: primaryColor },
  });

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

  // 目录项 - 卡片式（高自由度）或列表式（低自由度）
  if (freedom === "high" || !hasTemplate) {
    // 卡片式目录
    const cardH = 0.7;
    const startY = 1.5;
    sections.forEach((sec, idx) => {
      const cy = startY + idx * (cardH + 0.15);
      // 序号圆
      slide.addShape(pres.shapes.OVAL, {
        x: 1.2,
        y: cy + 0.1,
        w: 0.5,
        h: 0.5,
        fill: { color: primaryColor },
      });
      slide.addText(`${idx + 1}`, {
        x: 1.2,
        y: cy + 0.1,
        w: 0.5,
        h: 0.5,
        fontSize: 14,
        fontFace: titleFont,
        color: textLight,
        bold: true,
        align: "center",
        valign: "middle",
      });
      // 章节名
      slide.addText(sec.title || sec, {
        x: 2.0,
        y: cy,
        w: 6,
        h: cardH,
        fontSize: subtitleSize,
        fontFace: subtitleFont,
        color: textDark,
        bold: true,
        valign: "middle",
      });
      // 分隔线
      if (idx < sections.length - 1) {
        slide.addShape(pres.shapes.LINE, {
          x: 2.0,
          y: cy + cardH + 0.05,
          w: 6,
          h: 0,
          line: { color: "E2E8F0", width: 1 },
        });
      }
    });
  } else {
    // 列表式目录（中/低自由度）
    const tocItems = sections.map((sec, idx) => ({
      text: `${idx + 1}. ${sec.title || sec}`,
      options: { bullet: false, breakLine: true, fontSize: subtitleSize, fontFace: bodyFont, color: textDark },
    }));
    slide.addText(tocItems, {
      x: margins.left + 0.5,
      y: 1.5,
      w: 8,
      h: 3.5,
      valign: "top",
      paraSpaceAfter: 10,
    });
  }

  return slide;
}

/**
 * 章节分隔页
 */
function createSectionSlide(sectionTitle) {
  const slide = pres.addSlide();
  slide.background = { color: bgDark };

  if (freedom === "high" || !hasTemplate) {
    // 高自由度：大号章节编号
    slide.addText("SECTION", {
      x: margins.left,
      y: 1.5,
      w: 10 - margins.left - margins.right,
      h: 0.4,
      fontSize: 12,
      fontFace: bodyFont,
      color: accentColor,
      align: "center",
      charSpacing: 5,
    });
  }

  // 装饰线
  slide.addShape(pres.shapes.LINE, {
    x: 3.5,
    y: 2.2,
    w: 3,
    h: 0,
    line: { color: accentColor, width: 3 },
  });

  slide.addText(sectionTitle, {
    x: margins.left,
    y: 2.4,
    w: 10 - margins.left - margins.right,
    h: 1.2,
    fontSize: titleSize + 4,
    fontFace: titleFont,
    color: textLight,
    bold: true,
    align: "center",
  });

  return slide;
}

/**
 * 内容页
 */
function createContentSlide(heading, bodyText) {
  const slide = pres.addSlide();
  slide.background = { color: bgLight };

  // 标题栏背景
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 10,
    h: 1.0,
    fill: { color: primaryColor },
  });

  slide.addText(heading, {
    x: margins.left,
    y: 0.1,
    w: 10 - margins.left - margins.right,
    h: 0.8,
    fontSize: titleSize - 4,
    fontFace: titleFont,
    color: textLight,
    bold: true,
    valign: "middle",
  });

  // 正文
  const contentArea = { x: margins.left, y: 1.3, w: 10 - margins.left - margins.right, h: 4.0 };

  if (typeof bodyText === "string") {
    const paragraphs = bodyText.split("\n").filter(l => l.trim());
    const textItems = paragraphs.map(p => ({
      text: p.replace(/^[-•*]\s*/, ""),
      options: {
        bullet: /^[-•*]/.test(p),
        breakLine: true,
        fontSize: bodySize,
        fontFace: bodyFont,
        color: textDark,
      },
    }));
    slide.addText(textItems, { ...contentArea, valign: "top", paraSpaceAfter: 6 });
  } else if (Array.isArray(bodyText)) {
    const textItems = bodyText.map(p => {
      if (typeof p === "string") {
        return { text: p, options: { bullet: true, breakLine: true, fontSize: bodySize, fontFace: bodyFont, color: textDark } };
      }
      return {
        text: p.text || p.heading || "",
        options: {
          bullet: true,
          breakLine: true,
          fontSize: p.heading ? subtitleSize : bodySize,
          fontFace: p.heading ? subtitleFont : bodyFont,
          color: textDark,
          bold: !!p.heading,
        },
      };
    });
    slide.addText(textItems, { ...contentArea, valign: "top", paraSpaceAfter: 6 });
  }

  // 底部装饰线（高自由度时）
  if (freedom === "high" || !hasTemplate) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0,
      y: 5.425,
      w: 10,
      h: 0.04,
      fill: { color: accentColor },
    });
  }

  return slide;
}

/**
 * 数据展示页
 */
function createDataSlide(heading, dataPoints) {
  const slide = pres.addSlide();
  slide.background = { color: bgLight };

  // 标题
  slide.addText(heading, {
    x: margins.left,
    y: margins.top,
    w: 10 - margins.left - margins.right,
    h: 0.7,
    fontSize: titleSize - 4,
    fontFace: titleFont,
    color: primaryColor,
    bold: true,
  });

  // 数据卡片
  const cardW = Math.min(3.5, (10 - margins.left - margins.right - 0.3 * (dataPoints.length - 1)) / dataPoints.length);
  const startX = margins.left + (10 - margins.left - margins.right - (cardW * dataPoints.length + 0.3 * (dataPoints.length - 1))) / 2;

  dataPoints.forEach((dp, idx) => {
    const cx = startX + idx * (cardW + 0.3);
    const cy = 1.5;

    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx,
      y: cy,
      w: cardW,
      h: 2.8,
      fill: { color: "FFFFFF" },
      shadow: makeShadow(),
    });

    // 左侧装饰条
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx,
      y: cy,
      w: 0.06,
      h: 2.8,
      fill: { color: accentColor },
    });

    // 数值
    slide.addText(dp.value || dp.number || "—", {
      x: cx + 0.2,
      y: cy + 0.3,
      w: cardW - 0.4,
      h: 1.0,
      fontSize: 32,
      fontFace: titleFont,
      color: primaryColor,
      bold: true,
      align: "center",
    });

    // 标签
    slide.addText(dp.label || dp.name || "", {
      x: cx + 0.2,
      y: cy + 1.3,
      w: cardW - 0.4,
      h: 0.5,
      fontSize: subtitleSize - 2,
      fontFace: subtitleFont,
      color: textDark,
      bold: true,
      align: "center",
    });

    // 描述
    if (dp.description) {
      slide.addText(dp.description, {
        x: cx + 0.2,
        y: cy + 1.8,
        w: cardW - 0.4,
        h: 0.8,
        fontSize: 10,
        fontFace: bodyFont,
        color: "64748B",
        align: "center",
      });
    }
  });

  return slide;
}

/**
 * 结尾页
 */
function createEndingSlide() {
  const slide = pres.addSlide();
  slide.background = { color: bgDark };

  const endText = content.ending_text || "感谢观看";

  if (freedom === "high" || !hasTemplate) {
    // 装饰圆
    slide.addShape(pres.shapes.OVAL, {
      x: 4,
      y: 0.5,
      w: 2,
      h: 2,
      fill: { color: accentColor, transparency: 85 },
    });
  }

  slide.addText(endText, {
    x: margins.left,
    y: 1.8,
    w: 10 - margins.left - margins.right,
    h: 1.5,
    fontSize: titleSize + 8,
    fontFace: titleFont,
    color: textLight,
    bold: true,
    align: "center",
  });

  // 装饰线
  slide.addShape(pres.shapes.LINE, {
    x: 3.5,
    y: 3.5,
    w: 3,
    h: 0,
    line: { color: accentColor, width: 2 },
  });

  // 联系方式
  if (content.contact || content.email) {
    slide.addText(content.contact || content.email, {
      x: margins.left,
      y: 3.7,
      w: 10 - margins.left - margins.right,
      h: 0.5,
      fontSize: bodySize,
      fontFace: bodyFont,
      color: secondaryColor,
      align: "center",
    });
  }

  return slide;
}

// ─── 主生成逻辑 ───

// 1. 封面页
createCoverSlide();

// 2. 目录页
const sections = content.sections || [];
if (sections.length > 1) {
  const shouldShowToc = hasTemplate ? (toc.has_toc !== false) : true;
  if (shouldShowToc) {
    createTocSlide(sections);
  }
}

// 3. 逐章节生成
sections.forEach((section) => {
  // 章节分隔页（多章节时）
  if (sections.length > 1) {
    createSectionSlide(section.title);
  }

  // 章节内的各页
  const slides = section.slides || [];
  slides.forEach((slideData) => {
    switch (slideData.type) {
      case "data":
        createDataSlide(
          slideData.heading || section.title,
          slideData.data_points || slideData.items || []
        );
        break;
      case "content":
      default:
        createContentSlide(
          slideData.heading || section.title,
          slideData.body || slideData.content || ""
        );
        break;
    }
  });
});

// 4. 结尾页
createEndingSlide();

// ─── 输出 ───
pres.writeFile({ fileName: outputPath }).then(() => {
  console.log(`\n✅ PPT生成完成: ${outputPath}`);
  console.log(`   自由度: ${freedomLabel[freedom]}`);
  console.log(`   模板: ${hasTemplate ? spec.theme || "有参考" : "无（自由发挥）"}`);
  console.log(`   页数: ${pres.slides.length}`);
  console.log(`   配色: 主色=${primaryColor}, 辅色=${secondaryColor}, 强调色=${accentColor}`);
}).catch(err => {
  console.error("❌ 生成失败:", err);
  process.exit(1);
});
