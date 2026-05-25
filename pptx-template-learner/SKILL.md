---
name: pptx-template-learner
description: "PPT模板学习与生成技能：从已有PPT中逆向分析15+维度（配色、渐变、字体、排版、布局骨架、装饰元素、图片风格、动画、转场、目录、母版、图表、SmartArt等），抽象出可复用的模板规范，然后参考规范生成新PPT。有模板时参考模板风格（自由度可调），无模板时自由发挥。也能管理模板库，按主题归档PPT及规范。触发词：「学习PPT模板」、「按模板做PPT」、「分析PPT风格」、「用XX风格做PPT」、「模板库」、「PPT规范」、「把PPT存为模板」。当用户提到要参考某个PPT的风格、按某个模板做新内容、分析PPT设计规范时，务必使用本技能。"
---

# PPT 模板学习器 v4.1

从已有PPT中**逆向提取设计规范**，参考规范生成新PPT。

## 核心逻辑：有模板参考，无模板自由

```
有模板？
  ├── 是 → 参考模板的配色/字体/布局/动画风格，自由度按需调整
  └── 否 → 自由发挥，做出好看专业的PPT
```

**模板是参考底色，不是紧箍咒。** 参考模板 ≠ 1:1死板复刻，而是保持气质一致、风格延续，内容才是主角。

### 自由度等级

| 自由度 | 含义 | 配色 | 字体 | 布局 | 动画 | 适用场景 |
|--------|------|------|------|------|------|----------|
| **高**（默认） | 参考模板气质，灵活发挥 | 保持色系，可调整明度/饱和度 | 保持气质，可换同类型字体 | 保持骨架，可调比例和留白 | 可增删，保持风格 | 日常使用、灵活展示 |
| **中** | 较多遵循模板 | 主色照搬，辅色可调 | 标题字体照搬，正文可调 | 布局模式照搬，细节可调 | 转场照搬，元素动画可调 | 部门内统一风格 |
| **低** | 高度还原模板 | 照搬 | 照搬 | 照搬 | 照搬 | 品牌要求严格、客户指定 |

**默认自由度 = 高**。用户说"照着做"、"一模一样"→低；说"参考着来"→高；未指定→高。

> ⚠️ 即使自由度=低，也不是像素级复刻——模板提供的是**风格规范**，新内容本身决定了页面怎么组织。

---

