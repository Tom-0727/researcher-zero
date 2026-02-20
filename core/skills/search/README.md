# Search Skill (Developer README)

## 1. 定位

- `search` skill 通过单一 entry 暴露三种搜索后端：
  - `semantic_scholar`
  - `arxiv`
  - `general`（Tavily）
- 统一由 `run_skill_entry("search", entry_args)` 调用，stdout 返回 JSON。

## 2. 文件与入口

- Skill file: `core/skills/search/SKILL.md`
- Entry script: `core/skills/search/scripts/search_tool.py`
- Entry command: `python scripts/search_tool.py`

## 3. CLI 协议

基础参数：

```text
--provider <semantic_scholar|arxiv|general> --query "<text>" [--limit 5]
```

仅 `general` 支持扩展参数：

```text
--kwargs-json "<JSON_OBJECT>"
```

说明：
- `limit` 必须是正整数。
- `kwargs-json` 不是 JSON object 会直接报错（无 fallback）。

## 4. 环境变量

- `semantic_scholar`: 可选 `S2_API_KEY`
- `general`: 必需 `TAVILY_API_KEY`

## 5. 调用示例

Semantic Scholar:

```text
run_skill_entry(
  "search",
  "--provider semantic_scholar --query '\"Large Language Models\" hallucination mitigation' --limit 5"
)
```

arXiv:

```text
run_skill_entry(
  "search",
  "--provider arxiv --query '\"Attention Is All You Need\"' --limit 3"
)
```

Tavily:

```text
run_skill_entry(
  "search",
  "--provider general --query 'langgraph tutorial' --kwargs-json '{\"topic\":\"general\"}'"
)
```
