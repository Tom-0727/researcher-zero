# Learn Agent 设计（LangGraph）

## 1. 目标与边界
- 输入参数固定为 `workspace` 和 `task`。
- 行为主线固定为 `Plan & Execute + ReAct`。
- `plan/search/file_manage` 等能力统一走 `core/skills`，不在 learn 内硬编码业务实现。
- Plan 结构编辑必须通过 `run_skill_entry("plan", args)` 调用 plan skill；Agent 侧仅允许“新增步骤/删除步骤”。
- Plan 阶段必须读取并注入以下上下文：
  - 基本语境：`Basic_Context/basic_info.md` + `Basic_Context/taxonomy.md`
  - 认知构造：`Cognition/network.md` + `Cognition/main_challenge.md`
- Plan 阶段必须初始化 skills 元信息（基于 `core/tools/skill_meta_toolkit`），并将 skills runtime prompt 注入 `system_prompt`。
- Plan 目标是任务拆解（Task Decomposition），不是动作脚本编排（例如“先搜什么再总结什么”）。
- 每个子任务执行采用 ReAct 循环：`think -> act` 多轮迭代。
- 每个子任务结束后强制总结一次，只保留总结给后续子任务，中间 assistant/tool 细节不再继续暴露。
- 所有子任务完成后输出总体总结（本次学习做了什么、产出了什么、未完成什么）。

### 1.1 Learn 任务本质（补充）
- learn 不是“一次性回答问题”，而是“在指定 `workspace` 内持续积累知识”的过程。
- `workspace` 是 agent 的外部化上下文（externalized context）：随着学习推进，内容会被不断补充，后续轮次再消费这些新增内容。
- learn 的核心动作通常包括：`搜索资料 -> 阅读资料/论文 -> 写入 workspace 笔记`，用于持续丰富 workspace 内容。
- 子任务完成标准不仅是“给出结论”，还包括“将可复用知识沉淀为文件内容”，让 workspace 变得更丰富、更可复用。
- 参考来源（任务语义定义）：  
  - `https://www.tom-blogs.top/2026/02/13/researcher-zero/arch-design-learning/`  
  - `https://www.tom-blogs.top/2026/02/01/researcher-zero/arch-design-context/`

## 2. 参考模式（对齐 `core/agents/paper_searcher`）
- 使用 `StateGraph + Command(goto=..., update=...)` 的节点驱动模式。
- `think` 节点仅负责“下一步决策/工具选择”。
- `act` 节点仅负责“执行工具调用并写回状态”。
- 将配置、状态、提示词、主图构建分文件管理（与 `paper_searcher` 相同分层思路）。

## 3. 建议目录结构（learn）
```text
core/researcher_zero/learn/
  __init__.py
  configuration.py      # LearnConfig: 模型、循环上限、计划上限等
  state.py              # LearnState / PlanItem / SubtaskSummary
  prompts.py            # 仅维护文本模板（不维护 List[Message] 拼装）
  context_loader.py     # 上下文加载（workspace 四个文件读取 + skills capability 初始化 + List[Message] 拼装）
  skill_runtime.py      # build_skill_capability 封装与工具注册
  plan.py            # 计划生成与计划改写（通过 skill tools 调用 plan skill）
  react.py            # ReAct 子图（think/act/stop）
  summarize.py         # 子任务总结 + 全局总结
  graph.py              # 主图拼装（含子图调用）
  design.md
```

## 4. 状态模型（LangGraph State）
建议 `LearnState` 基于 `MessagesState` 扩展，字段最小化如下：

- `workspace: str`
- `task: str`
- `plan_file: str`（绝对路径，默认 `<workspace>/plan.md`）
- `system_prompt: str`（在 plan 前一次性构建）
- `skill_runtime_prompt: str`（`build_skill_capability(...).prompt`）
- `available_skills: list[str]`（用于可观测性与调试）
- `plan_items: list[PlanItem]`（由 plan skill 返回的 `<PLAN>...</PLAN>` 文本解析得到）
- `current_index: int`
- `current_subtask: str`
- `subtask_summaries: list[SubtaskSummary]`
- `react_messages: list[MessageLikeRepresentation]`
- `condensed_messages: list[MessageLikeRepresentation]`
- `final_summary: str`
- `done: bool`