## 核心工作流

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ 用户上传PPT  │────▶│ analyze_pptx │────▶│  spec.json  │
│ 或指定模板库  │     │ 提取完整规范   │     │  存入模板库   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  用户给新内容 │────▶│ 确定自由度    │────▶│ 生成新PPT    │
│ + 指定主题    │     │ 高/中/低      │     │ output.pptx │
└─────────────┘     └──────────────┘     └─────────────┘
```

### 三大核心操作

1. **分析**：从PPT提取完整规范 → `spec.json`
2. **归档**：将PPT+规范存入模板库
3. **生成**：参考规范+内容+自由度生成新PPT

---

## 操作1：分析PPT规范

当用户上传PPT或指定已有PPT时，提取完整设计规范。

### 步骤

1. **解包PPT**：
   ```bash
   python scripts/analyze_pptx.py <pptx_file> <output_spec.json>
   ```

2. **检查分析结果**：读取生成的 spec.json，确认关键维度是否完整

3. **展示给用户**：用简洁格式呈现分析结果（配色、字体、布局模式、动画风格等）

### 分析维度（v4.1 共 15+ 维度）

| 维度 | 提取来源 | 提取内容 | 版本 |
|------|---------|---------|------|
| **配色方案** | `theme1.xml` + 形状/文本/背景填充 | 主色/辅色/强调色/背景色/文字色（面积加权+饱和度优先） | v1.0 |
| **渐变填充** | `<a:gradFill>` | 渐变类型、方向、起止色、停靠点 | v4.0 |
| **字体体系** | `<a:rPr>` 统计频率 + `<a:ea>` 区分 | 标题/正文拉丁字体+东亚字体+字号+粗细 | v1.0 |
| **排版规则** | `<a:lnSpc>` + `<a:pPr>` + slideMaster默认 | 行距、段间距、对齐方式、字间距 | v4.0 |
| **文本样式** | `<a:buChar>` + `<a:buNone>` + 效果 | 列表样式（项目符号类型）、文字效果（阴影/描边/渐变填充） | v4.0 |
| **布局模式** | `<a:xfrm>` 位置聚类+骨架识别 | 居中标题、标题+内容、两栏、图文、数据页、卡片网格等 | v4.0 |
| **装饰元素** | 非内容形状+页码+Logo区域 | 装饰线/圆/矩形、页码位置、Logo位置 | v4.0 |
| **图片风格** | `<p:pic>` 统计 | 图片数量、面积占比、风格类型、位置偏好 | v4.0 |
| **动画效果** | `<p:timing>` + `<p:animEffect>` + `<p:anim>` | 进入/退出类型、预设效果名、触发方式、延迟、持续时间 | v4.1 |
| **转场效果** | `<p:transition>` | 转场效果类型、速度、方向 | v1.0 |
| **目录结构** | 关键词匹配+章节页识别+编号层级 | 目录页、章节列表、多级层级 | v4.0 |
| **幻灯片类型** | 布局+内容+背景多维度分类 | 封面/目录/内容/章节/数据/结尾/对比/图片展示 | v4.0 |
| **母版与版式** | `<p:sldMaster>` + `<p:sldLayout>` | 母版数量、版式列表（含名称和占位符） | v4.0 |
| **表格与图表** | `<a:tbl>` + `<c:chart>` XML | 表格样式、图表类型/配色/图例/坐标轴 | v4.1 |
| **SmartArt** | `<p:graphicFrame>` dgm命名空间 | SmartArt数量和类型 | v4.0 |
| **版式比例** | `<p:sldSz>` 尺寸 | 16:9 / 4:3 / 宽屏 | v1.0 |
| **边距** | 内容区域百分位反推 | 上下左右边距（英寸） | v4.0 |

### spec.json 结构（v4.1）

```json
{
  "theme": "主题名称",
  "version": "4.1",
  "meta": {
    "analyzed_at": "ISO日期",
    "source_files": ["文件列表"],
    "slide_count_range": [min, max]
  },
  "slide_size": { "w": 10, "h": 5.625, "ratio": "16:9" },
  "colors": {
    "primary": "4472C4",
    "secondary": "ED7D31",
    "accent": "A5A5A5",
    "bg_dark": "1E2761",
    "bg_light": "FFFFFF",
    "text_dark": "212121",
    "text_light": "FFFFFF"
  },
  "gradients": [
    { "type": "linear", "angle": 5400000, "stops": [{"color": "1E2761", "pos": 0}, {"color": "0891B2", "pos": 100000}] }
  ],
  "fonts": {
    "title": { "name": "Arial", "ea_name": "微软雅黑", "size": 36, "bold": true },
    "subtitle": { "name": "Arial", "ea_name": "微软雅黑", "size": 20, "bold": false },
    "body": { "name": "Calibri", "ea_name": "微软雅黑", "size": 14, "bold": false }
  },
  "typography": {
    "line_spacing": 1.2,
    "paragraph_spacing": 0.3,
    "alignment": "left",
    "char_spacing": 0
  },
  "text_styles": {
    "list": { "default_type": "•", "indent_levels": 2 },
    "text_effects": [
      { "type": "shadow", "target": "title" }
    ]
  },
  "layout": {
    "margins": { "top": 0.5, "right": 0.5, "bottom": 0.5, "left": 0.5 },
    "patterns": [
      { "name": "top-title-bottom-content", "frequency": 5, "description": "标题在上，内容区域在下" },
      { "name": "two-column", "frequency": 2, "description": "左右两栏布局" }
    ]
  },
  "decorations": {
    "shapes": [{"type": "rect", "role": "accent-bar", "color": "primary"}],
    "page_numbers": {"position": "bottom-right"},
    "logo_areas": [{"position": "top-right", "size": "small"}]
  },
  "image_style": {
    "count": 3,
    "area_ratio": 0.4,
    "layout_type": "medium-image",
    "position_preference": "left"
  },
  "toc_structure": {
    "has_toc": true,
    "toc_slide_position": 2,
    "sections": [{"title": "章节名", "level": 1}]
  },
  "slide_types": [
    {
      "role": "cover | toc | section | content | data | ending | comparison | gallery",
      "layout_pattern": "布局模式名",
      "elements": [
        { "type": "text|shape|image|chart", "role": "元素角色", "x": 0, "y": 0, "w": 0, "h": 0 }
      ]
    }
  ],
  "animations": {
    "default_transition": "fade",
    "transition_types": ["fade", "push"],
    "element_animations": [
      {"type": "entrance", "effect": "appear", "trigger": "onClick", "delay_ms": 0}
    ]
  },
  "master_layouts": {
    "masters": [{"name": "Office Theme", "layouts": 11}],
    "layouts": [{"name": "Title Slide", "placeholders": ["title", "subtitle"]}]
  },
  "table_chart_styles": {
    "tables": [{"rows": 4, "cols": 3, "has_header": true, "alt_row_color": "F2F2F2"}],
    "charts": [{"type": "bar", "series_colors": ["4472C4", "ED7D31"], "has_legend": true}],
    "smartart_count": 2
  }
}
```

---

## 操作2：模板库管理

模板库位于 `templates/` 目录下，按主题组织。

### 目录结构

```
templates/
├── 工作汇报/
│   ├── source/             # 原始PPT文件
│   │   ├── 模板A.pptx
│   │   └── 模板B.pptx
│   └── spec.json           # 该主题的统一规范
├── 产品发布/
│   ├── source/
│   └── spec.json
└── ...
```

### 管理命令

```bash
# 列出所有模板主题
python scripts/template_manager.py list

