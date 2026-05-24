# PPT分析规范指南

## 分析维度详解

### 1. 配色方案提取

**数据来源**：`ppt/theme/theme1.xml` + 各slide背景/形状填充

| 色彩角色 | 提取逻辑 | OOXML来源 |
|---------|---------|-----------|
| 主色 (primary) | theme的dk2或最高频形状填充色 | `<a:clrScheme>` → dk2 |
| 辅色 (secondary) | theme的lt2 | `<a:clrScheme>` → lt2 |
| 强调色 (accent) | theme的accent1 | `<a:clrScheme>` → accent1 |
| 暗背景 (bg_dark) | 深色slide背景众数 | `<p:bg>` → `<a:solidFill>` |
| 亮背景 (bg_light) | 浅色slide背景众数 | `<p:bg>` → `<a:solidFill>` |
| 暗文字 (text_dark) | 深色文字众数 | `<a:rPr>` → `<a:solidFill>` |
| 亮文字 (text_light) | 浅色文字众数 | `<a:rPr>` → `<a:solidFill>` |

**合并策略**：多个PPT归档同主题时，取各色彩角色的众数。

### 2. 字体体系提取

**数据来源**：`<a:rPr>` 中 `<a:latin>` / `<a:ea>` 的 typeface 属性 + `<a:rPr>` 的 sz 属性

分类逻辑：
- **标题**：出现频率最高的字体 + 最大字号
- **副标题**：第二高频字体 + 中位字号
- **正文**：第三高频字体（或与副标题同） + 最小字号

sz单位是1/100磅，转换：`实际磅值 = sz / 100`

### 3. 布局结构提取

**数据来源**：`<p:spTree>` 中各 `<p:sp>` 的 `<a:xfrm>`

关键属性：
- `<a:off x="..." y="...">` — 元素位置（EMU单位，1英寸 = 914400 EMU）
- `<a:ext cx="..." cy="...">` — 元素尺寸（EMU单位）

元素角色识别：
- 大文本框 + 顶部居中 → 标题
- 小文本框 + 顶部 → 副标题
- 中部文本框 → 正文内容
- 矩形 + 无文本 → 装饰元素
- 图片 → 图像

### 4. 动画效果提取

**数据来源**：`<p:timing>` 节点

常见动画类型：
| OOXML标签 | 效果 |
|-----------|------|
| `<p:animEffect transition="in">` | 进入动画 |
| `<p:animEffect transition="out">` | 退出动画 |
| `<p:anim>` | 属性动画（移动/缩放/旋转） |
| `<p:animMotion>` | 路径动画 |
| `<p:set>` | 设置动画 |

触发方式：
- `<p:click>` — 点击触发
- `<p:seq>` — 序列触发
- `<p:par>` — 并行触发

### 5. 转场效果提取

**数据来源**：`<p:transition>` 节点

| OOXML子标签 | 转场效果 |
|------------|---------|
| `<p:fade>` | 淡入淡出 |
| `<p:push>` | 推入 |
| `<p:wipe>` | 擦除 |
| `<p:cover>` | 覆盖 |
| `<p:split>` | 分割 |
| `<p:random>` | 随机 |

属性：
- `spd` — 速度 (slow/med/fast)
- `advTm` — 自动换页时间（毫秒）

### 6. 幻灯片类型分类

分类规则（优先级从高到低）：
1. **cover**：第1页
2. **ending**：最后1页 + 含"谢谢/感谢/thanks"关键词
3. **toc**：含"目录/contents/大纲/outline/议程"关键词
4. **section**：暗色背景 + ≤3个文本元素
5. **data**：含 `<graphicFrame>`（图表/表格）
6. **content**：默认

### 7. 目录结构识别

逻辑：
1. 检测toc页（关键词匹配）
2. 从section页提取章节名（暗背景页的主文本）
3. 从toc页提取章节列表

---

## 规范合并策略

当同主题归档多个PPT时：

| 维度 | 合并策略 |
|------|---------|
| 配色 | 取众数（出现次数最多的值） |
| 字体 | 取众数字体；字号取同类最大值 |
| 布局 | 取slide_types最丰富的那个spec |
| 动画 | 合并去重 |
| 转场 | 取众数 |
| 目录 | 取章节最完整的spec |
| 页数范围 | 取min~max |
