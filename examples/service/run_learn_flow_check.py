import asyncio
from pathlib import Path
from typing import Any

from core.services import learn_graph
from core.services.learn.configuration import LearnConfig
from core.services.learn.context_loader import build_learn_context_payload
from core.services.learn.graph import (
    plan_node,
    run_react_subgraph as graph_run_react_subgraph,
)
from core.services.learn.state import PlanItem
from core.tools.skill_meta_toolkit import build_skill_capability


# 直接在此处修改测试配置，不再读取命令行参数。
TASK = "调研 ReAct 这种 Agent 运作设计，形成阅读笔记存在 Atomic_Knowledge 目录下"
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


async def run_react_subgraph_check() -> None:
    """不经过 plan_node，直接构造最小状态测试 graph.py 的 react_subgraph 节点。"""
    workspace = Path(WORKSPACE).expanduser().resolve()
    config = build_runnable_config()
    task = TASK.strip()
    learn_config = LearnConfig.from_runnable_config(config)
    context_payload = build_learn_context_payload(workspace=str(workspace), task=task)
    capability = build_skill_capability(
        roots=learn_config.skill_roots,
        allow_run_entry=True,
        command_timeout=learn_config.skill_command_timeout,
    )

    react_state = {
        "workspace": str(workspace),
        "task": task,
        "messages": [],
        "system_prompt": context_payload["system_prompt"],
        "skill_runtime_prompt": capability.prompt,
        "plan_items": [PlanItem(id=1, title=task, status="doing")],
        "current_index": 0,
        "current_subtask_id": 1,
        "current_subtask": task,
        "react_messages": [],
        "react_turn": 0,
        "stop_reason": "",
        "condensed_messages": [],
    }

    print(f"[1/4] workspace: {workspace}")
    print("[2/4] building react-only state ...")
    print(f"- skills_count: {len(capability.toolkit.skills)}")

    print("[3/4] invoking graph.run_react_subgraph ...")
    react_command = await graph_run_react_subgraph(state=react_state, config=config)
    react_update = getattr(react_command, "update", {}) or {}
    react_messages = react_update.get("react_messages", []) or []

    print("[4/4] react subgraph result snapshot ...")
    print(f"- goto: {getattr(react_command, 'goto', '')}")
    print(f"- current_subtask_id: {react_state.get('current_subtask_id', 0)}")
    print(f"- current_subtask: {react_state.get('current_subtask', '')}")
    print(f"- react_turn: {react_update.get('react_turn', 0)}")
    print(f"- stop_reason: {react_update.get('stop_reason', '')}")
    print(f"- react_message_count: {len(react_messages)}")
    if react_messages:
        print(f"- last_message_type: {type(react_messages[-1]).__name__}")


def main() -> None:
    """脚本入口。"""
    asyncio.run(run_react_subgraph_check())


if __name__ == "__main__":
    main()
