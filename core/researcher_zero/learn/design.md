# Learn Agent 设计（LangGraph，含当前实现对照）

本文档不仅描述目标设计，也同步说明当前代码实现（截至本次提交）的落地点，避免“设计与代码脱节”。

## 1. 目标与边界
- 输入固定：`workspace`、`task`。
- 主流程固定：`Plan & Execute + ReAct`。
- 技能能力统一通过 `core/skills` 与 `core/tools/skill_meta_toolkit` 使用，不在 learn 内硬编码业务逻辑。
- Plan 结构编辑使用 `core/skills/plan` 暴露的 LangChain tools，不让 LLM 在 Plan 阶段自行 `load_skill` 决策。
- Plan 必须注入四个上下文文件：
  - `Basic_Context/basic_info.md`
  - `Basic_Context/taxonomy.md`
  - `Cognition/network.md`
  - `Cognition/main_challenge.md`
- ReAct 子任务结束后必须压缩总结，只向后续子任务暴露压缩历史，不暴露完整中间轨迹。
- 所有子任务完成后输出最终总结（完成项、产出、未完成与风险）。
- 不做 fallback：缺文件、工具异常、返回格式不符合约束时直接报错。

## 2. 当前实现文件地图
已实现目录（`core/researcher_zero/learn/`）：

```text
__init__.py
configuration.py      # LearnConfig + from_runnable_config
state.py              # LearnState / PlanItem / SubtaskSummary
prompts.py            # 纯文本模板
context_loader.py     # workspace 读取与 plan 阶段 prompt 载荷构建
plan.py               # plan 生成、plan 文件解析、状态流转 helper
react.py              # ReAct 子图（think/act/stop）+ read 顺序校验
summarize.py          # 子任务总结与最终总结
graph.py              # 主图编排（Plan & Execute 主循环）
design.md
```

相关技能实现：
- `core/skills/plan/service.py`：`build_plan_tools`、`plan_upsert_todos`、`plan_remove_ids`
- `core/skills/plan/scripts/plan_tool.py`：`mutate_plan_file`（底层 `<PLAN>` 文件操作）

## 3. 状态模型（`state.py`）
`LearnState` 基于 `MessagesState`，当前实现字段：

- 基础输入：`workspace`、`task`
- Plan 上下文：`plan_file`、`system_prompt`、`workspace_notes_summary`
- Skill 元信息：`skill_runtime_prompt`、`available_skills`
- 计划快照：`plan_items`
- 当前子任务：`current_index`、`current_subtask_id`、`current_subtask`
- ReAct 过程：`react_messages`、`react_turn`、`stop_reason`
- 子任务间压缩记忆：`condensed_messages`、`subtask_summaries`
- Read 顺序状态：`read_doc_stage`（`doc_id -> ingested/located/read`）
- 终态：`final_summary`、`done`

补充：
- `PlanItem.status` 受限于 `todo|doing|done|aborted`。
- `react_messages` 和 `condensed_messages` 使用普通 list（不是 `operator.add` 聚合），保证可以在子任务结束时真正清空 `react_messages`。

## 4. 上下文与 Prompt 构建

### 4.1 `context_loader.py`
- `resolve_workspace`：严格校验 `workspace` 目录存在。
- `resolve_plan_file`：默认 `<workspace>/plan.md`。
- `load_required_context`：强制读取四个必需文件，缺失即报错。
- `summarize_workspace_notes`：
  - 扫描 `workspace` 下 `.md`（排除四个必需文件与 `.read_cache`）
  - 每篇截断，拼成知识基线摘要。
- `build_plan_context_payload`：输出 `workspace`、`plan_file`、`system_prompt`、`workspace_notes_summary`。

### 4.2 `prompts.py`
只提供字符串模板，不拼 `List[Message]`：

- `get_plan_system_prompt`
- `get_plan_instruction`
- `render_plan_view`
- `get_react_think_prompt`
- `get_subtask_summary_prompt`
- `render_subtask_summaries`
- `get_final_summary_prompt`

