# skill_meta_toolkit

`skill_meta_toolkit` 是一个面向 LangChain/LangGraph 的文件型技能运行时。  
核心目标是 **progressive disclosure（渐进式加载）**：提示词只暴露技能元信息，完整技能内容和关联文件在工具调用时按需读取。

## 模块结构

- `toolkit.py`
  - 数据扫描与解析（`discover_skills`）
  - 运行时能力（`SkillToolkit`）
  - 文件读取、示例检索、可选入口命令执行
- `service.py`
  - 把 `SkillToolkit` 包装成 LangChain `@tool`
  - 提供 `build_skill_capability` 一次性构建能力对象
- `__init__.py`
  - 导出对外 API：
    - `SkillCapability`
    - `SkillToolkit`
    - `build_agent_tools`
    - `build_skill_capability`
    - `discover_skills`

## 数据模型

### `SkillRecord`

技能扫描后的标准结构：

- `name`: 技能名（来自 frontmatter `name`，否则目录名）
- `description`: 描述（来自 frontmatter `description`，否则从正文首个有效行推断）
- `path`: `SKILL.md` 路径
- `directory`: 技能目录（`SKILL.md` 所在目录）
- `content`: `SKILL.md` 正文（frontmatter 已剥离）
- `entry`: 可选入口命令（frontmatter `entry`）
- `examples`: `examples/*.md` 扫描得到的示例集合

### `SkillExample`

- `path`: 示例文件路径
- `title`: frontmatter `title`，缺省为文件名
- `tags`: frontmatter `tags` 解析结果
- `content`: 示例正文（frontmatter 已剥离）

## SKILL.md / 示例文件约定

前置元数据使用简化 frontmatter（`---` 包裹）：

- 支持 `key: value` 行
- 忽略空行、注释行（`#` 开头）和无 `:` 的行
- key 统一转小写

`SKILL.md` 当前识别字段：

- `name`
- `description`
- `entry`

`examples/*.md` 当前识别字段：

- `title`
- `tags`（支持 `a, b` 或 `[a, b]`）

## 发现与刷新流程

`discover_skills(roots)` 行为：

1. 遍历每个 root（`expanduser + resolve`）
2. 递归查找 `SKILL.md`
3. 解析 frontmatter + 正文
4. 组装 `SkillRecord`，并扫描 `examples` 目录下所有 `*.md`
5. 返回 `dict[name, SkillRecord]`

`SkillToolkit.refresh()` 会重新执行 `discover_skills` 更新内存索引。

## `SkillToolkit` 运行时能力

### 基础能力

- `build_prompt()`
  - 生成技能运行时说明 + 当前可用技能列表
- `list_available_skills()`
  - 返回 `- name: description` 列表

### 技能内容加载

- `load_skill(skill_name)`
  - 返回 `<skill_content ...>` 包裹的技能正文
  - 同时附带最多 `max_files` 个目录内文件样本（`<skill_files>`）

### 文件检索与读取

- `find_skill_files(skill_name, pattern="**/*", contains="")`
  - 用 `glob(pattern)` 查找文件
  - `contains` 非空时，按文本子串过滤（大小写不敏感）
  - 最多返回 200 条相对路径

- `read_skill_file(skill_name, relative_path, start_line=1, max_lines=200)`
  - 路径必须留在技能目录内（阻止路径逃逸）
  - 目录路径会返回目录项列表
  - 文件读取后按 `行号: 内容` 输出
  - 行数上限受 `min(max_lines, read_max_lines)` 限制
  - 内容超长按 `max_chars` 截断并标记 `(Truncated)`

### 示例检索

- `load_skill_examples(skill_name, query, top_k=3)`
  - 对 query 和示例做 token 化匹配（正则 `[a-zA-Z0-9_]+`）
  - 打分规则：
    - 正文/标题 token 交集：`+1`
    - tag token 交集：`+2`
  - 取分数最高前 `top_k`，范围强制在 `[1, 10]`
  - 没有正分命中时返回全量排序前 N（回退策略）

### 入口命令执行（可选）

- `run_skill_entry(skill_name, args="")`
  - 仅在 `allow_run_entry=True` 时可用
  - 执行 `SKILL.md` frontmatter 的 `entry` 命令，并拼接额外参数 `args`
  - 程序名必须在白名单 `allowed_entry_programs`
  - 在技能目录下执行，使用 `subprocess.run(..., capture_output=True, timeout=command_timeout)`
  - 返回：
    - `exit_code`
    - 实际执行命令
    - stdout/stderr（总长度受 `max_chars` 限制）

## LangChain 工具装配

`build_agent_tools(toolkit)` 会注册这些 `@tool`：

- `list_available_skills`
- `load_skill`
- `find_skill_files`
- `read_skill_file`
- `load_skill_examples`
- `run_skill_entry`（仅当 `toolkit.allow_run_entry=True`）

`build_skill_capability(...)` 返回 `SkillCapability`：

- `prompt`: `toolkit.build_prompt()` 的结果
- `tools`: 上述工具集合
- `toolkit`: 底层 `SkillToolkit` 实例

## 配置参数

`SkillToolkit(...)` / `build_skill_capability(...)` 关键参数：

- `roots`: 技能根目录（单个或多个）
- `max_files`: `load_skill` 展示的样本文件上限（默认 25）
- `max_chars`: 单次文本输出最大字符数（默认 12000）
- `read_max_lines`: 单次读取最大行数硬上限（默认 250）
- `allow_run_entry`: 是否启用入口命令执行（默认 `False`）
- `command_timeout`: 入口命令超时秒数（默认 60）
- `allowed_entry_programs`: 允许执行的命令白名单

## 最小使用示例

```python
from skill_meta_toolkit import build_skill_capability

cap = build_skill_capability(
  roots=["~/.codex/skills", "./skills"],
  allow_run_entry=False,
)

system_prompt = cap.prompt
tools = cap.tools
```

## 设计取舍与边界

- 面向轻量本地技能库，不依赖数据库
- frontmatter 解析是简化实现，不是完整 YAML 解析器
- 同名技能以扫描顺序最后一次写入为准（会覆盖）
- 文件读取/命令执行都做了基础边界控制，但仍建议在受控目录下使用