# 查看某主题的规范详情
python scripts/template_manager.py show "工作汇报"

# 归档PPT到模板库（自动分析+存储）
python scripts/template_manager.py add <pptx_file> --theme "工作汇报"

# 删除某主题
python scripts/template_manager.py remove "工作汇报"

# 更新某主题的规范（重新分析所有source）
python scripts/template_manager.py update "工作汇报"
```

### 归档流程

1. 用户上传PPT → 调用 `analyze_pptx.py` 提取规范
2. 询问用户归入哪个主题（可新建）
3. PPT 复制到 `templates/<主题>/source/`
4. spec.json 保存到 `templates/<主题>/spec.json`
5. 如主题已有 spec.json，合并多源PPT的规范（取交集/众数）

---

## 操作3：生成PPT

根据用户内容 + 规范来源 + 自由度生成新PPT。

### 生成步骤

1. **确定规范来源**：
   - 用户指定主题名 → 读取 `templates/<主题>/spec.json`（有模板，参考）
   - 用户上传PPT → 先分析再生成（有参考）
   - 用户啥都没给 → 无模板，自由发挥

2. **确定自由度**：高/中/低（默认高）

3. **内容规划**：
   - 根据用户给出的内容，规划幻灯片类型和页面结构
   - 有模板时参考 spec.json 的 slide_types 分配页面角色
   - 无模板时根据内容自然组织

4. **生成PPT**（使用 pptxgenjs）：
   ```bash
   node scripts/generate_from_spec.js <spec.json> <content.json> <output.pptx> [--freedom high|medium|low] [--no-spec]
   ```
   - 有模板时：`node scripts/generate_from_spec.js spec.json content.json output.pptx --freedom high`
   - 无模板时：`node scripts/generate_from_spec.js {} content.json output.pptx --no-spec`

5. **QA验证**：生成后按 pptx skill 的 QA 流程检查

### 自由度对生成的影响（v4.1 真正差异化）

| 方面 | 高自由度（默认） | 中自由度 | 低自由度 |
|------|-----------------|---------|---------|
| **配色** | 保持色系，RGB偏移±15，可调明度/饱和度 | 主色照搬，辅色RGB偏移±5 | 照搬模板配色(偏移±0) |
| **字体** | 保持气质，可换同类型字体 | 标题字体照搬，正文可调 | 照搬模板字体(含东亚字体) |
| **布局** | 保持骨架，可调比例/换布局变体 | 布局模式照搬，细节可调 | 高度还原模板布局 |
| **排版** | 参考行距/对齐，可灵活调整 | 参考行距/对齐 | 照搬行距/对齐/列表样式 |
| **装饰** | 可增减装饰元素 | 参考模板装饰量 | 照搬装饰元素 |
| **动画** | 可自由设计，保持风格一致 | 转场照搬，元素动画可调 | 照搬模板动画 |
| **渐变** | 可替换渐变配色 | 参考模板渐变 | 照搬模板渐变 |

### content.json 结构（用户内容输入）

```json
{
  "title": "演示文稿标题",
  "subtitle": "副标题",
  "sections": [
    {
      "title": "章节标题",
      "slides": [
        {
          "type": "content",
          "heading": "页面标题",
          "body": ["正文内容1", "正文内容2"],
          "notes": "备注（可选）"
        },
        {
          "type": "data",
          "heading": "数据展示",
          "body": [
            {"value": "2.8亿", "label": "营收", "description": "同比增长23%"}
          ]
        },
        {
          "type": "two-column",
          "heading": "对比分析",
          "body": ["左栏内容1", "左栏内容2"]
        }
      ]
    }
  ],
  "ending_text": "感谢观看",
  "contact": "email@example.com"
}
```

### 生成布局变体（v4.1）

| 页面类型 | 布局变体 | 说明 |
|---------|---------|------|
| 封面 | centered-title, split-image | 居中标题 / 图文分割 |
| 目录 | list-toc, card-toc | 列表式 / 卡片式 |
| 章节 | section-center, section-split | 居中 / 左右分割 |
| 内容 | top-title-bottom-content, two-column | 上标题下内容 / 左右两栏 |
| 数据 | data-with-title, card-grid | 标题+数据 / 卡片网格 |
| 对比 | two-column | 左右对比 |
| 图片 | top-image-bottom-text, image-only | 上图下文 / 纯图片 |
| 结尾 | centered-ending | 居中致谢 |

---

## 脚本说明

| 脚本 | 用途 | 版本 |
|------|------|------|
| `scripts/analyze_pptx.py` | 🔥 核心：从PPT提取完整spec.json（15+维度） | v4.1 |
| `scripts/template_manager.py` | 模板库增删查改 | v1.0 |
| `scripts/generate_from_spec.js` | 根据spec+内容+自由度生成PPT（真正消费spec信息） | v4.1 |

### 依赖继承

本技能继承 pptx skill 的全部脚本（unpack/pack/clean/thumbnail/add_slide），路径为：
```
/data/workspace/.agent/skills/pptx/scripts/
```

使用时需指定完整路径，或先 `cd /data/workspace/.agent/skills/pptx/scripts/`。

---

## 已验证的PPT来源

| 来源 | 格式 | 已测试 | 特点 |
|------|------|--------|------|
| Microsoft Office 2016+ | .pptx | ✅ | 标准OOXML，多母版、多版式、SmartArt |
| WPS Office | .pptx | ✅ | 兼容OOXML，中文东亚字体 |
| Google Slides (导出) | .pptx | ✅ | 简化OOXML，独特配色 |
| LibreOffice (导出) | .pptx | ✅ | 填充效果丰富，渐变支持好 |
| python-pptx (生成) | .pptx | ✅ | 极简结构，适合边界测试 |
| pptx-automizer (生成) | .pptx | ✅ | 图表/SmartArt/多媒体完整 |
| pptxgenjs (生成) | .pptx | ✅ | JS生态标准输出 |

---

## 常见场景

### 场景1：用户上传PPT学习后生成新内容
> "分析这个PPT的风格，然后按同样的风格做一份关于XX的新PPT"

1. `analyze_pptx.py` 提取规范
2. 展示分析结果
3. 用户给新内容 → 参考风格，自由发挥（默认高自由度） → 生成

### 场景2：从模板库选主题
> "用'工作汇报'模板做一份季度总结"

1. `template_manager.py show "工作汇报"` 读取spec
2. 参考模板风格，默认高自由度
3. 根据季度总结内容规划 → 生成

### 场景3：归档PPT到模板库
> "把这个PPT存为模板，叫'年会风格'"

1. `analyze_pptx.py` 提取规范
2. `template_manager.py add <file> --theme "年会风格"`
3. 确认归档成功

### 场景4：无模板自由发挥
> "帮我做一份产品介绍的PPT"

1. 无模板 → 自由发挥
2. 根据内容选择合适的风格 → 生成

### 场景5：要求高度还原
> "严格按这个模板的风格做，尽量一模一样"

1. 读取spec → 低自由度
2. 高度还原模板的配色/字体/布局/动画 → 生成

---

## 注意事项

- **分析质量**：动画和布局提取依赖OOXML节点完整度，简单PPT可能提取不到动画信息
- **规范合并**：同主题多个PPT归档时，取各维度的众数/交集作为统一规范
- **模板 ≠ 复刻**：模板提供风格参考，新内容才是主角。即使低自由度也是风格还原，不是像素级复制
- **中文适配**：生成时注意中文字体回退，标题字体优先选择系统中文字体（微软雅黑等）
- **东亚字体**：v4.1 区分拉丁字体和东亚字体，spec中`ea_name`字段记录中文字体
- **无幻灯片PPT**：v4.1 支持只有母版/版式没有实际幻灯片的PPTX文件（返回最小spec）
- **QA 必做**：每次生成后必须走 visual QA（参照 pptx skill 的 QA 流程）
