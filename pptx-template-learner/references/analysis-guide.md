# PPT 规范分析指南 (v4.1)

本文档说明 `analyze_pptx.py` 提取设计规范时各维度的详细逻辑。

## 分析维度一览

| # | 维度 | 主要XML来源 | 关键提取函数 |
|---|------|-----------|-------------|
| 1 | 幻灯片尺寸 | `ppt/presentation.xml` → `<p:sldSz>` | `_extract_slide_size()` |
| 2 | 配色方案 | `ppt/theme/theme1.xml` + slide XML中 `solidFill` | `_extract_colors()` |
| 3 | 渐变填充 | slide XML中 `<a:gradFill>` | `_extract_gradients()` |
| 4 | 字体体系 | `<a:rPr>` 中 `<a:latin>` + `<a:ea>` 统计 | `_extract_fonts_and_typography()` |
| 5 | 排版规则 | `<a:lnSpc>` + `<a:pPr>` + slideMaster默认值 | 同上 |
| 6 | 文本样式 | `<a:buChar>` / `<a:buNone>` + `<a:effectLst>` | `_extract_text_styles()` |
| 7 | 布局模式 | `<a:xfrm>` 位置聚类 + 骨架识别 | `_classify_layout()` |
| 8 | 装饰元素 | 非内容形状识别 + 页码/Logo检测 | `_extract_decorations()` |
| 9 | 图片风格 | `<p:pic>` 统计 + 面积/位置分析 | `_extract_image_style()` |
| 10 | 动画效果 | `<p:timing>` + `<p:animEffect>` + `<p:anim>` | `_extract_animations()` |
| 11 | 转场效果 | `<p:transition>` | 同上 |
| 12 | 目录结构 | 文本关键词匹配 + 章节编号识别 | `_extract_toc_structure()` |
| 13 | 幻灯片类型 | 多维度分类（位置/内容/背景） | `_classify_slide()` |
| 14 | 母版与版式 | `ppt/slideMasters/` + `ppt/slideLayouts/` | `_extract_master_layouts()` |
| 15 | 表格与图表 | `<a:tbl>` + `ppt/charts/chart*.xml` | `_extract_table_chart_styles()` |
| 16 | 边距 | 内容区域百分位反推 | `_extract_layout_margins()` |

## 配色提取算法

1. 解析 `theme1.xml` 的 `<a:clrScheme>` 获取基础12色
2. 扫描所有slide中的 `solidFill`，按面积加权统计
3. 饱和度优先：优先选择高饱和度颜色作为主色
4. 亮度区分：暗色→`bg_dark`，亮色→`bg_light`
5. 结果：primary / secondary / accent / bg_dark / bg_light / text_dark / text_light

## 渐变提取算法

1. 扫描所有slide XML中的 `<a:gradFill>` 节点
2. 提取方向（`<a:lin>` 的 `ang` 属性）
3. 提取停靠点列表（`<a:gsLst>` → `<a:gs>` → `pos` + `color`）
4. 去重（相同起止色的渐变只保留一个）
5. 结果：type / angle / stops[{pos, color}]

## 字体提取算法

1. 扫描所有 `<a:rPr>` 节点
2. 按 `<a:latin>` 和 `<a:ea>` 分别统计
3. 按 placeholder type 推断角色（title=1,2 → 标题; body=3,4 → 正文）
4. 取频率最高的字体和字号作为默认
5. 区分拉丁字体(name)和东亚字体(ea_name)
6. 结果：title / subtitle / body 各含 name + ea_name + size + bold

## 排版规则提取算法

1. 从slide XML中提取 `<a:lnSpc>` 的 `<a:spcPct>` / `<a:spcPts>`
2. 从slideMaster XML中提取默认行距（作为fallback）
3. 提取 `<a:pPr>` 的 `algn` 属性（对齐方式）
4. 提取 `<a:spcAft>` / `<a:spcBef>` 段间距
5. 结果：line_spacing / paragraph_spacing / alignment / char_spacing

## 文本样式提取算法

1. 从slide XML中提取 `<a:buChar>` 的 `char` 属性（项目符号）
2. 从slideMaster中提取默认bullet定义
3. 统计最常见的符号类型
4. 扫描 `<a:effectLst>` 中的文字效果（阴影、描边、渐变填充）
5. 结果：list.default_type / text_effects[]

## 布局模式识别算法

1. 对每页slide，提取所有元素的 `<a:xfrm>` (x, y, w, h)
2. 按元素位置关系识别布局骨架：
   - 标题在上（y < 25%页面高度）→ `top-title-*`
   - 左右分区（元素群分居左右）→ `two-column` / `image-text`
   - 居中大标题 → `centered-title`
   - 图片在上 → `top-image-bottom-text`
   - 多卡片排列 → `card-grid`
   - 纯数据展示 → `data` / `data-with-title`
3. 跨页聚类：统计每种布局模式的出现频率
4. 结果：layout.patterns[{name, frequency, description}]

## 装饰元素识别算法

1. 遍历所有形状，排除有文本内容的"内容形状"
2. 识别装饰性特征：
   - 面积很小 → 装饰点/线
   - 无文本无图片 → 纯装饰
   - 固定位置反复出现 → Logo/页码/底部栏
3. 页码检测：底部小文本含数字模式
4. Logo检测：固定位置+小尺寸+图片类型
5. 结果：shapes[] / page_numbers / logo_areas / footer_bars

## 图片风格分析算法

1. 扫描所有 `<p:pic>` 元素
2. 统计图片数量和面积占比
3. 按面积分类：
   - `bg-image`: 占比>60%，全屏背景
   - `large-image`: 占比30-60%，主视觉
   - `medium-image`: 占比15-30%，配图
   - `small-image` / `icon-accent`: 占比<15%，图标/点缀
4. 位置偏好：按x坐标分布判断 left/center/right
5. 结果：count / area_ratio / layout_type / position_preference

## 动画提取算法

1. 扫描 `<p:timing>` → `<p:tnLst>` → `<p:par>` 层次
2. 提取 `<p:animEffect>` 的 `transition` (in/out) 和 `prstTransition` (预设效果名)
3. 提取 `<p:anim>` 的目标属性和关键帧
4. 提取触发方式：`<p:seq>` (点击) / `afterPrevious` (自动)
5. 提取延迟和持续时间
6. 结果：default_transition / transition_types[] / element_animations[]

## 边距计算算法

1. 收集所有内容元素（文本框、图片、表格）的x/y坐标
2. 排除最外5%的异常值（防止标题/页码干扰）
3. 取5%百分位值作为边距
4. 限制在合理范围：0.3~1.5 英寸
5. 结果：margins.{top, right, bottom, left}

## 母版与版式提取

1. 扫描 `ppt/slideMasters/slideMaster*.xml`
2. 提取母版名称和关联的版式列表
3. 扫描 `ppt/slideLayouts/slideLayout*.xml`
4. 提取版式名称和占位符类型
5. 结果：masters[].name / layouts[].name + placeholders[]

## 表格与图表提取

1. 扫描 `<a:tbl>` 提取表格：行列数、表头、交替行颜色
2. 扫描 `<c:chart>` 引用，读取 `ppt/charts/chart*.xml`
3. 提取图表：类型、系列颜色、图例位置、坐标轴样式
4. 扫描 SmartArt (`<p:graphicFrame>` dgm命名空间)
5. 结果：tables[] / charts[] / smartart_count
