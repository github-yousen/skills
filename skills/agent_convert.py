#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_convert.py
================

通用 AI Agent 转换器:把 **任意源 agent** 项目里的内容一键转成
**任意一个或多个其它 agent** 所需的目录结构与文件格式。

转换规则参考自 spec-kit 的 integrations/registrar_config 和 OpenSpec 的
available-tools。

支持的 10 个 agent,按格式分三类:
  SKILL 格式:  codebuddy  claude  codex  cursor-agent
  Markdown:    qwen  iflow  roo  windsurf  copilot
  TOML:        gemini

7 类可同步内容(--sync 控制,默认全部开启):
  1. skills    技能/命令本体 + 资源(scripts/evals/数据文件)
  2. rules     规则文件 (.codebuddy/rules / .cursor/rules / .roo/rules / .windsurf/rules)
  3. context   项目记忆文件 (CLAUDE.md / GEMINI.md / AGENTS.md / CODEBUDDY.md ...)
  4. commands  斜杠命令 (commands_dir 与 skill dir 不重合的 agent)
  5. agents    子代理 (.claude/agents 等)
  6. mcp       MCP 服务器配置 (.mcp.json / .codex/config.toml)
  7. settings  hooks / settings 文件 (按目标路径原样拷贝并提示)

用法 (位置参数: from to):
    python agent_convert.py <from> <to> [选项]

例:
    python agent_convert.py codebuddy claude               # 单 → 单, 全部 7 类
    python agent_convert.py claude gemini,cursor-agent     # 单 → 多
    python agent_convert.py gemini all                     # → 全部其它
    python agent_convert.py codebuddy claude -i my-skill   # 只转一个 skill
    python agent_convert.py codebuddy all -n               # 干跑(预览)
    python agent_convert.py claude all --sync skills,context,mcp
    python agent_convert.py claude all --skip settings,agents
    python agent_convert.py --list                          # 列出 agent

依赖: 仅 Python 标准库;装了 PyYAML 会自动用;TOML 解析优先 tomllib (Py3.11+)。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# 可选依赖
# ----------------------------------------------------------------------------
try:
    import yaml  # type: ignore
    _HAS_YAML = True
except Exception:
    yaml = None  # type: ignore
    _HAS_YAML = False

try:  # py 3.11+
    import tomllib  # type: ignore
    _HAS_TOMLLIB = True
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore
    _HAS_TOMLLIB = False


# ----------------------------------------------------------------------------
# Agent 配置（移植自 spec-kit registrar_config + OpenSpec available-tools）
#
# 每条配置可包含:
#   核心字段:
#     name / dir / format / extension / args
#   skill / rules:
#     rules_dir          规则文件目录(None=不支持)
#     claude_inject      Claude 专属 frontmatter 字段注入
#     copilot_companion  Copilot 配套 .prompt.md
#   扩展同步类目 (--sync 控制):
#     context_file       根 context/记忆文件路径 (例 CLAUDE.md / GEMINI.md)
#     commands_dir       斜杠命令目录(可能与 skill dir 重合)
#     agents_dir         子代理目录(.claude/agents 等)
#     mcp_file           MCP 服务器配置文件
#     mcp_format         "json" | "toml"
#     mcp_key            mcp servers 在配置里的 key 名
#     settings_file      hooks / settings 文件
# ----------------------------------------------------------------------------
AGENT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "codebuddy": {
        "name": "CodeBuddy",
        "dir": ".codebuddy/skills",
        "format": "skill",
        "extension": "/SKILL.md",
        "args": "$ARGUMENTS",
        "rules_dir": ".codebuddy/rules",
        "context_file": "CODEBUDDY.md",
        "commands_dir": ".codebuddy/commands",
        "agents_dir": ".codebuddy/agents",
        "mcp_file": ".codebuddy/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": ".codebuddy/settings.json",
    },
    "claude": {
        "name": "Claude Code",
        "dir": ".claude/skills",
        "format": "skill",
        "extension": "/SKILL.md",
        "args": "$ARGUMENTS",
        "rules_dir": None,
        "claude_inject": True,
        "context_file": "CLAUDE.md",
        "commands_dir": ".claude/commands",
        "agents_dir": ".claude/agents",
        "mcp_file": ".mcp.json",                 # 项目根
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": ".claude/settings.json",
    },
    "codex": {
        "name": "Codex CLI",
        "dir": ".agents/skills",
        "format": "skill",
        "extension": "/SKILL.md",
        "args": "$ARGUMENTS",
        "rules_dir": None,
        "context_file": "AGENTS.md",
        "commands_dir": None,                    # codex 没有独立 commands
        "agents_dir": None,                      # .agents/ 就是 skill 父目录,无独立子代理
        "mcp_file": ".codex/config.toml",
        "mcp_format": "toml",
        "mcp_key": "mcp_servers",
        "settings_file": None,
    },
    "cursor-agent": {
        "name": "Cursor",
        "dir": ".cursor/skills",
        "format": "skill",
        "extension": "/SKILL.md",
        "args": "$ARGUMENTS",
        "rules_dir": ".cursor/rules",
        "context_file": ".cursor/rules/specify-rules.mdc",
        "commands_dir": ".cursor/commands",
        "agents_dir": ".cursor/subagents",
        "mcp_file": ".cursor/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": ".cursor/settings.json",
    },
    "qwen": {
        "name": "Qwen Code",
        "dir": ".qwen/commands",
        "format": "markdown",
        "extension": ".md",
        "args": "$ARGUMENTS",
        "rules_dir": None,
        "context_file": "QWEN.md",
        "commands_dir": ".qwen/commands",        # 与 skill dir 相同
        "agents_dir": None,
        "mcp_file": ".qwen/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,
    },
    "iflow": {
        "name": "iFlow CLI",
        "dir": ".iflow/commands",
        "format": "markdown",
        "extension": ".md",
        "args": "$ARGUMENTS",
        "rules_dir": None,
        "context_file": "IFLOW.md",
        "commands_dir": ".iflow/commands",
        "agents_dir": None,
        "mcp_file": ".iflow/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,
    },
    "roo": {
        "name": "Roo Code",
        "dir": ".roo/commands",
        "format": "markdown",
        "extension": ".md",
        "args": "$ARGUMENTS",
        "rules_dir": ".roo/rules",
        "context_file": ".roo/rules/specify-rules.md",
        "commands_dir": ".roo/commands",
        "agents_dir": None,
        "mcp_file": ".roo/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,
    },
    "windsurf": {
        "name": "Windsurf",
        "dir": ".windsurf/workflows",
        "format": "markdown",
        "extension": ".md",
        "args": "$ARGUMENTS",
        "rules_dir": ".windsurf/rules",
        "context_file": ".windsurf/rules/specify-rules.md",
        "commands_dir": ".windsurf/workflows",
        "agents_dir": None,
        "mcp_file": ".windsurf/mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,
    },
    "copilot": {
        "name": "GitHub Copilot",
        "dir": ".github/agents",
        "format": "markdown",
        "extension": ".agent.md",
        "args": "$ARGUMENTS",
        "rules_dir": None,
        "copilot_companion": True,
        "context_file": ".github/copilot-instructions.md",
        "commands_dir": ".github/prompts",
        "agents_dir": ".github/agents",          # 与 skill dir 相同
        "mcp_file": ".github/.mcp.json",
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,
    },
    "gemini": {
        "name": "Gemini CLI",
        "dir": ".gemini/commands",
        "format": "toml",
        "extension": ".toml",
        "args": "{{args}}",
        "rules_dir": None,
        "context_file": "GEMINI.md",
        "commands_dir": ".gemini/commands",      # 与 skill dir 相同
        "agents_dir": None,
        "mcp_file": ".gemini/settings.json",     # gemini 的 mcp 嵌在 settings.json 里
        "mcp_format": "json",
        "mcp_key": "mcpServers",
        "settings_file": None,                   # 不再单独同步,避免和 mcp_file 冲突
    },
}


