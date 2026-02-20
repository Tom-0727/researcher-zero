"""Single entry CLI for file_manage skill."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure this script also works when launched via:
# python core/skills/file_manage/scripts/file_manage_tool.py
SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from scripts.service import FileManager


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for workspace-scoped file operations."""
    parser = argparse.ArgumentParser(description="Workspace file manager skill entry")
    parser.add_argument("--workspace", required=True, help="Absolute workspace path")
    subparsers = parser.add_subparsers(dest="op", required=True)

    create = subparsers.add_parser("create", help="Create a file")
    create.add_argument("--path", required=True, help="Path inside workspace")
    create.add_argument("--content", default="", help="File content")
    create.add_argument("--overwrite", action="store_true", help="Overwrite if exists")

    list_cmd = subparsers.add_parser("list", help="List files")
    list_cmd.add_argument("--base-path", default=".", help="Base path inside workspace")
    list_cmd.add_argument("--flat", action="store_true", help="Disable recursive listing")
    list_cmd.add_argument("--include-dirs", action="store_true", help="Include directories")
    list_cmd.add_argument("--include-hidden", action="store_true", help="Include hidden files")

    edit = subparsers.add_parser("edit", help="Apply SEARCH/REPLACE to one file")
    edit.add_argument("--path", required=True, help="Path inside workspace")
    edit.add_argument("--search", required=True, help="Exact text to search")
    edit.add_argument("--replace", required=True, help="Replacement text")

    edit_blocks = subparsers.add_parser("edit-blocks", help="Apply multi-file edit blocks")
    edit_blocks.add_argument("--instruction", required=True, help="Edit block instruction text")

    return parser


def run_operation(args: argparse.Namespace) -> dict:
    """Execute selected operation and return JSON-serializable payload."""
    fm = FileManager(workspace_root=args.workspace)

    if args.op == "create":
        rel_path = fm.create_file(path=args.path, content=args.content, overwrite=args.overwrite)
        return {"op": "create", "path": rel_path}

    if args.op == "list":
        files = fm.list_files(
            base_path=args.base_path,
            recursive=not args.flat,
            include_dirs=args.include_dirs,
            include_hidden=args.include_hidden,
        )
        return {"op": "list", "files": files}

    if args.op == "edit":
        outcome = fm.edit_file(path=args.path, search=args.search, replace=args.replace)
        return {"op": "edit", "result": asdict(outcome)}

    outcomes = fm.apply_edit_blocks(instruction_text=args.instruction)
    return {"op": "edit-blocks", "results": [asdict(item) for item in outcomes]}


def main() -> None:
    """CLI entry."""
    args = build_parser().parse_args()
    result = run_operation(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
