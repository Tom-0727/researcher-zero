import asyncio
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from core.services import init_research_workspace, learn_graph


# 直接在此处修改测试配置，不再读取命令行参数。
TASK = "调研包括 ReAct 模式在内的 Agent 运作设计，沉淀知识"
WORKSPACE = "/Users/tom/Codes/researcher-zero/cache/agent"  # 为空时自动创建 workspace
KEEP_WORKSPACE = False  # WORKSPACE 为空时，是否保留到 ./cache
PLAN_MODEL = "deepseek"
REACT_MODEL = "deepseek"
SUMMARY_MODEL = "deepseek"
MAX_PLAN_STEPS = 3
MAX_REACT_TURNS = 5


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
        "skill_roots": ["core/skills"],
    }
    if PLAN_MODEL.strip():
        configurable["plan_model"] = PLAN_MODEL.strip()
    if REACT_MODEL.strip():
        configurable["react_think_model"] = REACT_MODEL.strip()
    if SUMMARY_MODEL.strip():
        configurable["summary_model"] = SUMMARY_MODEL.strip()
    return {"configurable": configurable}


async def run_flow_check() -> None:
    """执行 learn graph，并输出结果摘要。"""
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

        print("[3/4] result snapshot ...")
        print(f"- done: {result.get('done')}")
        print(f"- plan_file: {result.get('plan_file')}")
        print(f"- plan_count: {len(result.get('plan_items', []) or [])}")
        print(f"- summary_count: {len(result.get('subtask_summaries', []) or [])}")
        print("- final_summary (first 240 chars):")
        print(str(result.get("final_summary", ""))[:240])
        print("[4/4] flow check finished")
    finally:
        if tmp is not None:
            tmp.cleanup()


def main() -> None:
    """脚本入口。"""
    asyncio.run(run_flow_check())


if __name__ == "__main__":
    main()