辅助模型：
- `PlanItem`：`id`、`title`、`status(todo|doing|done|aborted)`
- `SubtaskSummary`：`subtask_id`、`summary`

约束：
- 不做 fallback：缺文件、工具返回异常时直接显式报错。
- 计划文件必须是 `<PLAN>...</PLAN>` 包裹，行格式固定为 `- [status][id] title`。
- `id` 必须连续 `1..N`；解析到不连续 id 直接报错。
- `plan_file` 是计划结构的单一事实源；`state.plan_items` 是其内存快照，每次结构写入后必须重新解析回填。
- Agent 通过 plan skill 只能追加 todo 步骤（`upsert` 且不带 `id`）或删除步骤（`remove`）。
- 状态流转（`todo -> doing -> done/aborted`）由开发者代码控制，不由 Agent 通过 skill 改状态。
- `SkillCapability` 与工具对象不放入 state（不可序列化对象），由 graph/runtime 注入节点执行上下文。

## 5. 上下文构建策略

### 5.1 Plan 阶段上下文（一次性）
- 从 `workspace` 读取四个 markdown 原文。
- 扫描并读取 `workspace` 中已有学习笔记（可按索引或约定目录），用于评估当前知识基线与缺口。
- 初始化 skills 能力（`build_skill_capability(roots=["core/skills"], allow_run_entry=True, ...)`）。
- 组装 `system_prompt`（持久保存到 state）：
  - 任务目标（task）
  - 领域基本语境（basic_info + taxonomy）
  - 认知构造（network + main_challenge）
  - 当前 workspace 已沉淀知识摘要（避免重复学习，优先补缺）
  - skills runtime 说明与可用技能清单（来自 `skill_runtime_prompt`）
  - 执行规则（先做任务拆解、按子任务循环 react、每子任务结束必须总结并写回 workspace）
- `plan_task` 节点消息构造与绑定：
  1. `SystemMessage(system_prompt)`（含基本语境 + 认知构造 + learn 任务指示 + skills 元信息）
  2. `HumanMessage(plan_instruction)`（仅描述“做任务拆解，不做动作编排”）
  3. 绑定工具：`load_skill` + `run_skill_entry`（其中 `run_skill_entry` 只允许触发 `plan` skill）

Plan 输出约束：
- `plan_task` 必须产出“独立、更小、可执行”的学习子任务列表。
- `plan_task` 不输出工具动作序列，不输出“先搜什么、再总结什么”的操作脚本。
- `plan_task` 执行落盘时流程固定：
  1. 先让模型产出子任务标题列表（不含 `id/status`）；
  2. 转换为 `items-json`：`[{"status":"todo","title":"..."}]`；
  3. 调用 `run_skill_entry("plan", "--plan /abs/path/plan.md --op upsert --items-json '<JSON_ARRAY>'")`；
  4. 解析返回的 `<PLAN>...</PLAN>` 为 `plan_items`，并与 `plan_file` 保持一致。
- 示例（输入：研究 agent memory 的设计）：
  - 分析 memory 的核心维度
  - 调研代表性工作与系统
  - 抽象 memory 设计的关键 trade-offs
  - 总结可迁移的设计原则与边界条件

### 5.2 子任务阶段上下文（压缩可见）
- 每轮调用 LLM 时由节点动态构造 `List[Message]`，而不是在 `prompts.py` 中维护消息历史。
- `react_think` 的输入消息顺序固定为：
  1. `SystemMessage(system_prompt)`（含 skills 说明与 skill meta tool 使用约束）
  2. `HumanMessage(plan)`：当前计划视图（至少含当前子任务与 plan 状态）
  3. `HumanMessage(history)`：`condensed_messages` 的压缩历史（仅前序 subtask 总结）
  4. `HumanMessage(current_subtask)`：当前子任务与本轮所需指令
- `react_think` 绑定工具：`skill_meta_toolkit` 全量工具 + `finish/stop` 决策动作（无工具调用）。
- `react_messages` 只在当前子任务内部循环使用。
- 子任务结束后：
  - 触发总结节点，生成 1 条压缩总结 message
  - 将该总结 append 到 `condensed_messages`
  - 清空 `react_messages`