# ----------------------------------------------------------------------------
# Frontmatter 解析与渲染
# ----------------------------------------------------------------------------
def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}, content

    end_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            end_idx = i
            break
    if end_idx == -1:
        return {}, content

    fm_text = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1:])

    fm: Dict[str, Any] = {}
    if _HAS_YAML:
        try:
            loaded = yaml.safe_load(fm_text) or {}
            if isinstance(loaded, dict):
                fm = loaded
        except Exception:
            fm = {}
    else:
        fm = _simple_yaml_parse(fm_text)
    return fm, body


def _simple_yaml_parse(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        result[key] = value
    return result


def render_yaml_frontmatter(fm: Dict[str, Any]) -> str:
    if not fm:
        return ""
    if _HAS_YAML:
        body = yaml.safe_dump(
            fm, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
    else:
        body = _simple_yaml_dump(fm)
    return f"---\n{body}---\n"


def _simple_yaml_dump(d: Dict[str, Any]) -> str:
    out: List[str] = []
    for k, v in d.items():
        if isinstance(v, bool):
            out.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{k}: {v}")
        elif isinstance(v, dict):
            out.append(f"{k}:")
            for sk, sv in v.items():
                out.append(f"  {sk}: {_yaml_scalar(sv)}")
        else:
            out.append(f"{k}: {_yaml_scalar(v)}")
    return "\n".join(out) + "\n"


def _yaml_scalar(v: Any) -> str:
    s = "" if v is None else str(v)
    if any(c in s for c in [":", "#", "\n", '"', "'", "{", "}", "[", "]", "&", "*", "!", "|", ">", "%", "@", "`"]):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


# ----------------------------------------------------------------------------
# TOML 渲染 / 解析
# ----------------------------------------------------------------------------
def render_toml_command(description: str, body: str) -> str:
    out: List[str] = []
    if description:
        out.append(f"description = {_toml_string(description)}")
        out.append("")
    body = body.rstrip("\n")
    out.append(f"prompt = {_toml_string(body)}")
    return "\n".join(out) + "\n"


def _toml_string(value: str) -> str:
    if "\n" not in value and "\r" not in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if '"""' not in value:
        escaped = value.replace("\\", "\\\\")
        if escaped.endswith('"'):
            return '"""\n' + escaped + '\\\n"""'
        return '"""\n' + escaped + '\n"""'
    if "'''" not in value:
        return "'''\n" + value + "\n'''"
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def parse_toml_command(text: str) -> Tuple[str, str]:
    """从 TOML 命令文件中提取 (description, prompt)。"""
    if _HAS_TOMLLIB:
        try:
            data = tomllib.loads(text)
            return str(data.get("description", "") or ""), str(data.get("prompt", "") or "")
        except Exception:
            pass
    # fallback：简单正则
    description = ""
    prompt = ""
    m = re.search(r'^description\s*=\s*"([^"\n]*)"\s*$', text, re.MULTILINE)
    if m:
        description = m.group(1)
    # prompt = """..."""
    m = re.search(r'^prompt\s*=\s*"""\s*\n?(.*?)"""\s*$', text, re.MULTILINE | re.DOTALL)
    if m:
        prompt = m.group(1).rstrip("\\\n")
    else:
        m = re.search(r"^prompt\s*=\s*'''\s*\n?(.*?)'''\s*$", text, re.MULTILINE | re.DOTALL)
        if m:
            prompt = m.group(1)
        else:
            m = re.search(r'^prompt\s*=\s*"((?:[^"\\]|\\.)*)"\s*$', text, re.MULTILINE)
            if m:
                prompt = m.group(1).encode().decode("unicode_escape", errors="replace")
    return description, prompt


# ----------------------------------------------------------------------------
# 数据类
# ----------------------------------------------------------------------------
@dataclass
class Skill:
    name: str
    src_root: Path                 # 资源目录(用于计算 extras 的相对路径)
    frontmatter: Dict[str, Any]
    body: str                       # 已经把 args 占位符规范成 $ARGUMENTS
    extra_files: List[Path] = field(default_factory=list)

    @property
    def description(self) -> str:
        d = self.frontmatter.get("description", "")
        if not isinstance(d, str):
            d = str(d) if d is not None else ""
        return d


# ----------------------------------------------------------------------------
# 读取 (任意 agent → Skill)
# ----------------------------------------------------------------------------
def _normalize_args(text: str, src_arg: str) -> str:
    """把源 agent 的参数占位符统一规范成内部表示 $ARGUMENTS。"""
    if not text:
        return text
    if src_arg != "$ARGUMENTS":
        text = text.replace(src_arg, "$ARGUMENTS")
    text = text.replace("{ARGS}", "$ARGUMENTS")
    return text


def _strip_source_note(body: str) -> str:
    """去掉 <!-- Source: xxx --> 那行注释（写入时会重新加）。"""
    return re.sub(r"^\s*<!--\s*Source:.*?-->\s*\n", "", body, count=1)


def discover_from_agent(agent_key: str, root: Path) -> Tuple[List[Skill], List[Path]]:
    """从指定 agent 的目录读出所有技能/命令 + 规则文件。"""
    if agent_key not in AGENT_CONFIGS:
        raise ValueError(f"Unknown agent: {agent_key}")
    cfg = AGENT_CONFIGS[agent_key]
    src_dir = root / cfg["dir"]
    fmt = cfg["format"]

    skills: List[Skill] = []
    if not src_dir.is_dir():
        return [], _discover_rules(agent_key, root)

    if fmt == "skill":
        for sub in sorted(src_dir.iterdir()):
            if not sub.is_dir():
                continue
            skill_md = sub / "SKILL.md"
            if not skill_md.is_file():
                continue
            content = skill_md.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(content)
            name = str(fm.get("name") or sub.name)
            extras: List[Path] = []
            for child in sub.rglob("*"):
                if not child.is_file() or child == skill_md:
                    continue
                rel_parts = child.relative_to(sub).parts
                if any(p.startswith(".") for p in rel_parts):
                    continue
                extras.append(child)
            skills.append(Skill(
                name=name,
                src_root=sub,
                frontmatter=fm,
                body=_normalize_args(body, cfg["args"]),
                extra_files=extras,
            ))

    elif fmt == "markdown":
        ext = cfg["extension"]
        # 收集匹配 ext 的文件（如 *.md / *.agent.md）
        pattern = f"*{ext}"
        files = sorted(p for p in src_dir.glob(pattern) if p.is_file())
        for f in files:
            content = f.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(content)
            body = _strip_source_note(body)
            # 取技能名：先 frontmatter.name，再去掉扩展名
            stem = f.name[:-len(ext)] if f.name.endswith(ext) and ext != ".md" else f.stem
            name = str(fm.get("name") or stem)
            # 找同级 _assets/<name>/ 资源
            extras_root, extras = _collect_assets(src_dir, name)
            skills.append(Skill(
                name=name,
                src_root=extras_root or f.parent,
                frontmatter=fm,
                body=_normalize_args(body, cfg["args"]),
                extra_files=extras,
            ))

    elif fmt == "toml":
        for f in sorted(src_dir.glob("*.toml")):
            description, prompt = parse_toml_command(f.read_text(encoding="utf-8"))
            name = f.stem
            fm = {"description": description} if description else {}
            extras_root, extras = _collect_assets(src_dir, name)
            skills.append(Skill(
                name=name,
                src_root=extras_root or f.parent,
                frontmatter=fm,
                body=_normalize_args(prompt, cfg["args"]),
                extra_files=extras,
            ))

    return skills, _discover_rules(agent_key, root)


def _collect_assets(src_dir: Path, name: str) -> Tuple[Optional[Path], List[Path]]:
    assets_dir = src_dir / "_assets" / name
    if not assets_dir.is_dir():
        return None, []
    files: List[Path] = []
    for child in assets_dir.rglob("*"):
        if child.is_file():
            files.append(child)
    return assets_dir, files


def _discover_rules(agent_key: str, root: Path) -> List[Path]:
    cfg = AGENT_CONFIGS[agent_key]
    rules_dir = cfg.get("rules_dir")
    if not rules_dir:
        return []
    rd = root / rules_dir
    if not rd.is_dir():
        return []
    return sorted(p for p in rd.iterdir() if p.is_file())


# ----------------------------------------------------------------------------
# 写入器
# ----------------------------------------------------------------------------
class Writer:
    def __init__(self, dst_root: Path, dry_run: bool = False) -> None:
        self.dst_root = dst_root
        self.dry_run = dry_run
        self.created: List[Path] = []

    def _log(self, action: str, path: Path) -> None:
        try:
            rel = path.relative_to(self.dst_root)
        except Exception:
            rel = path
        print(f"  [{action}] {rel}")

    def write_text(self, dest: Path, content: str) -> None:
        if self.dry_run:
            self._log("WOULD-WRITE", dest); return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content.replace("\r\n", "\n").encode("utf-8"))
        self.created.append(dest)
        self._log("WRITE", dest)

    def copy_file(self, src: Path, dest: Path) -> None:
        if self.dry_run:
            self._log("WOULD-COPY", dest); return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        self.created.append(dest)
        self._log("COPY", dest)


# ----------------------------------------------------------------------------
# 写出 (Skill → 任意 agent)
# ----------------------------------------------------------------------------
def _convert_args(text: str, target_arg: str) -> str:
    if target_arg == "$ARGUMENTS":
        return text
    return text.replace("$ARGUMENTS", target_arg)


def _build_skill_frontmatter(agent_key: str, skill: Skill) -> Dict[str, Any]:
    fm: Dict[str, Any] = {
        "name": skill.name,
        "description": skill.description or f"Skill: {skill.name}",
    }
    if AGENT_CONFIGS[agent_key].get("claude_inject"):
        fm["user-invocable"] = True
        fm["disable-model-invocation"] = True
    return fm


def write_skill_format(agent_key: str, skill: Skill, writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    target_dir = writer.dst_root / cfg["dir"] / skill.name

    new_fm = _build_skill_frontmatter(agent_key, skill)
    new_body = _convert_args(skill.body, cfg["args"])
    skill_content = render_yaml_frontmatter(new_fm) + "\n" + new_body.lstrip("\n")
    writer.write_text(target_dir / "SKILL.md", skill_content)

    for f in skill.extra_files:
        rel = f.relative_to(skill.src_root)
        writer.copy_file(f, target_dir / rel)


def write_markdown_command(agent_key: str, skill: Skill, writer: Writer, source_id: str) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    fname = f"{skill.name}{cfg['extension']}"
    target_file = writer.dst_root / cfg["dir"] / fname

    fm: Dict[str, Any] = {}
    if skill.description:
        fm["description"] = skill.description
    body = _convert_args(skill.body, cfg["args"])
    note = f"\n<!-- Source: {source_id}:{skill.name} -->\n"
    content = render_yaml_frontmatter(fm) + note + body.lstrip("\n")
    writer.write_text(target_file, content)

    if cfg.get("copilot_companion"):
        prompt_dir = writer.dst_root / ".github" / "prompts"
        writer.write_text(prompt_dir / f"{skill.name}.prompt.md",
                          f"---\nagent: {skill.name}\n---\n")

    if skill.extra_files:
        sibling = writer.dst_root / cfg["dir"] / "_assets" / skill.name
        for f in skill.extra_files:
            rel = f.relative_to(skill.src_root)
            writer.copy_file(f, sibling / rel)


def write_toml_command(agent_key: str, skill: Skill, writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    fname = f"{skill.name}{cfg['extension']}"
    target_file = writer.dst_root / cfg["dir"] / fname
    body = _convert_args(skill.body, cfg["args"])
    content = render_toml_command(skill.description, body)
    writer.write_text(target_file, content)

    if skill.extra_files:
        sibling = writer.dst_root / cfg["dir"] / "_assets" / skill.name
        for f in skill.extra_files:
            rel = f.relative_to(skill.src_root)
            writer.copy_file(f, sibling / rel)


def write_rules(agent_key: str, rules: List[Path], writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    rules_dir = cfg.get("rules_dir")
    if not rules_dir:
        return
    target_dir = writer.dst_root / rules_dir
    for r in rules:
        writer.copy_file(r, target_dir / r.name)


# ============================================================================
# 扩展同步类目: context / commands / agents / mcp / settings
# ============================================================================

# ---- 1. context 文件 (CLAUDE.md / GEMINI.md / AGENTS.md / ...) -------------
def discover_context(agent_key: str, root: Path) -> Optional[Path]:
    cfg = AGENT_CONFIGS[agent_key]
    cf = cfg.get("context_file")
    if not cf:
        return None
    p = root / cf
    return p if p.is_file() else None


def write_context(agent_key: str, content: str, writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    cf = cfg.get("context_file")
    if not cf:
        return
    writer.write_text(writer.dst_root / cf, content)


# ---- 2. 斜杠命令 (commands_dir, 与 skill dir 区分) -------------------------
def discover_commands(agent_key: str, root: Path) -> List[Path]:
    """读出 commands_dir 下的命令文件(不递归到 skill 子目录)。"""
    cfg = AGENT_CONFIGS[agent_key]
    cmd_dir = cfg.get("commands_dir")
    if not cmd_dir:
        return []
    # 如果 commands_dir 与 skill dir 重合，跳过(避免和 skill 重复处理)
    if cmd_dir == cfg.get("dir"):
        return []
    cd = root / cmd_dir
    if not cd.is_dir():
        return []
    files: List[Path] = []
    for p in sorted(cd.iterdir()):
        if p.is_file() and p.suffix in (".md", ".toml", ".prompt.md"):
            files.append(p)
        elif p.is_file() and p.name.endswith(".agent.md"):
            files.append(p)
    return files


def write_commands(agent_key: str, commands: List[Path], writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    cmd_dir = cfg.get("commands_dir")
    if not cmd_dir:
        return
    if cmd_dir == cfg.get("dir"):
        return  # commands 已通过 skill 通道写入,这里跳过避免重复
    target = writer.dst_root / cmd_dir
    for c in commands:
        # 简单按目标 agent 的命名规则微调：copilot → .agent.md / 其它 → .md
        target_name = c.name
        # 去掉源的特殊后缀
        for suffix in (".agent.md", ".prompt.md"):
            if target_name.endswith(suffix):
                target_name = target_name[: -len(suffix)] + ".md"
                break
        if cfg.get("copilot_companion") and target_name.endswith(".md"):
            target_name = target_name[:-3] + ".agent.md"
        writer.copy_file(c, target / target_name)


# ---- 3. 子代理 (agents_dir, 通常是单文件 markdown) -----------------------
def discover_agents(agent_key: str, root: Path) -> List[Path]:
    cfg = AGENT_CONFIGS[agent_key]
    a_dir = cfg.get("agents_dir")
    if not a_dir:
        return []
    if a_dir == cfg.get("dir"):
        return []  # 与 skill dir 重合则跳过
    ad = root / a_dir
    if not ad.is_dir():
        return []
    files: List[Path] = []
    for p in sorted(ad.iterdir()):
        if p.is_file() and (p.suffix == ".md" or p.name.endswith(".agent.md")):
            files.append(p)
    return files


def write_agents(agent_key: str, agents: List[Path], writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    a_dir = cfg.get("agents_dir")
    if not a_dir:
        return
    if a_dir == cfg.get("dir"):
        return
    target = writer.dst_root / a_dir
    for a in agents:
        # 文件名按目标后缀适配
        name = a.name
        for suffix in (".agent.md", ".md"):
            if name.endswith(suffix):
                name = name[: -len(suffix)] + ".md"
                break
        if cfg.get("copilot_companion") and name.endswith(".md"):
            name = name[:-3] + ".agent.md"
        writer.copy_file(a, target / name)


# ---- 4. MCP 配置 (json / toml) ----------------------------------------------
def _parse_json_loose(text: str) -> Dict[str, Any]:
    try:
        import json
        return json.loads(text)
    except Exception:
        return {}


def discover_mcp(agent_key: str, root: Path) -> Dict[str, Any]:
    """返回 mcp_servers dict (key 已规范化为 'servers')。"""
    cfg = AGENT_CONFIGS[agent_key]
    mf = cfg.get("mcp_file")
    if not mf:
        return {}
    p = root / mf
    if not p.is_file():
        return {}
    text = p.read_text(encoding="utf-8")
    fmt = cfg.get("mcp_format", "json")
    key = cfg.get("mcp_key", "mcpServers")
    if fmt == "toml":
        if _HAS_TOMLLIB:
            try:
                data = tomllib.loads(text)
            except Exception:
                data = {}
        else:
            data = {}
    else:
        data = _parse_json_loose(text)
    if not isinstance(data, dict):
        return {}
    servers = data.get(key) or {}
    return {"servers": servers, "raw": data}


def _render_mcp_json(servers: Dict[str, Any], key: str, base: Optional[Dict[str, Any]] = None) -> str:
    import json
    out = dict(base or {})
    out[key] = servers
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def _render_mcp_toml(servers: Dict[str, Any], key: str) -> str:
    """Codex 的 ~/.codex/config.toml 用 [mcp_servers.<name>] 表头。"""
    lines: List[str] = []
    for name, conf in servers.items():
        lines.append(f"[{key}.{name}]")
        if isinstance(conf, dict):
            for k, v in conf.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                elif isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, list):
                    items = ", ".join(
                        f'"{x}"' if isinstance(x, str) else str(x) for x in v
                    )
                    lines.append(f"{k} = [{items}]")
                elif isinstance(v, dict):
                    lines.append(f"")
                    lines.append(f"[{key}.{name}.{k}]")
                    for sk, sv in v.items():
                        if isinstance(sv, str):
                            lines.append(f'{sk} = "{sv}"')
                        else:
                            lines.append(f"{sk} = {sv}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_mcp(agent_key: str, mcp: Dict[str, Any], writer: Writer) -> None:
    cfg = AGENT_CONFIGS[agent_key]
    mf = cfg.get("mcp_file")
    if not mf:
        return
    servers = mcp.get("servers") or {}
    if not servers:
        return
    fmt = cfg.get("mcp_format", "json")
    key = cfg.get("mcp_key", "mcpServers")
    target = writer.dst_root / mf

    if fmt == "toml":
        content = _render_mcp_toml(servers, key)
    else:
        # 如果目标文件已存在,优先合并:把已有 mcp_key 替换成新值
        base: Dict[str, Any] = {}
        if target.is_file() and not writer.dry_run:
            try:
                import json as _json
                base = _json.loads(target.read_text(encoding="utf-8"))
                if not isinstance(base, dict):
                    base = {}
            except Exception:
                base = {}
        content = _render_mcp_json(servers, key, base)
    writer.write_text(target, content)


# ---- 5. settings / hooks ---------------------------------------------------
def discover_settings(agent_key: str, root: Path) -> Optional[Path]:
    cfg = AGENT_CONFIGS[agent_key]
    sf = cfg.get("settings_file")
    if not sf:
        return None
    p = root / sf
    return p if p.is_file() else None


def write_settings(agent_key: str, src_path: Path, writer: Writer) -> None:
    """settings 在不同 agent 间结构差异极大,这里仅按目标路径原样拷贝并提示警告。"""
    cfg = AGENT_CONFIGS[agent_key]
    sf = cfg.get("settings_file")
    if not sf:
        print(f"  [warn] {agent_key} 不支持 settings,跳过")
        return
    writer.copy_file(src_path, writer.dst_root / sf)
    print(f"  [warn] settings 已按路径拷贝,但不同 agent 的 schema 可能不兼容,请人工核对")


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
SYNC_CATEGORIES = ["skills", "rules", "context", "commands", "agents", "mcp", "settings"]


# ============================================================================
# sync 模式 (`agent_convert.py all`): 全局自动扫描 + 冲突裁决 + 双向同步
# ============================================================================
@dataclass
class Candidate:
    """同一逻辑项在不同 agent 里的某个具体来源。"""
    agent: str
    name: str
    src_path: Path                # 用于 mtime / 显示
    canonical: str                # 用于内容比较的规范化字符串
    payload: Any                  # 实际对象 (Skill / Path / dict 等)


def detect_active_agents(root: Path) -> List[str]:
    """探测项目里实际有内容的 agent。"""
    active: List[str] = []
    for key, cfg in AGENT_CONFIGS.items():
        paths_to_check: List[str] = []
        for k in ("dir", "rules_dir", "context_file", "commands_dir",
                 "agents_dir", "mcp_file", "settings_file"):
            v = cfg.get(k)
            if v:
                paths_to_check.append(v)
        for p in paths_to_check:
            full = root / p
            if full.exists():
                active.append(key)
                break
    return active


def _canon_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").strip()


def _file_canon(path: Path) -> str:
    try:
        return _canon_text(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return path.read_bytes().hex()
        except Exception:
            return ""


def _prompt_conflict(category: str, name: str, cands: List[Candidate],
                     prefer: Optional[str], auto: Optional[str]) -> Optional[Candidate]:
    """冲突裁决: 返回选定 candidate, 或 None 表示跳过。"""
    # 1) 先看内容是否其实一致
    canons = {c.canonical for c in cands}
    if len(canons) == 1:
        return cands[0]                   # 没冲突
    # 2) --prefer
    if prefer:
        for c in cands:
            if c.agent == prefer:
                print(f"  [auto-prefer={prefer}] {category}:{name} → {c.agent}")
                return c
    # 3) --auto
    if auto == "newest":
        c = max(cands, key=lambda x: x.src_path.stat().st_mtime if x.src_path.exists() else 0)
        print(f"  [auto-newest] {category}:{name} → {c.agent} ({c.src_path})")
        return c
    if auto == "skip":
        print(f"  [auto-skip] 跳过 {category}:{name}")
        return None
    if auto == "first":
        return cands[0]
    # 4) 交互
    print()
    print(f"!! 冲突: {category} \"{name}\" 在多个 agent 里内容不同:")
    for i, c in enumerate(cands, 1):
        try:
            mtime_str = ""
            if c.src_path.exists():
                import datetime
                mt = datetime.datetime.fromtimestamp(c.src_path.stat().st_mtime)
                mtime_str = mt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            mtime_str = "?"
        preview = c.canonical.replace("\n", " | ")[:80]
        print(f"  [{i}] {c.agent:14s} {mtime_str}  ({len(c.canonical)} 字)")
        print(f"      {preview}")
    print(f"  [s] 跳过这一项     [q] 退出整个同步")
    while True:
        try:
            choice = input(f"  请选择 [1-{len(cands)}/s/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] 已取消"); sys.exit(130)
        if choice == "s":
            return None
        if choice == "q":
            print("[!] 用户主动退出"); sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(cands):
            return cands[int(choice) - 1]


# ---------- 各类目从所有 agent 中收集 candidates ----------
def _collect_skills(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {}
    for agent in agents:
        skills, _ = discover_from_agent(agent, root)
        for sk in skills:
            canon = _canon_text(sk.description) + "\n---BODY---\n" + _canon_text(sk.body)
            # 用 frontmatter file 路径(skill 目录或单文件)作为 src_path
            src = sk.src_root if sk.src_root.exists() else root
            out.setdefault(sk.name, []).append(
                Candidate(agent, sk.name, src, canon, sk)
            )
    return out


def _collect_rules(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {}
    for agent in agents:
        for r in _discover_rules(agent, root):
            out.setdefault(r.name, []).append(
                Candidate(agent, r.name, r, _file_canon(r), r)
            )
    return out


def _collect_context(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {"<context>": []}
    for agent in agents:
        p = discover_context(agent, root)
        if p:
            out["<context>"].append(
                Candidate(agent, "<context>", p, _canon_text(p.read_text(encoding="utf-8")), p)
            )
    return out if out["<context>"] else {}


def _collect_commands(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {}
    for agent in agents:
        for f in discover_commands(agent, root):
            base = f.name
            for sfx in (".agent.md", ".prompt.md"):
                if base.endswith(sfx):
                    base = base[: -len(sfx)] + ".md"; break
            out.setdefault(base, []).append(
                Candidate(agent, base, f, _file_canon(f), f)
            )
    return out


def _collect_agents(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {}
    for agent in agents:
        for f in discover_agents(agent, root):
            base = f.name
            for sfx in (".agent.md", ".md"):
                if base.endswith(sfx):
                    base = base[: -len(sfx)] + ".md"; break
            out.setdefault(base, []).append(
                Candidate(agent, base, f, _file_canon(f), f)
            )
    return out


def _collect_mcp(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    """整个 mcp 配置作为一项,canonical = 排序后的 servers JSON。"""
    import json
    out: Dict[str, List[Candidate]] = {"<mcp>": []}
    for agent in agents:
        d = discover_mcp(agent, root)
        if d.get("servers"):
            cfg = AGENT_CONFIGS[agent]
            src = root / cfg["mcp_file"]
            canon = json.dumps(d["servers"], sort_keys=True, ensure_ascii=False)
            out["<mcp>"].append(Candidate(agent, "<mcp>", src, canon, d))
    return out if out["<mcp>"] else {}


def _collect_settings(root: Path, agents: List[str]) -> Dict[str, List[Candidate]]:
    out: Dict[str, List[Candidate]] = {"<settings>": []}
    for agent in agents:
        p = discover_settings(agent, root)
        if p:
            out["<settings>"].append(
                Candidate(agent, "<settings>", p, _file_canon(p), p)
            )
    return out if out["<settings>"] else {}


# ---------- 把已裁决的内容写到所有目标 agent ----------
def _write_resolved(category: str, chosen: Candidate, all_targets: List[str], writer: Writer) -> None:
    if category == "skills":
        sk: Skill = chosen.payload
        for to_key in all_targets:
            cfg = AGENT_CONFIGS[to_key]
            fmt = cfg["format"]
            if fmt == "skill":
                write_skill_format(to_key, sk, writer)
            elif fmt == "markdown":
                write_markdown_command(to_key, sk, writer, source_id=chosen.agent)
            elif fmt == "toml":
                write_toml_command(to_key, sk, writer)
    elif category == "rules":
        for to_key in all_targets:
            write_rules(to_key, [chosen.payload], writer)
    elif category == "context":
        text = chosen.payload.read_text(encoding="utf-8")
        for to_key in all_targets:
            if AGENT_CONFIGS[to_key].get("context_file"):
                write_context(to_key, text, writer)
    elif category == "commands":
        for to_key in all_targets:
            if AGENT_CONFIGS[to_key].get("commands_dir"):
                write_commands(to_key, [chosen.payload], writer)
    elif category == "agents":
        for to_key in all_targets:
            if AGENT_CONFIGS[to_key].get("agents_dir"):
                write_agents(to_key, [chosen.payload], writer)
    elif category == "mcp":
        for to_key in all_targets:
            if AGENT_CONFIGS[to_key].get("mcp_file"):
                write_mcp(to_key, chosen.payload, writer)
    elif category == "settings":
        for to_key in all_targets:
            if AGENT_CONFIGS[to_key].get("settings_file"):
                write_settings(to_key, chosen.payload, writer)


def sync_all(root: Path, dry_run: bool = False, sync: Optional[List[str]] = None,
             prefer: Optional[str] = None, auto: Optional[str] = None,
             targets: Optional[List[str]] = None) -> None:
    """全局 sync 模式: 扫描所有 agent → 合并 → 解决冲突 → 写回所有。"""
    enabled = set(sync or SYNC_CATEGORIES)

    active = detect_active_agents(root)
    if not active:
        print(f"[!] 在 {root} 下没有发现任何 agent 的内容"); return

    all_targets = targets or list(AGENT_CONFIGS.keys())

    print(f"项目根目录: {root}")
    print(f"检测到内容的 agent: {active}")
    print(f"将同步到所有 agent: {all_targets}")
    print(f"sync:    {sorted(enabled)}")
    print(f"prefer:  {prefer}    auto:    {auto}    dry-run: {dry_run}")
    print("=" * 60)

    collectors = {
        "skills":   _collect_skills,
        "rules":    _collect_rules,
        "context":  _collect_context,
        "commands": _collect_commands,
        "agents":   _collect_agents,
        "mcp":      _collect_mcp,
        "settings": _collect_settings,
    }

    writer = Writer(root, dry_run=dry_run)
    total_resolved = 0

    for cat in SYNC_CATEGORIES:
        if cat not in enabled:
            continue
        collected = collectors[cat](root, active)
        if not collected:
            continue
        print(f"\n>>> 类目 [{cat}]  共 {len(collected)} 项")
        for name, cands in collected.items():
            chosen = _prompt_conflict(cat, name, cands, prefer, auto)
            if chosen is None:
                continue
            display = chosen.agent
            if len(cands) > 1 and len({c.canonical for c in cands}) == 1:
                display = "(全部一致)"
            print(f"  · {name:30s} → 选用 {display}")
            _write_resolved(cat, chosen, all_targets, writer)
            total_resolved += 1

    print("\n" + "=" * 60)
    print(f"完成! 共 {total_resolved} 项已分发, 写入/拷贝 {len(writer.created)} 个文件"
          f"{'(dry-run 未实际写)' if dry_run else ''}")


# ============================================================================
# 单源 → 多目标 (原 convert 模式)
# ============================================================================
def convert(
    src_root: Path,
    dst_root: Path,
    from_agent: str,
    to_agents: List[str],
    items_filter: Optional[List[str]] = None,
    dry_run: bool = False,
    sync: Optional[List[str]] = None,
) -> None:
    if from_agent not in AGENT_CONFIGS:
        print(f"[!] 未知源 agent: {from_agent}（支持的见 --list）"); sys.exit(2)

    enabled = set(sync or SYNC_CATEGORIES)
    src_cfg = AGENT_CONFIGS[from_agent]

    # ---- 发现源端所有可同步内容 ----
    skills, rules = discover_from_agent(from_agent, src_root)
    if items_filter and "skills" in enabled:
        wanted = set(items_filter)
        skills = [s for s in skills if s.name in wanted]

    context_path = discover_context(from_agent, src_root) if "context" in enabled else None
    context_text = context_path.read_text(encoding="utf-8") if context_path else None
    commands_files = discover_commands(from_agent, src_root) if "commands" in enabled else []
    agents_files = discover_agents(from_agent, src_root) if "agents" in enabled else []
    mcp_data = discover_mcp(from_agent, src_root) if "mcp" in enabled else {}
    settings_path = discover_settings(from_agent, src_root) if "settings" in enabled else None

    nothing = (
        not skills and not rules and not context_path
        and not commands_files and not agents_files
        and not mcp_data.get("servers") and not settings_path
    )
    if nothing:
        print(f"[!] 在 {from_agent} 项目下没有发现任何可同步内容"); return

    # ---- 概要 ----
    print(f"源目录:   {src_root}")
    print(f"目标目录: {dst_root}")
    print(f"from:     {from_agent}  ({src_cfg['name']}, format={src_cfg['format']}, dir={src_cfg['dir']})")
    print(f"to:       {to_agents}")
    print(f"sync:     {sorted(enabled)}")
    print(f"  · skills   : {[s.name for s in skills] if 'skills' in enabled else '<skip>'}")
    print(f"  · rules    : {[r.name for r in rules] if 'rules' in enabled else '<skip>'}")
    print(f"  · context  : {context_path.name if context_path else None}")
    print(f"  · commands : {[c.name for c in commands_files]}")
    print(f"  · agents   : {[a.name for a in agents_files]}")
    print(f"  · mcp      : {list((mcp_data.get('servers') or {}).keys())}")
    print(f"  · settings : {settings_path.name if settings_path else None}")
    print(f"dry-run:  {dry_run}")
    print("=" * 60)

    writer = Writer(dst_root, dry_run=dry_run)

    for to_key in to_agents:
        if to_key not in AGENT_CONFIGS:
            print(f"[skip] 未知 agent: {to_key}"); continue
        if to_key == from_agent and src_root == dst_root:
            print(f"[skip] {to_key} 与源相同且 src==dst,跳过避免覆盖自身"); continue

        cfg = AGENT_CONFIGS[to_key]
        print(f"\n>>> 转到 [{to_key}] ({cfg['name']}) format={cfg['format']} dir={cfg['dir']}")

        # 1) skills
        if "skills" in enabled and skills:
            for sk in skills:
                fmt = cfg["format"]
                if fmt == "skill":
                    write_skill_format(to_key, sk, writer)
                elif fmt == "markdown":
                    write_markdown_command(to_key, sk, writer, source_id=from_agent)
                elif fmt == "toml":
                    write_toml_command(to_key, sk, writer)
                else:
                    print(f"  [skip] 不支持的 format: {fmt}")

        # 2) rules
        if "rules" in enabled and rules:
            write_rules(to_key, rules, writer)

        # 3) context
        if "context" in enabled and context_text is not None:
            if cfg.get("context_file"):
                write_context(to_key, context_text, writer)
            else:
                print(f"  [skip-context] {to_key} 没有 context_file 路径")

        # 4) commands
        if "commands" in enabled and commands_files:
            if cfg.get("commands_dir"):
                write_commands(to_key, commands_files, writer)
            else:
                print(f"  [skip-commands] {to_key} 没有 commands_dir")

        # 5) agents
        if "agents" in enabled and agents_files:
            if cfg.get("agents_dir"):
                write_agents(to_key, agents_files, writer)
            else:
                print(f"  [skip-agents] {to_key} 没有 agents_dir")

        # 6) mcp
        if "mcp" in enabled and mcp_data.get("servers"):
            if cfg.get("mcp_file"):
                write_mcp(to_key, mcp_data, writer)
            else:
                print(f"  [skip-mcp] {to_key} 没有 mcp_file")

        # 7) settings
        if "settings" in enabled and settings_path:
            if cfg.get("settings_file"):
                write_settings(to_key, settings_path, writer)
            else:
                print(f"  [skip-settings] {to_key} 没有 settings_file")

    print("\n" + "=" * 60)
    print(f"完成！共写入/拷贝 {len(writer.created)} 个文件{'(dry-run 未实际写)' if dry_run else ''}")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _parse_agents(raw: str) -> List[str]:
    if raw.lower() == "all":
        return list(AGENT_CONFIGS.keys())
    return [a.strip() for a in raw.split(",") if a.strip()]


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="agent_convert.py",
        description="通用 AI Agent 转换器 (任意 agent → 任意 agent, 7 类同步内容)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "两种模式:\n"
            "  ① convert 模式 (单源 → 多目标):\n"
            "       agent_convert.py codebuddy claude\n"
            "       agent_convert.py claude all\n"
            "  ② sync 模式 (扫描所有 agent → 合并冲突 → 双向同步):\n"
            "       agent_convert.py all                       # 交互式裁决冲突\n"
            "       agent_convert.py all --prefer claude       # 冲突时 claude 总是赢\n"
            "       agent_convert.py all --auto newest         # 冲突时取最新修改的\n"
            "       agent_convert.py all --auto skip           # 冲突时全部跳过\n"
            "       agent_convert.py all --auto first          # 取扫描到的第一个\n\n"
            "可同步的 7 类内容(--sync 控制):\n"
            "  skills    技能/命令本体 + 资源文件 (默认开)\n"
            "  rules     规则文件 (.codebuddy/rules 等, 默认开)\n"
            "  context   项目记忆文件 (CLAUDE.md / GEMINI.md / AGENTS.md ...)\n"
            "  commands  斜杠命令 (.claude/commands 等)\n"
            "  agents    子代理 (.claude/agents 等)\n"
            "  mcp       MCP 服务器配置 (.mcp.json / config.toml)\n"
            "  settings  hooks / settings 文件\n\n"
            "更多示例:\n"
            "  agent_convert.py codebuddy claude -i my-skill -n\n"
            "  agent_convert.py all --sync mcp,context\n"
            "  agent_convert.py all --skip settings,agents -n\n"
            "  agent_convert.py --list\n"
        ),
    )
    parser.add_argument("from_agent", nargs="?",
                        help='源 agent;或 "all" 进入 sync 模式')
    parser.add_argument("to_agents", nargs="?",
                        help='目标 agent,逗号分隔;"all" 表示全部其它 agent')
    parser.add_argument("--src", default=".", help="源根目录(默认当前目录)")
    parser.add_argument("--dst", default=None, help="目标根目录(默认与 --src 相同)")
    parser.add_argument("-i", "--item", dest="items", action="append", default=None,
                        help="只转某个技能/命令名,可重复。例: -i luoke-data-updater")
    parser.add_argument("--skill", dest="items", action="append",
                        help="同 --item,向后兼容")
    parser.add_argument("--sync", default=None,
                        help='只同步指定类目,逗号分隔。可选: skills,rules,context,commands,agents,mcp,settings')
    parser.add_argument("--skip", default=None,
                        help='跳过指定类目,逗号分隔(与 --sync 互斥)')
    parser.add_argument("--prefer", default=None,
                        help="(sync 模式) 冲突时偏好哪个 agent,例: --prefer claude")
    parser.add_argument("--auto", default=None, choices=["newest", "skip", "first"],
                        help="(sync 模式) 非交互冲突解决策略")
    parser.add_argument("-n", "--dry-run", action="store_true", help="只预览不写")
    parser.add_argument("-l", "--list", action="store_true", help="列出支持的 agent")
    args = parser.parse_args(argv)

    if args.list:
        col_keys = [
            ("skills",   "dir"),
            ("rules",    "rules_dir"),
            ("context",  "context_file"),
            ("commands", "commands_dir"),
            ("agents",   "agents_dir"),
            ("mcp",      "mcp_file"),
            ("settings", "settings_file"),
        ]
        header = f"  {'agent':14s}  " + "  ".join(f"{c[0]:8s}" for c in col_keys)
        print(header)
        print("  " + "-" * (len(header) - 2))
        for k, v in AGENT_CONFIGS.items():
            cells = []
            for cat, key in col_keys:
                if cat in ("commands", "agents") and v.get(key) and v.get(key) == v.get("dir"):
                    cells.append(f"{'(skill)':8s}")
                elif v.get(key):
                    cells.append(f"{'Y':8s}")
                else:
                    cells.append(f"{'--':8s}")
            print(f"  {k:14s}  " + "  ".join(cells))
        return

    # ---- 解析 --sync / --skip ----
    sync_set: Optional[List[str]] = None
    if args.sync and args.skip:
        print("[!] --sync 与 --skip 互斥,请只用其中一个"); sys.exit(2)
    if args.sync:
        sync_set = [s.strip() for s in args.sync.split(",") if s.strip()]
        unknown = [s for s in sync_set if s not in SYNC_CATEGORIES]
        if unknown:
            print(f"[!] 未知 --sync 类目: {unknown} (可选: {SYNC_CATEGORIES})"); sys.exit(2)
    elif args.skip:
        skip = [s.strip() for s in args.skip.split(",") if s.strip()]
        unknown = [s for s in skip if s not in SYNC_CATEGORIES]
        if unknown:
            print(f"[!] 未知 --skip 类目: {unknown} (可选: {SYNC_CATEGORIES})"); sys.exit(2)
        sync_set = [c for c in SYNC_CATEGORIES if c not in skip]

    # ---- sync 模式: agent_convert.py all (无第二个位置参数) ----
    if args.from_agent == "all" and not args.to_agents:
        root = Path(args.src).resolve()
        sync_all(
            root=root,
            dry_run=args.dry_run,
            sync=sync_set,
            prefer=args.prefer,
            auto=args.auto,
        )
        return

    # ---- convert 模式: 必须两个位置参数 ----
    if not args.from_agent or not args.to_agents:
        parser.print_help()
        sys.exit(0 if not (args.from_agent or args.to_agents) else 2)

    src_root = Path(args.src).resolve()
    dst_root = Path(args.dst).resolve() if args.dst else src_root
    to_agents = _parse_agents(args.to_agents)

    convert(
        src_root=src_root,
        dst_root=dst_root,
        from_agent=args.from_agent,
        to_agents=to_agents,
        items_filter=args.items,
        dry_run=args.dry_run,
        sync=sync_set,
    )


if __name__ == "__main__":
    main()
