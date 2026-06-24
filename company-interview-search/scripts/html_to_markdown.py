"""
轻量 HTML → Markdown 转换器（零外部依赖）。

设计目标：把搜索引擎结果后的目标页面正文转成干净的 markdown，
供 LLM 阅读/总结。覆盖常见标签，复杂页面 best-effort。

支持的转换：
- 块级：h1-h6 / p / br / div / ul / ol / li / blockquote / pre / hr
- 行内：a[href] / strong / b / em / i / code
- 表格：table / thead / tbody / tr / th / td
- 移除：script / style / noscript / nav / header / footer / aside / form / iframe

不依赖任何第三方库（无 markdownify / beautifulsoup）。
"""
from __future__ import annotations

import re
from html.parser import HTMLParser


# 块级元素，遇到时强制换行
BLOCK_TAGS = {
    "p", "div", "section", "article", "main",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "hr",
    "table", "thead", "tbody", "tr",
    "br",
}
# 完全移除内容的标签（含其子内容）
DROP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "canvas"}


class _HTMLToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip_depth = 0       # 在 DROP 标签内的嵌套深度
        self._in_pre = 0           # <pre> 嵌套深度，保留空白
        self._in_table = 0         # <table> 内
        self._list_stack: list[tuple[str, int]] = []  # (type, index)
        self._in_link_href: str | None = None
        self._in_link_text: list[str] = []
        self._in_table_row: list[str] | None = None
        self._in_table_cell: list[str] | None = None
        self._skip_cell: bool = False
        self._table_header_done: bool = False

    # ---- 标签处理 ----

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        if tag in DROP_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._out.append("\n\n" + "#" * level + " ")
        elif tag == "p":
            self._out.append("\n\n")
        elif tag == "br":
            self._out.append("\n")
        elif tag == "hr":
            self._out.append("\n\n---\n\n")
        elif tag in ("div", "section", "article", "main"):
            self._out.append("\n")
        elif tag == "ul":
            self._list_stack.append(("ul", 0))
            self._out.append("\n")
        elif tag == "ol":
            self._list_stack.append(("ol", 0))
            self._out.append("\n")
        elif tag == "li":
            if self._list_stack:
                ltype, _ = self._list_stack[-1]
                if ltype == "ol":
                    self._list_stack[-1] = ("ol", self._list_stack[-1][1] + 1)
                    self._out.append(f"\n{self._list_stack[-1][1]}. ")
                else:
                    self._out.append("\n- ")
            else:
                self._out.append("\n- ")
        elif tag == "blockquote":
            self._out.append("\n\n> ")
        elif tag == "pre":
            self._in_pre += 1
            self._out.append("\n\n```\n")
        elif tag == "code" and self._in_pre == 0:
            self._out.append("`")
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")
        elif tag == "a":
            self._in_link_href = a.get("href", "").strip()
            self._in_link_text = []
        elif tag == "table":
            self._in_table += 1
            self._out.append("\n\n")
        elif tag == "tr":
            self._in_table_row = []
        elif tag in ("th", "td"):
            self._in_table_cell = []
            self._skip_cell = tag == "th" and not self._table_header_done
        elif tag == "thead":
            pass  # 标记进入表头
        elif tag == "tbody":
            pass

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if self._skip_depth > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._out.append("\n")
        elif tag == "p":
            self._out.append("\n")
        elif tag in ("div", "section", "article", "main", "blockquote", "pre"):
            if tag == "pre" and self._in_pre > 0:
                self._in_pre -= 1
                self._out.append("\n```\n")
            else:
                self._out.append("\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._out.append("\n")
        elif tag == "li":
            pass  # 列表项结束已在新行
        elif tag == "code" and self._in_pre == 0:
            self._out.append("`")
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")
        elif tag == "a":
            text = "".join(self._in_link_text).strip()
            href = self._in_link_href or ""
            self._in_link_href = None
            self._in_link_text = []
            if not text:
                return
            if href and href.startswith(("http://", "https://", "/")):
                self._out.append(f"[{text}]({href})")
            else:
                self._out.append(text)
        elif tag == "table":
            self._in_table = max(0, self._in_table - 1)
            self._out.append("\n")
        elif tag == "tr":
            if self._in_table_row is not None and self._in_table > 0:
                row = [c.strip() for c in self._in_table_row]
                self._out.append("| " + " | ".join(row) + " |\n")
                if not self._table_header_done and any(row):
                    self._out.append("|" + "|".join(["---"] * len(row)) + "|\n")
                    self._table_header_done = True
            self._in_table_row = None
        elif tag in ("th", "td"):
            if self._in_table_row is not None and self._in_table_cell is not None:
                cell_text = re.sub(r"\s+", " ", "".join(self._in_table_cell)).strip()
                self._in_table_row.append(cell_text)
            self._in_table_cell = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_link_href is not None:
            self._in_link_text.append(data)
            return
        if self._in_table_cell is not None and not self._skip_cell:
            self._in_table_cell.append(data)
            return
        # 在 <pre> 内保留空白；其他地方折叠连续空白
        if self._in_pre > 0:
            self._out.append(data)
        else:
            # 折叠空白但保留换行（前面已通过 \n 注入）
            self._out.append(data)

    @property
    def markdown(self) -> str:
        return _cleanup("".join(self._out))


def _cleanup(s: str) -> str:
    """收尾清理：去多余空行、合并连续空行、首尾空白。"""
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def convert(html: str, max_chars: int = 0) -> str:
    """HTML → Markdown。

    max_chars > 0 时按段落边界截断到 max_chars 字符。
    """
    if not html:
        return ""
    p = _HTMLToMarkdown()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001
        # 解析失败：回退到去标签纯文本
        return re.sub(r"<[^>]+>", " ", html)
    md = p.markdown
    if max_chars > 0 and len(md) > max_chars:
        md = _truncate_by_paragraph(md, max_chars)
    return md


def _truncate_by_paragraph(s: str, max_chars: int) -> str:
    """按段落（双换行）截断，避免在句子中间切断。"""
    if len(s) <= max_chars:
        return s
    cut = s[: max_chars + 200]  # 多取一点找最近的段落边界
    last_break = cut.rfind("\n\n")
    if last_break > max_chars * 0.7:
        return cut[:last_break] + f"\n\n[…内容已截断，原文长度 {len(s)} 字符…]"
    return cut[:max_chars] + f"\n\n[…内容已截断…]"


# ============ 自检 ============
if __name__ == "__main__":
    sample = """
    <html><body>
    <nav>忽略的导航</nav>
    <h1>标题</h1>
    <p>这是 <strong>粗体</strong> 和 <a href="/x">链接</a>。</p>
    <script>alert(1)</script>
    <ul><li>项目 1</li><li>项目 2</li></ul>
    <pre><code>code block</code></pre>
    <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
    </body></html>
    """
    print(convert(sample))
