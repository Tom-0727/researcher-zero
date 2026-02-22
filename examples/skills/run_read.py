import json

from core.tools.skill_meta_toolkit import SkillToolkit

TARGET_URL = "https://www.semanticscholar.org/reader/ecc51ce52ca524be17616a9c0dc8a051a2996ad7"


def parse_entry_json(output: str) -> dict:
    """从 run_skill_entry 返回文本中提取 JSON payload。"""
    lines = output.splitlines()
    if not lines or not lines[0].startswith("exit_code: "):
        raise ValueError("run_skill_entry 输出格式不符合预期。")
    exit_code = int(lines[0].split(": ", 1)[1])
    if exit_code != 0:
        raise RuntimeError(f"read skill 执行失败:\n{output}")

    payload_text = output.split("\n\n", 1)[1].strip()
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("read skill 返回的 JSON payload 必须是 object。")
    return payload


def main() -> None:
    toolkit = SkillToolkit(roots=["core/skills"], allow_run_entry=True)
    if "read" not in toolkit.skills:
        raise RuntimeError("未找到 read 技能")

    print("== 1) ingest 网页 ==")
    ingest_output = toolkit.run_skill_entry(
        "read",
        f'ingest --source {TARGET_URL} --title "url content"',
    )
    print(ingest_output)
    ingest_json = parse_entry_json(ingest_output)
    doc_id = ingest_json["data"]["doc_id"]

    print("\n== 2) outline 查看文档元信息 ==")
    outline_output = toolkit.run_skill_entry("read", f"outline --doc-id {doc_id} --max-chunks 3")
    print(outline_output)

    print("\n== 3) find 检索相关 chunks ==")
    find_output = toolkit.run_skill_entry(
        "read",
        f'find --doc-id {doc_id} --query "learn agent plan execute react skill runtime" --top-k 2',
    )
    print(find_output)
    find_json = parse_entry_json(find_output)
    results = find_json["data"]["results"]

    chunk_ids = ",".join(str(item["id"]) for item in results)
    print("\n== 4) read 按 chunk ids 读取正文片段 ==")
    read_output = toolkit.run_skill_entry("read", f"read --doc-id {doc_id} --chunk-ids {chunk_ids}")
    print(read_output)


if __name__ == "__main__":
    main()
