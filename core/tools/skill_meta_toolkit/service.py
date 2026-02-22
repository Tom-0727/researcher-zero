from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from langchain_core.tools import tool

from .toolkit import SkillToolkit


@dataclass(slots=True)
class SkillCapability:
  prompt: str
  tools: list[Any]
  toolkit: SkillToolkit


def build_agent_tools(toolkit: SkillToolkit) -> list[Any]:
  @tool
  def list_available_skills() -> str:
    """List all available skills with brief descriptions."""
    return toolkit.list_available_skills()

  @tool
  def load_skill(skill_name: str) -> str:
    """Load the full SKILL.md content for a skill by name."""
    return toolkit.load_skill(skill_name)

  @tool
  def find_skill_files(skill_name: str, pattern: str = "**/*", contains: str = "") -> str:
    """
    Find files under a skill directory.

    pattern: Glob pattern relative to skill directory, e.g. 'examples/*.md', '**/*.sql'.
    contains: Optional substring filter applied to file text for text files.
    """
    return toolkit.find_skill_files(skill_name, pattern, contains)

  @tool
  def read_skill_file(skill_name: str, relative_path: str, start_line: int = 1, max_lines: int = 200) -> str:
    """
    Read a text file in a skill directory with line numbers.

    `relative_path` must stay inside the skill directory.
    """
    return toolkit.read_skill_file(skill_name, relative_path, start_line, max_lines)

  @tool
  def load_skill_examples(skill_name: str, query: str, top_k: int = 3) -> str:
    """Load top-k relevant few-shot examples from skill/examples by tag/keyword overlap."""
    return toolkit.load_skill_examples(skill_name, query, top_k)

  tools: list[Any] = [
    list_available_skills,
    load_skill,
    find_skill_files,
    read_skill_file,
    load_skill_examples,
  ]

  if toolkit.allow_run_entry:

    @tool
    def run_skill_entry(skill_name: str, entry_args: str = "") -> str:
      """
      Execute the command declared by `entry` in SKILL.md frontmatter.

      Security defaults:
      - only programs in allowed_entry_programs
      - cwd fixed to the skill directory
      """
      return toolkit.run_skill_entry(skill_name, entry_args)

    tools.append(run_skill_entry)

  return tools


def build_skill_capability(
  roots: Sequence[str | Path] | str,
  *,
  max_files: int = 25,
  max_chars: int = 12_000,
  read_max_lines: int = 250,
  allow_run_entry: bool = False,
  command_timeout: int = 60,
  allowed_entry_programs: Sequence[str] = ("python", "python3", "bash", "sh"),
  only_tools: Sequence[str] | None = None,
) -> SkillCapability:
  """
  only_tools: 若提供，则只包含这些名称的 tool（如 "list_available_skills", "load_skill" 等）；None 表示全部。
  """
  toolkit = SkillToolkit(
    roots=roots,
    max_files=max_files,
    max_chars=max_chars,
    read_max_lines=read_max_lines,
    allow_run_entry=allow_run_entry,
    command_timeout=command_timeout,
    allowed_entry_programs=allowed_entry_programs,
  )
  tools = build_agent_tools(toolkit)
  if only_tools is not None:
    allowed = frozenset(only_tools)
    tools = [t for t in tools if t.name in allowed]
  return SkillCapability(
    prompt=toolkit.build_prompt(),
    tools=tools,
    toolkit=toolkit,
  )
