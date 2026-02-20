"""Deterministic upsert/remove operator for <PLAN> files."""

import argparse
import json
import re
from pathlib import Path

PLAN_RE = re.compile(r"<PLAN>\s*(.*?)\s*</PLAN>", re.DOTALL)
ITEM_RE = re.compile(r"^- \[(todo|doing|done|aborted)\]\[(\d+)\] (.+)$")
VALID_STATUS = {"todo", "doing", "done", "aborted"}


def parse_plan(text: str) -> list[dict[str, str]]:
    """Parse a strict <PLAN> block into ordered plan items."""
    match = PLAN_RE.search(text)
    if not match:
        raise ValueError("Missing <PLAN>...</PLAN> block.")

    body = match.group(1).strip()
    if not body:
        return []

    items: list[dict[str, str]] = []
    expected_id = 1
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        item_match = ITEM_RE.fullmatch(line)
        if not item_match:
            raise ValueError(
                f"Invalid plan line: {raw!r}. Expected '- [status][id] <text>'."
            )

        status, id_str, title = item_match.groups()
        line_id = int(id_str)
        if line_id != expected_id:
            raise ValueError(
                f"Invalid plan id sequence: expected {expected_id}, got {line_id}."
            )
        title = title.strip()
        if not title:
            raise ValueError("Plan item title cannot be empty.")
        items.append({"status": status, "title": title})
        expected_id += 1
    return items


def render_plan_block(items: list[dict[str, str]]) -> str:
    """Render canonical <PLAN> block and always reindex ids from 1."""
    if not items:
        return "<PLAN>\n</PLAN>"

    lines: list[str] = []
    for idx, item in enumerate(items, start=1):
        status = item["status"]
        title = item["title"].strip()
        if status not in VALID_STATUS:
            raise ValueError(f"Invalid status: {status!r}.")
        if not title:
            raise ValueError("Plan item title cannot be empty.")
        lines.append(f"- [{status}][{idx}] {title}")
    return "<PLAN>\n" + "\n".join(lines) + "\n</PLAN>"


def _is_positive_int(value: object) -> bool:
    """Return True only for positive integers (exclude bool)."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _parse_items_json(items_json: str) -> list[dict[str, object]]:
    """Parse and validate upsert payload."""
    try:
        payload = json.loads(items_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --items-json: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("--items-json must be a non-empty JSON array.")

    normalized: list[dict[str, object]] = []
    seen_ids: set[int] = set()
    for idx, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"--items-json[{idx}] must be an object.")

        keys = set(raw.keys())
        if keys - {"id", "status", "title"}:
            extra = ", ".join(sorted(keys - {"id", "status", "title"}))
            raise ValueError(f"--items-json[{idx}] has unsupported keys: {extra}.")

        status = raw.get("status")
        title = raw.get("title")
        item_id = raw.get("id")

        if status not in VALID_STATUS:
            raise ValueError(
                f"--items-json[{idx}].status must be one of {sorted(VALID_STATUS)}."
            )
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"--items-json[{idx}].title must be a non-empty string.")

        normalized_item: dict[str, object] = {
            "status": status,
            "title": title.strip(),
            "id": None,
        }
        if item_id is not None:
            if not _is_positive_int(item_id):
                raise ValueError(f"--items-json[{idx}].id must be a positive integer.")
            if item_id in seen_ids:
                raise ValueError(f"Duplicate upsert id in payload: {item_id}.")
            seen_ids.add(item_id)
            normalized_item["id"] = item_id
        normalized.append(normalized_item)

    return normalized


def upsert_items(
    plan: list[dict[str, str]], updates: list[dict[str, object]]
) -> list[dict[str, str]]:
    """Upsert one or more items. Missing id means append."""
    result = [{"status": item["status"], "title": item["title"]} for item in plan]

    for update in updates:
        status = str(update["status"])
        title = str(update["title"])
        item_id = update.get("id")
        if item_id is None:
            result.append({"status": status, "title": title})
            continue

        target_id = int(item_id)
        if target_id > len(result):
            raise ValueError(
                f"Upsert target id out of range: {target_id}. Current max id is {len(result)}."
            )
        result[target_id - 1] = {"status": status, "title": title}
    return result


def _parse_remove_ids(ids_csv: str) -> list[int]:
    """Parse comma-separated positive ids for remove operation."""
    raw_parts = [part.strip() for part in ids_csv.split(",")]
    parts = [part for part in raw_parts if part]
    if not parts:
        raise ValueError("--ids must contain at least one id.")

    ids: list[int] = []
    seen: set[int] = set()
    for raw in parts:
        if not raw.isdigit() or raw == "0":
            raise ValueError(f"Invalid id in --ids: {raw!r}.")
        value = int(raw)
        if value in seen:
            raise ValueError(f"Duplicate id in --ids: {value}.")
        seen.add(value)
        ids.append(value)
    return ids


def remove_items(plan: list[dict[str, str]], ids: list[int]) -> list[dict[str, str]]:
    """Remove one or more items by current dynamic ids."""
    result = [{"status": item["status"], "title": item["title"]} for item in plan]

    max_id = len(result)
    for value in ids:
        if value > max_id:
            raise ValueError(f"Remove id out of range: {value}. Current max id is {max_id}.")

    for value in sorted(ids, reverse=True):
        del result[value - 1]
    return result


def mutate_plan_file(
    plan_path: str | Path,
    op: str,
    items_json: str | None,
    ids_csv: str | None,
) -> str:
    """Apply a single upsert/remove operation, persist, and return new plan text."""
    path = Path(plan_path)
    if path.exists():
        original = path.read_text(encoding="utf-8")
    else:
        original = "<PLAN>\n</PLAN>\n"

    current = parse_plan(original)

    if op == "upsert":
        if items_json is None:
            raise ValueError("--op upsert requires --items-json.")
        if ids_csv is not None:
            raise ValueError("--ids is only valid for --op remove.")
        next_items = upsert_items(current, _parse_items_json(items_json))
    elif op == "remove":
        if ids_csv is None:
            raise ValueError("--op remove requires --ids.")
        if items_json is not None:
            raise ValueError("--items-json is only valid for --op upsert.")
        next_items = remove_items(current, _parse_remove_ids(ids_csv))
    else:
        raise ValueError(f"Unsupported op: {op!r}.")

    output = render_plan_block(next_items)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{output}\n", encoding="utf-8")
    return output


def main() -> None:
    """CLI: mutate <PLAN> by upsert/remove and print updated canonical block."""
    parser = argparse.ArgumentParser(description="Mutate a <PLAN> file by upsert/remove")
    parser.add_argument("--plan", required=True, help="Path to plan file")
    parser.add_argument(
        "--op", required=True, choices=["upsert", "remove"], help="Mutation operation"
    )
    parser.add_argument(
        "--items-json",
        help="JSON array for upsert, item fields: id(optional), status, title",
    )
    parser.add_argument("--ids", help="Comma-separated ids for remove, e.g. 1,3,5")
    args = parser.parse_args()
    print(mutate_plan_file(args.plan, args.op, args.items_json, args.ids))


if __name__ == "__main__":
    main()
