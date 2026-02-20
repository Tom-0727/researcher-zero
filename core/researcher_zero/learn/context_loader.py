from pathlib import Path

from core.researcher_zero.learn.prompts import get_plan_system_prompt

REQUIRED_CONTEXT_PATHS = {
    "basic_info": "Basic_Context/basic_info.md",
    "taxonomy": "Basic_Context/taxonomy.md",
    "network": "Cognition/network.md",
    "main_challenge": "Cognition/main_challenge.md",
}


def resolve_workspace(workspace: str) -> Path:
    """Resolve and validate workspace directory."""
    path = Path(workspace).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Invalid workspace directory: {path}")
    return path


def resolve_plan_file(workspace: Path, plan_file: str | None = None) -> Path:
    """Resolve plan file path, default to <workspace>/plan.md."""
    if plan_file:
        resolved = Path(plan_file).expanduser().resolve()
    else:
        resolved = workspace / "plan.md"
    return resolved


def load_required_context(workspace: Path) -> dict[str, str]:
    """Load required workspace context files with strict validation."""
    loaded: dict[str, str] = {}
    for key, relative_path in REQUIRED_CONTEXT_PATHS.items():
        target = workspace / relative_path
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Missing required context file: {target}")
        loaded[key] = target.read_text(encoding="utf-8").strip()
    return loaded


def summarize_workspace_notes(workspace: Path, limit_files: int = 20) -> str:
    """Summarize existing markdown notes except required context files."""
    excluded = {
        (workspace / relative).resolve()
        for relative in REQUIRED_CONTEXT_PATHS.values()
    }
    summaries: list[str] = []
    for path in sorted(workspace.rglob("*.md")):
        resolved = path.resolve()
        if resolved in excluded:
            continue
        if ".read_cache" in resolved.parts:
            continue
        rel = resolved.relative_to(workspace).as_posix()
        text = resolved.read_text(encoding="utf-8").strip()
        if not text:
            continue
        summaries.append(f"[{rel}]\n{text[:1200]}")
        if len(summaries) >= limit_files:
            break
    if not summaries:
        return "(none)"
    return "\n\n".join(summaries)


def build_plan_context_payload(
    *,
    workspace: str,
    task: str,
    skill_runtime_prompt: str,
    plan_file: str | None = None,
) -> dict[str, str | list[str]]:
    """Build plan-stage prompt payload from workspace and runtime metadata."""
    workspace_path = resolve_workspace(workspace)
    resolved_plan_file = resolve_plan_file(workspace_path, plan_file=plan_file)
    context = load_required_context(workspace_path)
    notes_summary = summarize_workspace_notes(workspace_path)
    system_prompt = get_plan_system_prompt(
        task=task,
        basic_info=context["basic_info"],
        taxonomy=context["taxonomy"],
        network=context["network"],
        main_challenge=context["main_challenge"],
        workspace_notes=notes_summary,
        skill_runtime_prompt=skill_runtime_prompt,
    )
    return {
        "workspace": str(workspace_path),
        "plan_file": str(resolved_plan_file),
        "system_prompt": system_prompt,
        "workspace_notes_summary": notes_summary,
    }