### 5.3 消息拼装职责（强约束）
- `prompts.py` 只输出文本模板（string），不接收也不返回 `List[Message]`。
- `plan.py / react.py / summarize.py` 在节点内根据 state 拼装消息：
  - `plan.py`：`SystemMessage(plan_system_prompt) + HumanMessage(task)`
  - `react.py`：`SystemMessage(system_prompt) + HumanMessage(plan) + HumanMessage(history) + HumanMessage(current_subtask)`
  - `summarize.py`：`SystemMessage(system_prompt) + HumanMessage(summary_instruction + react_trace)`
- `react_messages` 是当前子任务内部临时轨迹；`condensed_messages` 是跨子任务可见历史。

### 5.4 Skill 渐进式加载（强约束）
- `system_prompt` 只暴露 skill 元信息，不预加载全部 `SKILL.md` 正文。
- 当 Agent 判断需要某个 skill（如 `plan/search/file_manage`）时，先调用 `load_skill(skill_name)` 加载完整技能说明。
- 若技能说明引用了目录文件或示例，再调用 `find_skill_files / read_skill_file / load_skill_examples` 按需补充。
- 需要执行技能入口时，只能通过 `run_skill_entry(skill_name, args)` 触发 `entry` 脚本。

## 6. 图结构设计（主图 + 子图）

### 6.1 主图（Plan & Execute）
节点建议：
1. `validate_input`：校验 `workspace/task`
2. `build_plan_context`：加载四类上下文 + 初始化 skills capability
3. `plan_task`：将输入 task 拆解为初始步骤，并通过 plan skill 写入 `plan_file` 后回填 `plan_items`
4. `select_next_subtask`：选择待执行子任务，并根据情况改变plan的状态，若无则转最终总结
5. `run_react_subgraph`：执行当前子任务 ReAct 子图
6. `summarize_subtask`：压缩当前 ReAct 对话为总结 message
7. `finalize_summary`：生成全局总结并结束

主路由：
- `START -> validate_input -> build_plan_context -> plan_task -> select_next_subtask`
- `select_next_subtask -> run_react_subgraph` 或 `finalize_summary`
- `run_react_subgraph -> summarize_subtask -> select_next_subtask`
- `finalize_summary -> END`

### 6.2 ReAct 子图（每个子任务）
节点建议：
1. `react_think`：基于当前可见上下文决定下一步动作（工具调用/完成）
2. `react_act`：执行动作并写入 `react_messages`
3. `react_should_stop`：判断是否完成该子任务

子图路由：
- `START -> react_think -> react_act -> react_should_stop`
- `react_should_stop == false` 回到 `react_think`
- `react_should_stop == true` 到 `END`
- `react_should_stop` 触发条件：
  - LLM 明确给出 `finish/stop`；
  - 或达到 `max_react_turns_per_subtask`。

### 6.3 端到端时序（与运行逻辑一一对应）
1. 输入 `workspace` 与 `task` 后先走 `validate_input`，失败即报错退出。
2. 进入 `build_plan_context`，构建一次性 `system_prompt`（基本语境 + 认知构造 + learn 任务指示 + skills 元信息）。
3. 进入 `plan_task`：
  - 使用 `SystemMessage(system_prompt) + HumanMessage(plan_instruction)`；
  - 绑定 plan 相关工具（通过 skill meta tool 间接调用 `run_skill_entry("plan", ...)`）；
  - 产出并落盘 `plan_file`，并同步回填 `state.plan_items`。
4. 进入主循环 `while 有待执行 subtask`：
  - 先以 `plan_file` 为准刷新/校验 `plan_items` 快照；
  - `select_next_subtask` 选择下一条并将状态置为 `doing`；
  - 进入 ReAct 子循环 `while 未 stop 且未超上限`：
    - `react_think` 基于（system + plan + 前序总结 + 当前子任务）决策；
    - `react_act` 执行工具调用并写回 `react_messages`；
  - 退出子循环后进入 `summarize_subtask`，写入该 subtask 总结到 `condensed_messages`；
  - 根据执行结果将该 subtask 置为 `done` 或 `aborted`。
5. 所有 subtask 结束后执行 `finalize_summary`，输出全局总结（做了什么、产出什么、未完成什么）。

