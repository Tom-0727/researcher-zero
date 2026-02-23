from core.services.learn.state import PlanItem, SubtaskSummary


def get_learn_system_prompt(
    *,
    workspace: str,
    task: str,
    basic_info: str,
    taxonomy: str,
    human_preference: str,
    network: str,
    main_challenge: str,
) -> str:
    return f"""You are Learn Agent for continuous domain-specific knowledge accumulation.

Primary objective:
Learn from study materials (papers, docs, tools, etc.) and persist the accumulated knowledge by writing or updating files under the workspace. Your main job is to read/analyze sources and write refined knowledge into the workspace file paths below.

Now the task is:
{task}

The workspace path (you must use this for all file reads and writes) is:
{workspace}

Directory structure under the workspace:
{workspace}
├── Basic_Context
│   ├── basic_info.md       # Basic definition: what this domain is
│   └── taxonomy.md         # Taxonomy network: hierarchical tree of Category + Concept
├── Cognition
│   ├── main_challenge.md   # Core challenges: unresolved problems in the current domain
│   └── network.md          # Relationship network: mapping concept connections and evolution
├── Atomic_Knowledge       # Directory for specific notes (algorithms, papers)
└── Alignment
    └── human_preference.md # Human preferences and negative constraints

The following blocks are the current contents of the corresponding files. Each block maps to exactly one file; when you update that knowledge, you must write to the same file.
- <Basic_Info>  →  {workspace}/Basic_Context/basic_info.md
- <Taxonomy>    →  {workspace}/Basic_Context/taxonomy.md
- <Alignment_Human_Preference>  →  {workspace}/Alignment/human_preference.md
- <Cognition_Network>  →  {workspace}/Cognition/network.md
- <Main_Challenge>     →  {workspace}/Cognition/main_challenge.md

Current file contents:

<Basic_Info>
{basic_info}
</Basic_Info>

<Taxonomy>
{taxonomy}
</Taxonomy>

<Alignment_Human_Preference>
{human_preference}
</Alignment_Human_Preference>

<Cognition_Network>
{network}
</Cognition_Network>

<Main_Challenge>
{main_challenge}
</Main_Challenge>
"""


def get_plan_instruction(*, task: str, max_plan_steps: int) -> str:
    """Instruction for plan_task human message."""
    return f"""Please decompose the learning task into at most {max_plan_steps} subtasks.

Task:
{task}

Rules:
1. First think of subtask titles only.
2. Then call `plan_upsert_todos` exactly once with JSON array:
   [{{"status":"todo","title":"..."}}]
3. Never include `id` in upsert payload.
"""


def render_plan_view(plan_items: list[PlanItem]) -> str:
    """Render plan items into compact text for follow-up prompts."""
    if not plan_items:
        return "<PLAN>\n</PLAN>"
    lines = [f"- [{item.status}][{item.id}] {item.title}" for item in plan_items]
    return "<PLAN>\n" + "\n".join(lines) + "\n</PLAN>"


def get_react_think_prompt(
    *,
    current_subtask_id: int,
    current_subtask: str,
    react_turn: int,
    max_react_turns: int,
) -> str:
    """Instruction text for one ReAct think turn."""
    return f"""Current subtask:
- id: {current_subtask_id}
- title: {current_subtask}
- turn: {react_turn}/{max_react_turns}

Rules:
1. Focus only on this subtask and ignore unrelated goals.
2. Choose exactly one next action: call one tool, or finish this subtask.
3. If the subtask is completed, finish immediately instead of over-calling tools.
4. Follow the skills usage instructions from the previous message when calling tools.
"""


def get_subtask_summary_prompt(*, current_subtask_id: int, current_subtask: str) -> str:
    """Instruction text for compressing one subtask trace."""
    return f"""Please summarize this finished subtask in concise Chinese.

Subtask:
- id: {current_subtask_id}
- title: {current_subtask}

Output format:
1. `结论`：1-3 句。
2. `证据`：最多 3 条要点（来源或工具结果）。
3. `沉淀`：写入/更新了哪些 workspace 文件；若没有写入，明确写“无”。
"""


def render_subtask_summaries(summaries: list[SubtaskSummary]) -> str:
    """Render subtask summaries for final aggregation prompt."""
    if not summaries:
        return "(none)"
    lines = [f"[{item.subtask_id}] {item.summary}" for item in summaries]
    return "\n".join(lines)


def get_final_summary_prompt(*, task: str, plan_view: str, summaries_view: str) -> str:
    """Instruction text for final learn report."""
    return f"""Please produce the final learn report in concise Chinese.

Original task:
{task}

Final plan snapshot:
{plan_view}

Subtask summaries:
{summaries_view}

Output sections:
1. `本次完成`：本轮学习实际完成内容。
2. `关键产出`：沉淀到 workspace 的可复用知识与文件。
3. `未完成与风险`：未完成项、阻塞点、已知不确定性。
"""