其中 `get_react_think_prompt` 已内置 read 约束提示：
- 仅允许 `run_skill_entry("read", args)`；
- 顺序必须 `ingest -> outline/find -> read(--chunk-ids)`；
- 禁止整文注入上下文。

## 5. Plan 阶段实现（`plan.py` + `core/skills/plan/service.py`）

### 5.1 Plan 工具绑定策略
- `plan.py` 直接使用 `core.skills.plan.build_plan_tools(plan_file=...)`。
- Plan 阶段仅绑定 plan 专用工具，不向 LLM 暴露 `load_skill`。

### 5.2 `run_plan_task`
核心流程：
1. `init_chat_model(...).bind_tools(plan_tools, tool_choice="required")`
2. 输入消息：
   - `SystemMessage(system_prompt)`
   - `HumanMessage(get_plan_instruction(...))`
3. 必须返回 tool calls；逐个执行 `_invoke_tool`。
4. 最终快照从 `plan_file` 重新加载（`load_plan_items_from_file`），确保 `plan_file` 为单一事实源。
5. 校验 `max_plan_steps`。

### 5.3 计划解析与格式约束
- `parse_plan_items` 强制 `<PLAN>...</PLAN>` 包裹。
- 每行格式必须是 `- [status][id] title`。
- `id` 必须严格连续 `1..N`。
- 空标题直接报错。

### 5.4 开发者受控状态流转（不暴露给 LLM）
- `STATUS_TRANSITIONS`：
  - `todo -> doing`
  - `doing -> done|aborted`
- `transition_plan_item_status`：
  - 先读取当前快照并校验迁移合法性；
  - 内部调用 `mutate_plan_file(op="upsert", id=...)` 回写状态；
  - 回读校验状态写入成功。
- `start_next_subtask`：选择第一个 `todo` 并置为 `doing`。

说明：`mutate_plan_file` 属于开发者运行时受控能力，Agent 在 ReAct 中不直接拥有“自由改状态”权限。

## 6. ReAct 子图实现（`react.py`）

### 6.1 子图结构
- 节点：`react_think -> react_act -> react_should_stop`
- 编译对象：`react_subgraph`

### 6.2 `react_think`
- 工具集：`skill_meta_toolkit` 全量工具 + `FinishSubtask`。
- `tool_choice="required"`，每轮必须产生一个动作。
- 强约束：`_pick_single_tool_call` 要求每轮恰好一个 tool call。
- 输入消息顺序：
  1. `SystemMessage(system_prompt)`
  2. `HumanMessage(Current plan)`
  3. `HumanMessage(Previous subtask summaries)`
  4. `HumanMessage(Current subtask instruction)`
  5. 追加本子任务历史 `react_messages`（如有）

### 6.3 `react_act`
- 若动作为 `FinishSubtask`，直接写 `stop_reason` 并进入 stop 判断。
- 否则在 `tool_map` 中执行对应工具，写回 `ToolMessage`。
- 对 `run_skill_entry`：
  - `_raise_on_failed_run_skill_entry` 要求返回首行匹配 `exit_code: ...`
  - 非 0 直接抛错
  - 非预期格式也抛错（不做兜底）

### 6.4 read 能力执行层强约束
针对 `run_skill_entry("read", args)`，当前代码做了前置与后置双校验：

前置（执行前）：
- `_parse_read_entry_args`：
  - 必须包含 `--workspace`
  - 必须包含操作 `ingest|outline|find|read`
  - `ingest` 必须有 `--source`
  - `outline/find/read` 必须有 `--doc-id`
  - `find` 必须有 `--query`
  - `read` 必须有 `--chunk-ids` 且 id 格式合法
- `_validate_read_sequence`：
  - `outline/find/read` 前必须已有该 `doc_id` 的 ingest 记录
  - `read` 前必须至少经过 `outline` 或 `find`（stage=`located` 或 `read`）

