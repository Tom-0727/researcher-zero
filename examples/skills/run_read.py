import json
import shlex
from pathlib import Path
from tempfile import TemporaryDirectory

from core.tools.skill_meta_toolkit import SkillToolkit

TARGET_URL = "https://arxiv.org/html/1706.03762v7"


def build_read_args(workspace: Path, op: str, extra: list[str]) -> str:
    """组装 run_skill_entry("read", entry_args) 的参数字符串。"""
    parts = ["--workspace", str(workspace), op, *extra]
    return " ".join(shlex.quote(item) for item in parts)


def run_read_entry(toolkit: SkillToolkit, workspace: Path, op: str, extra: list[str]) -> str:
    """执行 read skill 的一次 entry 调用。"""
    entry_args = build_read_args(workspace=workspace, op=op, extra=extra)
    return toolkit.run_skill_entry("read", entry_args)


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

    with TemporaryDirectory(prefix="read-skill-") as tmp_dir:
        workspace = Path(tmp_dir)
        print("== 1) ingest 网页 ==")
        ingest_output = run_read_entry(
            toolkit=toolkit,
            workspace=workspace,
            op="ingest",
            extra=[
                "--source",
                TARGET_URL,
                "--title",
                "Researcher Zero Learn Agent 设计",
                "--chunk-size",
                "1200",
                "--chunk-overlap",
                "150",
            ],
        )
        print(ingest_output)
        ingest_json = parse_entry_json(ingest_output)
        doc_id = ingest_json["data"]["doc_id"]

        print("\n== 2) outline 查看文档元信息 ==")
        outline_output = run_read_entry(
            toolkit=toolkit,
            workspace=workspace,
            op="outline",
            extra=["--doc-id", doc_id, "--max-chunks", "3"],
        )
        print(outline_output)

        print("\n== 3) find 检索相关 chunks ==")
        find_output = run_read_entry(
            toolkit=toolkit,
            workspace=workspace,
            op="find",
            extra=[
                "--doc-id",
                doc_id,
                "--query",
                "learn agent plan execute react skill runtime",
                "--top-k",
                "2",
            ],
        )
        print(find_output)
        find_json = parse_entry_json(find_output)
        results = find_json["data"]["results"]
        if not results:
            raise RuntimeError("find 未命中任何 chunk，无法继续 read 测试。")

        # 用 find 返回的 chunk id 做精准读取。
        chunk_ids = ",".join(str(item["id"]) for item in results)
        print("\n== 4) read 按 chunk ids 读取正文片段 ==")
        read_output = run_read_entry(
            toolkit=toolkit,
            workspace=workspace,
            op="read",
            extra=["--doc-id", doc_id, "--chunk-ids", chunk_ids],
        )
        print(read_output)


if __name__ == "__main__":
    main()
