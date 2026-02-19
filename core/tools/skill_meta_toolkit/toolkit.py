from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import subprocess
from typing import Sequence

TOKEN = re.compile(r"[a-zA-Z0-9_]+")


@dataclass(slots=True)
class SkillExample:
  path: Path
  title: str
  tags: tuple[str, ...]
  content: str


@dataclass(slots=True)
class SkillRecord:
  name: str
  description: str
  path: Path
  directory: Path
  content: str
  entry: str | None
  examples: tuple[SkillExample, ...]


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
  if not text.startswith("---"):
    return {}, text
  lines = text.splitlines()
  if not lines or lines[0].strip() != "---":
    return {}, text
  stop = -1
  for idx, line in enumerate(lines[1:], start=1):
    if line.strip() == "---":
      stop = idx
      break
  if stop < 0:
    return {}, text
  data: dict[str, str] = {}
  for line in lines[1:stop]:
    line = line.strip()
    if not line or line.startswith("#") or ":" not in line:
      continue
    key, value = line.split(":", 1)
    data[key.strip().lower()] = value.strip().strip("'\"")
  body = "\n".join(lines[stop + 1 :]).lstrip("\n")
  return data, body


def _parse_tags(value: str | None) -> tuple[str, ...]:
  if not value:
    return ()
  raw = value.strip()
  if raw.startswith("[") and raw.endswith("]"):
    raw = raw[1:-1]
  parts = [x.strip().strip("'\"").lower() for x in raw.split(",")]
  return tuple(x for x in parts if x)


def _infer_description(text: str) -> str:
  for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    return line[:220]
  return "File-based skill with on-demand instructions."


def _tokenize(text: str) -> set[str]:
  return {token.lower() for token in TOKEN.findall(text)}


def _slice_with_line_numbers(text: str, start_line: int, max_lines: int) -> tuple[str, bool]:
  lines = text.splitlines()
  if start_line < 1:
    start_line = 1
  end = min(len(lines), start_line + max_lines - 1)
  payload = [f"{i + 1}: {line}" for i, line in enumerate(lines[start_line - 1 : end], start=start_line - 1)]
  return "\n".join(payload), end < len(lines)