后置（执行成功后）：
- `_apply_read_stage_update` 更新 `read_doc_stage`
  - ingest：从 read skill JSON 输出中解析 `data.doc_id`，标记 `ingested`
  - outline/find：标记 `located`
  - read：标记 `read`

### 6.5 `react_should_stop`
- 有 `stop_reason` 则结束子图。
- 否则达到 `max_react_turns_per_subtask` 时结束，并写 `stop_reason="max_react_turns"`。
- 否则回到 `react_think`。

## 7. 总结模块（`summarize.py`）

### 7.1 `run_subtask_summary`
- 输入前校验：`current_subtask_id > 0` 且 `current_subtask` 非空。
- 将 `react_messages` 渲染为 trace 文本（包含 tool_call 参数）。
- 用 `summary_model` 生成压缩总结。
- 更新：
  - 追加 `SubtaskSummary` 到 `subtask_summaries`
  - 追加一条 `HumanMessage` 到 `condensed_messages`
  - 清空 `react_messages`
  - 重置 `react_turn`、`stop_reason`、`current_subtask*`
  - 清空 `read_doc_stage`

### 7.2 `run_finalize_summary`
- 组合 `task + final plan + subtask summaries` 生成 `final_summary`。
- 写 `done=True`。

## 8. 主图编排（`graph.py`）
节点：
1. `validate_input`
2. `build_plan_context`
3. `plan_task`
4. `select_next_subtask`
5. `run_react_subgraph`
6. `summarize_subtask`
7. `finalize_summary`

路由：
- `START -> validate_input -> build_plan_context -> plan_task -> select_next_subtask`
- `select_next_subtask -> run_react_subgraph | finalize_summary`
- `run_react_subgraph -> summarize_subtask -> select_next_subtask`
- `finalize_summary -> END`

关键实现点：
- `build_plan_context` 初始化本轮运行态，避免脏状态污染。
- `select_next_subtask` 每轮先从 `plan_file` 刷新快照；若存在残留 `doing` 直接报错。
- `summarize_subtask` 根据 `stop_reason` 决定 `done` 或 `aborted` 并回写 plan 文件。
- `finalize_summary` 前强制校验 plan 中无 `todo/doing`。

## 9. 配置项（`configuration.py`）
当前支持：
- `plan_model`
- `react_think_model`
- `summary_model`
- `max_plan_steps`
- `max_react_turns_per_subtask`
- `skill_roots`
- `skill_allow_run_entry`
- `skill_command_timeout`
- `skill_allowed_entry_programs`

`from_runnable_config` 会同时读取：
- `configurable` 参数
- 对应环境变量（大写）

并做类型转换（bool、csv/list）。

## 10. 运行产出（状态终值）
主图结束后，至少可从状态拿到：
- `final_summary`
- `plan_items`（最终状态）
- `subtask_summaries`
- `workspace`、`task`

此外还保留 `messages`（模型/工具过程消息）用于调试与可观测性。

## 11. 已完成验证（本地）
已执行并通过：

1. 语法编译  
`python -m py_compile core/researcher_zero/learn/*.py core/skills/plan/service.py`

2. 无模型 smoke（不使用 mock）  
- `select_next_subtask`：可把 `todo -> doing`，无 `todo` 时转 `finalize_summary`。  
- `transition_plan_item_status`：合法迁移通过，非法迁移报错。  
- read 顺序校验：  
  - `outline/read` 在 ingest 前报错；  
  - `read` 在 outline/find 前报错；  
  - 合法顺序通过。

## 12. 当前限制与后续可演进点
- 未在本地执行真实 LLM 端到端（依赖外部模型配置和密钥）。
- `run_skill_entry` 输出格式与 `skill_meta_toolkit` 当前实现耦合（假设首行为 `exit_code: ...`）。
- `read` 的约束目前在 `react_act` 执行层强校验；若后续需要更强控制，可在 `skill_meta_toolkit` 增加策略层统一约束。
