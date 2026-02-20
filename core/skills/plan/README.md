# Plan Skill (Developer README)

## 1. 定位

- `SKILL.md` 是给 Agent 的指令，当前只开放“新增步骤 + 删除步骤”两种动作。
- 本 README 是给开发者的实现说明，描述 `plan_tool.py` 的完整能力与约束。

## 2. 文件与入口

- Skill file: `core/skills/plan/SKILL.md`
- Entry script: `core/skills/plan/scripts/plan_tool.py`
- Entry command: `python scripts/plan_tool.py`

通过 meta toolkit 调用时使用：

```text
run_skill_entry("plan", entry_args)
```

## 3. 数据格式

计划文件必须包含 `<PLAN>...</PLAN>`，行格式为：

```text
- [status][id] title
```

- `status`: `todo | doing | done | aborted`
- `id`: 动态序号，始终是 `1..N`
- 每次写入后会自动重排 id

## 4. CLI 协议（完整）

### 4.1 upsert（增/改）

```text
--plan /abs/path/plan.md --op upsert --items-json "<JSON_ARRAY>"
```

`items-json` 每个元素字段：
- `status` (required)
- `title` (required)
- `id` (optional)

语义：
- 无 `id` -> 追加新行
- 有 `id` -> 覆盖该 id 对应行（等价于“修改”）

### 4.2 remove（删）

```text
--plan /abs/path/plan.md --op remove --ids "1,3,5"
```

语义：
- 删除多个 id（同一调用可批量）
- 删除后自动重排 id

## 5. 关键约束

- 若计划文件不存在，会从空计划初始化。
- `id` 越界、重复 id、非法状态、空标题都会直接报错（不做 fallback）。
- 解析阶段要求已有计划中的 id 连续，否则报错。

## 6. Agent 与开发者分工

- Agent（依据 `SKILL.md`）：
  - 只做结构变更：新增步骤、删除步骤
  - 不负责状态流转
- 开发者代码：
  - 负责状态机策略，例如 `todo -> doing -> done/aborted`
  - 可在受控逻辑下使用 `upsert + id` 更新状态

## 7. 示例

初始化多个步骤：

```text
--plan /abs/path/plan.md --op upsert --items-json "[{\"status\":\"todo\",\"title\":\"步骤A\"},{\"status\":\"todo\",\"title\":\"步骤B\"}]"
```

按 id 更新状态（开发者代码使用）：

```text
--plan /abs/path/plan.md --op upsert --items-json "[{\"id\":1,\"status\":\"doing\",\"title\":\"步骤A\"}]"
```

批量删除：

```text
--plan /abs/path/plan.md --op remove --ids "2,4"
```
