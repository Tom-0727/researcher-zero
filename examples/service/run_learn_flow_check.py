import asyncio
from pathlib import Path
from typing import Any

from core.services import learn_graph
from core.services.learn.graph import plan_node


# 直接在此处修改测试配置，不再读取命令行参数。
TASK = "调研包括 ReAct 模式在内的 Agent 运作设计"
WORKSPACE = "/Users/tom/Codes/researcher-zero/cache/agent"
PLAN_MODEL = "glm"
REACT_MODEL = "glm"
SUMMARY_MODEL = "glm"
MAX_PLAN_STEPS = 3
MAX_REACT_TURNS = 5


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
    workspace = Path(WORKSPACE).expanduser().resolve()

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


async def run_plan_node_check() -> None:
    """仅执行 learn graph 的 plan 节点，并输出计划结果摘要。"""
    workspace = Path(WORKSPACE).expanduser().resolve()

    print(f"[1/3] workspace: {workspace}")
    print("[2/3] invoking plan_node ...")

    command = await plan_node(
        state={
            "workspace": str(workspace),
            "task": TASK.strip(),
            "messages": [],
        },
        config=build_runnable_config(),
    )
    update = getattr(command, "update", {}) or {}
    plan_items = update.get("plan_items", []) or []

    print("[3/3] plan node result snapshot ...")
    print(f"- goto: {getattr(command, 'goto', '')}")
    print(f"- plan_file: {update.get('plan_file')}")
    print(f"- plan_count: {len(plan_items)}")
    breakpoint()


def main() -> None:
    """脚本入口。"""
    asyncio.run(run_flow_check())


if __name__ == "__main__":
    main()
