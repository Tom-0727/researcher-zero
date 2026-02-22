from pathlib import Path

from core.services.learn.prompts import get_learn_system_prompt

REQUIRED_CONTEXT_PATHS = {
    "basic_info": "Basic_Context/basic_info.md",
    "taxonomy": "Basic_Context/taxonomy.md",
    "human_preference": "Alignment/human_preference.md",
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


def build_learn_context_payload(
    *,
    workspace: str,
    task: str,
    plan_file: str | None = None,
) -> dict[str, str]:
    """Build shared learn-stage prompt payload from workspace context."""
    workspace_path = resolve_workspace(workspace)
    resolved_plan_file = resolve_plan_file(workspace_path, plan_file=plan_file)
    context = load_required_context(workspace_path)
    system_prompt = get_learn_system_prompt(
        task=task,
        basic_info=context["basic_info"],
        taxonomy=context["taxonomy"],
        human_preference=context["human_preference"],
        network=context["network"],
        main_challenge=context["main_challenge"],
    )
    return {
        "workspace": str(workspace_path),
        "plan_file": str(resolved_plan_file),
        "system_prompt": system_prompt,
    }