def _scan_examples(skill_dir: Path) -> tuple[SkillExample, ...]:
  root = skill_dir / "examples"
  if not root.is_dir():
    return ()
  output: list[SkillExample] = []
  for path in sorted(root.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    title = meta.get("title") or path.stem.replace("_", " ")
    tags = _parse_tags(meta.get("tags"))
    output.append(
      SkillExample(
        path=path,
        title=title,
        tags=tags,
        content=body.strip(),
      )
    )
  return tuple(output)


def discover_skills(roots: Sequence[str | Path]) -> dict[str, SkillRecord]:
  output: dict[str, SkillRecord] = {}
  for root in roots:
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
      continue
    for path in sorted(base.rglob("SKILL.md")):
      text = path.read_text(encoding="utf-8")
      meta, body = _split_frontmatter(text)
      name = (meta.get("name") or path.parent.name).strip()
      description = (meta.get("description") or _infer_description(body)).strip()
      if not name or not description:
        continue
      output[name] = SkillRecord(
        name=name,
        description=description,
        path=path,
        directory=path.parent,
        content=body.strip(),
        entry=(meta.get("entry") or "").strip() or None,
        examples=_scan_examples(path.parent),
      )
  return output


class SkillToolkit:
  """
  Minimal file-based skills runtime for LangChain/LangGraph.

  Designed for progressive disclosure:
  - Prompt only contains lightweight skill metadata.
  - Full skill content is loaded by tool call on demand.
  """

  def __init__(
    self,
    roots: Sequence[str | Path] | str,
    *,
    max_files: int = 25,
    max_chars: int = 12_000,
    read_max_lines: int = 250,
    allow_run_entry: bool = False,
    command_timeout: int = 60,
    allowed_entry_programs: Sequence[str] = ("python", "python3", "bash", "sh"),
  ) -> None:
    self.roots = [Path(roots).expanduser()] if isinstance(roots, (str, Path)) else [Path(x).expanduser() for x in roots]
    self.max_files = max_files
    self.max_chars = max_chars
    self.read_max_lines = read_max_lines
    self.allow_run_entry = allow_run_entry
    self.command_timeout = command_timeout
    self.allowed_entry_programs = tuple(allowed_entry_programs)
    self.skills: dict[str, SkillRecord] = {}
    self.refresh()

  def refresh(self) -> None:
    self.skills = discover_skills(self.roots)

  def _skill(self, name: str) -> SkillRecord | None:
    return self.skills.get(name)

  def _available_lines(self) -> list[str]:
    rows = [f"- {item.name}: {item.description}" for item in sorted(self.skills.values(), key=lambda x: x.name)]
    return rows or ["- (none)"]

  def build_prompt(self) -> str:
    """
    Prompt addendum for your system prompt.
    """
    return "\n".join(
      [
        "## Skills Runtime",
        "You can use file-based skills through tools with progressive disclosure.",
        "Workflow:",
        "1. Use `list_available_skills` when unsure which skill fits the task.",
        "2. Call `load_skill` before solving domain-specific requests.",
        "3. If the skill references files, use `find_skill_files` and `read_skill_file`.",
        "4. If examples are needed, call `load_skill_examples` to load matching few-shot examples.",
        "5. If a skill exposes an entry command and run permission is enabled, use `run_skill_entry`.",
        "",
        "Available skills:",
        *self._available_lines(),
      ]
    )

  def list_available_skills(self) -> str:
    if not self.skills:
      return "No skills are available."
    return "\n".join(self._available_lines())

  def _sample_files(self, skill: SkillRecord) -> list[str]:
    files = [path.relative_to(skill.directory).as_posix() for path in sorted(skill.directory.rglob("*")) if path.is_file()]
    return files[: self.max_files]

  def _safe_path(self, skill: SkillRecord, rel: str) -> Path | None:
    target = (skill.directory / rel).resolve()
    if target == skill.directory:
      return target
    if skill.directory not in target.parents:
      return None
    return target

  def _match_examples(self, skill: SkillRecord, query: str, top_k: int) -> list[tuple[int, SkillExample]]:
    q = _tokenize(query)
    scored = []
    for ex in skill.examples:
      tag_tokens = _tokenize(" ".join(ex.tags))
      body_tokens = _tokenize(ex.title + " " + ex.content)
      score = len(q & body_tokens) + (2 * len(q & tag_tokens))
      scored.append((score, ex))
    ranked = sorted(scored, key=lambda x: x[0], reverse=True)
    filtered = [item for item in ranked if item[0] > 0]
    picked = filtered if filtered else ranked
    return picked[: max(1, min(top_k, 10))]

  def load_skill(self, skill_name: str) -> str:
    skill = self._skill(skill_name)
    if not skill:
      available = ", ".join(sorted(self.skills.keys())) or "none"
      return f"Skill '{skill_name}' not found. Available skills: {available}"
    files = "\n".join(f"- {file}" for file in self._sample_files(skill))
    return "\n".join(
      [
        f"<skill_content name=\"{skill.name}\">",
        skill.content,
        "",
        f"Base directory: {skill.directory}",
        "Use find/read tools for files in this directory.",
        "",
        "<skill_files>",
        files or "- (none)",
        "</skill_files>",
        "</skill_content>",
      ]
    )

  def find_skill_files(self, skill_name: str, pattern: str = "**/*", contains: str = "") -> str:
    skill = self._skill(skill_name)
    if not skill:
      return f"Skill '{skill_name}' not found."
    matches = [path for path in sorted(skill.directory.glob(pattern)) if path.is_file()]
    if contains:
      token = contains.lower()
      filtered = []
      for path in matches:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if token in text.lower():
          filtered.append(path)
      matches = filtered
    rel = [path.relative_to(skill.directory).as_posix() for path in matches[:200]]
    if not rel:
      return "No matching files found."
    return "\n".join(rel)

  def read_skill_file(
    self,
    skill_name: str,
    relative_path: str,
    start_line: int = 1,
    max_lines: int = 200,
  ) -> str:
    skill = self._skill(skill_name)
    if not skill:
      return f"Skill '{skill_name}' not found."
    target = self._safe_path(skill, relative_path)
    if not target:
      return "Invalid path: path escapes the skill directory."
    if not target.exists():
      return f"File not found: {relative_path}"
    if target.is_dir():
      entries = [path.name + ("/" if path.is_dir() else "") for path in sorted(target.iterdir())]
      return "\n".join(entries[:200]) or "(empty directory)"
    text = target.read_text(encoding="utf-8", errors="ignore")
    snippet, truncated = _slice_with_line_numbers(text, start_line, min(max_lines, self.read_max_lines))
    if len(snippet) > self.max_chars:
      snippet = snippet[: self.max_chars]
      truncated = True
    suffix = "\n\n(Truncated)" if truncated else ""
    return f"{snippet}{suffix}"

  def load_skill_examples(self, skill_name: str, query: str, top_k: int = 3) -> str:
    skill = self._skill(skill_name)
    if not skill:
      return f"Skill '{skill_name}' not found."
    if not skill.examples:
      return "This skill has no examples directory or example markdown files."
    picked = self._match_examples(skill, query, top_k)
    blocks = []
    for idx, (score, ex) in enumerate(picked, start=1):
      rel = ex.path.relative_to(skill.directory).as_posix()
      body = ex.content[: self.max_chars]
      tags = ", ".join(ex.tags) if ex.tags else "-"
      blocks.append(
        "\n".join(
          [
            f"<example index=\"{idx}\" score=\"{score}\">",
            f"title: {ex.title}",
            f"tags: {tags}",
            f"source: {rel}",
            body,
            "</example>",
          ]
        )
      )
    return "\n\n".join(blocks)

  def run_skill_entry(self, skill_name: str, args: str = "") -> str:
    if not self.allow_run_entry:
      return "Entry execution is disabled. Set allow_run_entry=True to enable it."
    skill = self._skill(skill_name)
    if not skill:
      return f"Skill '{skill_name}' not found."
    if not skill.entry:
      return "This skill does not define an entry command."
    cmd = shlex.split(skill.entry)
    if args.strip():
      cmd.extend(shlex.split(args))
    program = Path(cmd[0]).name.lower()
    if program not in self.allowed_entry_programs:
      allowed = ", ".join(self.allowed_entry_programs)
      return f"Entry command blocked. Allowed programs: {allowed}"
    result = subprocess.run(
      cmd,
      cwd=skill.directory,
      text=True,
      capture_output=True,
      timeout=self.command_timeout,
    )
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    output = output[: self.max_chars] if len(output) > self.max_chars else output
    return "\n".join(
      [
        f"exit_code: {result.returncode}",
        f"command: {' '.join(cmd)}",
        "",
        output.strip() or "(no output)",
      ]
    )
