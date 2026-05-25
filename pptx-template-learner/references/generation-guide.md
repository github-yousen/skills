# PPT 规范生成指南 (v4.1)

本文档说明 `generate_from_spec.js` 如何根据 spec.json 生成新PPT。

## 核心原则

**spec是参考，不是蓝图。** 生成时根据自由度等级灵活参考spec中的各维度信息。

## 生成流程

```
1. 读取spec.json + content.json
2. 根据自由度确定各维度的参考程度
3. 规划页面结构（封面→目录→章节→内容→结尾）
4. 逐页生成，每页根据类型选择布局模板
5. 应用配色/字体/排版/装饰
6. 输出PPTX
```

## 自由度实现细节

### 配色

```javascript
// 低自由度：照搬spec配色
primary = spec.colors.primary;  // RGB偏移±0

// 中自由度：主色照搬，辅色微调
primary = adjustColor(spec.colors.primary, ±5);
secondary = adjustColor(spec.colors.secondary, ±5);

// 高自由度：保持色系，可调整明度/饱和度
primary = adjustColor(spec.colors.primary, ±15);
secondary = adjustColor(spec.colors.secondary, ±15);
```

### 字体

```javascript
// 低自由度：照搬字体（含东亚字体）
titleFont = spec.fonts.title.name;
titleEaFont = spec.fonts.title.ea_name;

// 中自由度：标题照搬，正文可调
titleFont = spec.fonts.title.name;
bodyFont = spec.fonts.body.name;  // 可换同类型

// 高自由度：保持气质，可换同类型字体
// 如 Arial → Calibri, 微软雅黑 → 思源黑体
```

### 排版

```javascript
// 低自由度：照搬行距/对齐/列表样式
lineSpacing = spec.typography.line_spacing;
alignment = spec.typography.alignment;
bulletChar = spec.text_styles.list.default_type;

// 中自由度：参考但可微调
lineSpacing = spec.typography.line_spacing * 1.05;  // 微调

// 高自由度：参考但灵活调整
// 根据内容量自动调整行距
```

### 布局

```javascript
// 低自由度：照搬布局模式，从spec.patterns中选择频率最高的
layoutPattern = spec.layout.patterns[0].name;

// 中自由度：照搬布局模式，细节可调
// 可调整间距、比例

// 高自由度：保持骨架，可换布局变体
// 根据内容自动选择最合适的布局
```

### 装饰

```javascript
// 低自由度：照搬装饰元素
decoShapes = spec.decorations.shapes;
pageNumbers = spec.decorations.page_numbers;
logoAreas = spec.decorations.logo_areas;

// 中自由度：参考装饰量
// 可增减具体装饰元素

// 高自由度：可自由设计装饰
// 保持风格一致即可
```

### 渐变

```javascript
// 低自由度：照搬渐变
gradients = spec.gradients;

// 中自由度：参考渐变类型和方向
// 配色可微调

// 高自由度：可替换渐变配色
// 保持渐变类型和方向
```

## 布局模板系统

### 页面类型与布局对应

| 页面类型 | 布局模板 | 生成函数 |
|---------|---------|---------|
| 封面 (cover) | centered-title / split-image | `_addCoverSlide()` |
| 目录 (toc) | list-toc / card-toc | `_addTocSlide()` |
| 章节 (section) | section-center / section-split | `_addSectionSlide()` |
| 内容 (content) | top-title-bottom-content / two-column | `_addContentSlide()` / `_addTwoColumnSlide()` |
| 数据 (data) | data-with-title / card-grid | `_addDataSlide()` / `_addCardGridSlide()` |
| 对比 (comparison) | two-column | `_addTwoColumnSlide()` |
| 图片 (gallery) | top-image-bottom-text / image-only | `_addImageSlide()` |
| 结尾 (ending) | centered-ending | `_addEndingSlide()` |

### 布局选择逻辑

1. 根据content.json中的slide type确定页面类型
2. 如果spec中有布局模式信息，优先使用spec的布局模式
3. 根据自由度决定是否使用spec布局还是自由选择
4. 低自由度→严格按spec布局，高自由度→根据内容灵活选择

## 配色应用规则

1. **封面**：使用`bg_dark`作为背景色，`text_light`作为文字色
2. **章节页**：使用`primary`作为背景色，`text_light`作为文字色
3. **内容页**：使用`bg_light`作为背景色，`text_dark`作为文字色
4. **装饰**：使用`primary`/`accent`作为装饰元素色
5. **渐变**：优先使用spec中的渐变定义

## 字体应用规则

1. 标题：使用`fonts.title`（含ea_name中文字体）
2. 副标题：使用`fonts.subtitle`
3. 正文：使用`fonts.body`（含ea_name中文字体）
4. 中文字体回退：ea_name → 微软雅黑 → SimHei

## 排版应用规则

1. 行距：使用`typography.line_spacing`（低自由度严格照搬）
2. 对齐：使用`typography.alignment`
3. 列表符号：使用`text_styles.list.default_type`
4. 段间距：使用`typography.paragraph_spacing`

## 图片风格应用

1. 根据`image_style.layout_type`决定图片在页面中的占比
2. 根据`image_style.position_preference`决定图片位置
3. 低自由度：严格照搬图片风格
4. 高自由度：根据内容灵活调整

## 渐变应用

1. 优先用于封面和章节页的背景
2. 根据spec中的渐变方向和起止色
3. 低自由度：照搬渐变
4. 高自由度：可替换渐变配色但保持方向

## 从spec到生成的完整映射

```
spec.colors           → 配色方案（按自由度偏移）
spec.gradients        → 渐变背景（封面/章节页）
spec.fonts            → 字体选择（含东亚字体）
spec.typography       → 行距/对齐/段间距
spec.text_styles      → 列表符号/文字效果
spec.layout.patterns  → 布局模式选择
spec.decorations      → 装饰元素/页码/Logo
spec.image_style      → 图片风格/位置
spec.toc_structure    → 目录结构
spec.master_layouts   → 版式参考
spec.table_chart_styles → 表格/图表样式
spec.animations       → 转场效果
```
