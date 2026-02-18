"""Deterministic plan parser and SEARCH/REPLACE-style plan editor."""

import argparse
import json
import re
import sys
from pathlib import Path

PLAN_RE = re.compile(r"<PLAN>\s*(.*?)\s*</PLAN>", re.DOTALL)
ITEM_RE = re.compile(r"^- (.+)$")


def parse_plan(text: str) -> list[str]:
    """Parse a strict <PLAN> block into a list of step strings."""
    match = PLAN_RE.search(text)
    if not match:
        raise ValueError("Missing <PLAN>...</PLAN> block.")
    body = match.group(1).strip()
    if not body:
        return []
    items = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        item_match = ITEM_RE.fullmatch(line)
        if not item_match:
            raise ValueError(f"Invalid plan line: {raw!r}. Expected '- <text>'.")
        items.append(item_match.group(1).strip())
    return items


def _render_plan(items: list[str]) -> str:
    """Render list items to normalized text used by patch matching."""
    if not items:
        return ""
    return "\n".join(f"- {item.strip()}" for item in items) + "\n"


def _normalize_patch_block(block_text: str) -> str:
    """Normalize SEARCH/REPLACE block lines to canonical bullet format."""
    stripped = block_text.strip()
    if not stripped:
        return ""
    lines = []
    for raw in stripped.splitlines():
        line = raw.strip()
        if not line:
            continue
        item_match = ITEM_RE.fullmatch(line)
        if not item_match:
            raise ValueError(f"Invalid patch line: {raw!r}. Expected '- <text>'.")
        lines.append(f"- {item_match.group(1).strip()}")
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_patch_blocks(patch_text: str) -> list[tuple[str, str]]:
    """Parse SEARCH/REPLACE patch blocks with strict markers."""
    lines = patch_text.splitlines()
    blocks: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line != "<<<<<<< SEARCH":
            raise ValueError(f"Unexpected patch line outside block: {lines[i]!r}")

        i += 1
        search_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "=======":
            search_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("Missing '=======' marker in patch block.")

        i += 1
        replace_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != ">>>>>>> REPLACE":
            replace_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("Missing '>>>>>>> REPLACE' marker in patch block.")

        blocks.append(("\n".join(search_lines), "\n".join(replace_lines)))
        i += 1
    return blocks


def apply_patch(plan: list[str], patch_text: str) -> list[str]:
    """Apply one or more SEARCH/REPLACE blocks to a plan list."""
    blocks = _parse_patch_blocks(patch_text)
    if not blocks:
        raise ValueError("No valid SEARCH/REPLACE block found.")

    content = _render_plan(plan)
    for search_raw, replace_raw in blocks:
        search = _normalize_patch_block(search_raw)
        replace = _normalize_patch_block(replace_raw)

        # Empty SEARCH means append.
        if not search:
            content += replace
            continue

        hits = content.count(search)
        if hits != 1:
            raise ValueError(f"SEARCH must match exactly once, found {hits}.")
        content = content.replace(search, replace, 1)

    return parse_plan(f"<PLAN>\n{content}</PLAN>")


def _read_text(path: str) -> str:
    """Read UTF-8 text from file path or stdin marker '-'."""
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> None:
    """Provide CLI access for parsing and patching plans."""
    parser = argparse.ArgumentParser(description="Plan parser/editor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse <PLAN> text to JSON list")
    parse_cmd.add_argument("input_path", help="Input file path or '-' for stdin")

    patch_cmd = sub.add_parser("patch", help="Apply patch to plan")
    patch_cmd.add_argument("--plan", required=True, help="Plan text file")
    patch_cmd.add_argument("--patch", required=True, help="Patch text file")

    args = parser.parse_args()
    if args.cmd == "parse":
        plan = parse_plan(_read_text(args.input_path))
        print(json.dumps(plan, ensure_ascii=False))
        return

    plan = parse_plan(_read_text(args.plan))
    patched = apply_patch(plan, _read_text(args.patch))
    print(json.dumps(patched, ensure_ascii=False))


if __name__ == "__main__":
    main()
