from pathlib import Path

from .workspace import WorkspaceGuard


def list_files_in_workspace(
    guard: WorkspaceGuard,
    base_path: str = ".",
    recursive: bool = True,
    include_dirs: bool = False,
    include_hidden: bool = False,
) -> list[str]:
    base_abs = guard.resolve_path(base_path)
    if not base_abs.exists():
        return []

    if base_abs.is_file():
        return [base_abs.relative_to(guard.root).as_posix()]

    results: list[str] = []
    iterator = base_abs.rglob("*") if recursive else base_abs.glob("*")
    for item in iterator:
        rel = item.relative_to(guard.root).as_posix()
        if not include_hidden and any(part.startswith(".") for part in Path(rel).parts):
            continue
        if item.is_file() or (include_dirs and item.is_dir()):
            results.append(rel)
    return sorted(results)
