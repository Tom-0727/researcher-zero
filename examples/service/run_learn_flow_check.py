import asyncio
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from core.researcher_zero import init_research_workspace, learn_graph
from core.researcher_zero.learn.plan import load_plan_items_from_file


# 直接在此处修改测试配置，不再读取命令行参数。
TASK = "调研包括 ReAct 模式在内的 Agent 运作设计，沉淀知识"
WORKSPACE = "/Users/tom/Codes/researcher-zero/cache/agent"  # 为空时自动创建 workspace
KEEP_WORKSPACE = False  # WORKSPACE 为空时，是否保留到 ./cache
PLAN_MODEL = "deepseek"
REACT_MODEL = "deepseek"
SUMMARY_MODEL = "deepseek"
MAX_PLAN_STEPS = 3
MAX_REACT_TURNS = 5


def _read_attr(item: Any, key: str) -> Any:
    """从 dict 或 pydantic 对象读取字段。"""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key)


def _normalize_plan_items(plan_items: list[Any]) -> list[dict[str, Any]]:
    """统一 plan item 结构，便于断言。"""
    normalized: list[dict[str, Any]] = []
    for item in plan_items:
        normalized.append(
            {
                "id": int(_read_attr(item, "id")),
                "status": str(_read_attr(item, "status")),
                "title": str(_read_attr(item, "title")),
            }
        )
    return normalized


def _normalize_subtask_summaries(subtask_summaries: list[Any]) -> list[dict[str, Any]]:
    """统一 subtask summary 结构，便于断言。"""
    normalized: list[dict[str, Any]] = []
    for item in subtask_summaries:
        normalized.append(
            {
                "subtask_id": int(_read_attr(item, "subtask_id")),
                "summary": str(_read_attr(item, "summary")).strip(),
            }
        )
    return normalized


def assert_learn_result(result: dict[str, Any]) -> dict[str, Any]:
    """检查 learn 全流程运行结果。"""
    final_summary = str(result.get("final_summary", "")).strip()
    if not final_summary:
        raise AssertionError("final_summary 为空。")
    if result.get("done") is not True:
        raise AssertionError("done 必须为 True。")

    plan_items_raw = result.get("plan_items", [])
    if not isinstance(plan_items_raw, list) or not plan_items_raw:
        raise AssertionError("plan_items 必须是非空列表。")
    plan_items = _normalize_plan_items(plan_items_raw)

    illegal_status = [item for item in plan_items if item["status"] in {"todo", "doing"}]
    if illegal_status:
        raise AssertionError(f"最终计划中不应存在 todo/doing: {illegal_status}")

    plan_file = str(result.get("plan_file", "")).strip()
    if not plan_file:
        raise AssertionError("result.plan_file 为空。")
    loaded_plan = load_plan_items_from_file(plan_file)
    if len(loaded_plan) != len(plan_items):
        raise AssertionError("plan_file 与 state.plan_items 长度不一致。")

    summaries_raw = result.get("subtask_summaries", [])
    if not isinstance(summaries_raw, list):
        raise AssertionError("subtask_summaries 必须是列表。")
    summaries = _normalize_subtask_summaries(summaries_raw)
    if len(summaries) != len(plan_items):
        raise AssertionError("subtask_summaries 数量必须与 plan_items 一致。")
    if any(not item["summary"] for item in summaries):
        raise AssertionError("subtask_summaries 中存在空 summary。")

    plan_ids = sorted(item["id"] for item in plan_items)
    summary_ids = sorted(item["subtask_id"] for item in summaries)
    if summary_ids != plan_ids:
        raise AssertionError(
            f"summary subtask_id 与 plan id 不一致: summary={summary_ids}, plan={plan_ids}"
        )

    return {
        "plan_count": len(plan_items),
        "summary_count": len(summaries),
        "plan_file": plan_file,
        "final_summary": final_summary,
    }


def prepare_workspace() -> tuple[Path, TemporaryDirectory | None]:
    """准备测试 workspace。"""
    if WORKSPACE.strip():
        workspace = Path(WORKSPACE).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        init_research_workspace(workspace)
        return workspace, None

    if KEEP_WORKSPACE:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        workspace = (Path("cache") / f"learn-flow-{stamp}").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        init_research_workspace(workspace)
        return workspace, None

    tmp = TemporaryDirectory(prefix="learn-flow-")
    workspace = Path(tmp.name).resolve()
    init_research_workspace(workspace)
    return workspace, tmp


def build_runnable_config() -> dict[str, dict[str, Any]]:
    """构建 graph configurable 参数。"""
    configurable: dict[str, Any] = {
        "max_plan_steps": MAX_PLAN_STEPS,
        "max_react_turns_per_subtask": MAX_REACT_TURNS,
        "skill_allow_run_entry": True,
    }
    if PLAN_MODEL.strip():
        configurable["plan_model"] = PLAN_MODEL.strip()
    if REACT_MODEL.strip():
        configurable["react_think_model"] = REACT_MODEL.strip()
    if SUMMARY_MODEL.strip():
        configurable["summary_model"] = SUMMARY_MODEL.strip()
    return {"configurable": configurable}


async def run_flow_check() -> None:
    """执行 learn graph，并做结果断言。"""
    workspace, tmp = prepare_workspace()
    try:
        print(f"[1/4] workspace: {workspace}")
        print("[2/4] invoking learn_graph ...")

        initial_state = {
            "workspace": str(workspace),
            "task": TASK.strip(),
            "messages": [],
        }
        result = await learn_graph.ainvoke(
            initial_state,
            config=build_runnable_config(),
        )

        print("[3/4] validating final state ...")
        report = assert_learn_result(result)

        print("[4/4] flow check passed")
        print(f"- plan_file: {report['plan_file']}")
        print(f"- plan_count: {report['plan_count']}")
        print(f"- summary_count: {report['summary_count']}")
        print("- final_summary (first 240 chars):")
        print(report["final_summary"][:240])
    finally:
        if tmp is not None:
            tmp.cleanup()


def main() -> None:
    """脚本入口。"""
    if not TASK.strip():
        raise ValueError("TASK 不能为空。")
    if MAX_PLAN_STEPS <= 0:
        raise ValueError("MAX_PLAN_STEPS 必须大于 0。")
    if MAX_REACT_TURNS <= 0:
        raise ValueError("MAX_REACT_TURNS 必须大于 0。")
    asyncio.run(run_flow_check())


if __name__ == "__main__":
    main()