## 7. Prompt 与消息构造分层
- `get_plan_system_prompt(...)`：生成 Plan 阶段 SystemMessage 文本（含四类上下文与任务拆解约束）。
- `get_react_think_prompt(...)`：生成 ReAct think 的“当前子任务指令文本”。
- `get_subtask_summary_prompt(...)`：生成子任务总结指令文本（压缩当前 `react_messages`）。
- `get_final_summary_prompt(...)`：生成最终汇总指令文本（汇总 `subtask_summaries`）。

注意：
- `prompts.py` 只负责“文本内容模板”；不负责拼装 `List[Message]`。
- `plan.py / react.py / summarize.py` 在调用 LLM 前，按 state 动态构造 `List[Message]`。
- Plan 与 ReAct 使用同一个 `system_prompt` 基底，再按节点职责追加消息。
- 子任务间严格隔离细粒度过程，仅传递总结消息。

## 8. 工具调用抽象（Act 层）
- `react_think` 输出“动作决策”（工具名 + 参数 或 finish）。
- `react_act` 负责执行并产出 `ToolMessage`。
- tools 由 `core/tools/skill_meta_toolkit` 注册，至少包含：
  - `list_available_skills`
  - `load_skill`
  - `find_skill_files`
  - `read_skill_file`
  - `load_skill_examples`
  - `run_skill_entry`（`allow_run_entry=True` 时启用）
- act 节点只做调度与状态更新，不做技能逻辑内嵌。
- 任何工具异常直接抛出，不做静默兜底。

## 8.1 Skill 驱动执行策略（强约束）
- `plan.py / react.py` 不直接 import `core/skills/*/scripts/*.py`。
- 所有技能能力（含 plan/search/file_manage）统一按以下流程执行：
  1. 通过 `load_skill(skill_name)` 获取完整 `SKILL.md` 指令与入口约束；
  2. 需要补充细节时，再调用 `find_skill_files / read_skill_file / load_skill_examples`；
  3. 需要执行时调用 `run_skill_entry(skill_name, args)`，由 skill frontmatter 的 `entry` 真正落地。
- 计划结构改写（Agent 侧）示例：
  - 先 `load_skill("plan")`；
  - 再 `run_skill_entry("plan", "--plan /abs/path/plan.md --op upsert --items-json '<JSON_ARRAY>'")`（仅追加，item 必须是 `{"status":"todo","title":"..."}` 且不带 `id`）；
  - 或 `run_skill_entry("plan", "--plan /abs/path/plan.md --op remove --ids '2,4'")`（批量删）；
  - 用返回结果更新 state 中的计划视图。
- 计划状态流转（开发者代码）：
  - Agent 不通过 plan skill 修改状态。
  - 由 learn runtime 在 `select_next_subtask / summarize_subtask` 等节点维护 `todo -> doing -> done/aborted`。
  - 如需将状态回写到计划文件，可由开发者代码受控调用 `upsert + id`；该能力不暴露为 Agent 的自由动作。
- 若 skill 不存在、`entry` 缺失或命令执行失败，直接显式报错，不做 fallback。

## 9. 配置项建议（configuration.py）
- `plan_model`
- `react_think_model`
- `summary_model`
- `max_plan_steps`
- `max_react_turns_per_subtask`
- `skill_roots`（默认含 `core/skills`）
- `skill_allow_run_entry`（learn 场景默认 `True`）
- `skill_command_timeout`
- `skill_allowed_entry_programs`

配置读取方式沿用 `paper_searcher` 的 `from_runnable_config` 模式。

## 10. 执行产出定义
返回结构最少包含：
- `final_summary`
- `plan_items`（最终状态）
- `subtask_summaries`
- `workspace`、`task`

这样上层可以直接落库或继续驱动下游流程。

## 11. 最小可落地顺序
1. 先完成 `context_loader + skill_runtime + state + prompts + plan_task`（先打通 skills 元信息注入与计划生成）。
2. 再接入 `react` 子图（think/act/stop）。
3. 接入 `summarize_subtask` 实现上下文压缩。
4. 最后补 `finalize_summary`。

以上顺序可确保每一步都能独立验证，且始终符合 LangGraph 的节点化设计。
