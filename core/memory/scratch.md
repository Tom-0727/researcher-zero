## Graph Memory 设计方案

### 1. 节点定义

| type | 属性 | 说明 |
|------|------|------|
| Taxonomy | name, description | 方法论 |
| Category | name, description | 方法论下的类别 |
| Concept | name, definition | 具体概念 |
| Paper | title, problem, method, metrics, insights, year, abbreviation | 论文 |
| Benchmark | name, metrics_def, sota(JSON) | 评估集 |
| Challenge | name, description | 核心挑战/能力 |

### 2. 边定义

| rel | 关系 | 说明 |
|-----|------|------|
| BELONGS_TO | Paper→Concept→Category→Category->Taxonomy | 层级属于 |
| ADDRESSES | Paper→Challenge | 论文针对某挑战 |
| MEASURES | Benchmark→Challenge | 评测某能力 |
| HAS_SOTA | Benchmark→Paper | 当前SOTA |

### 3. ID 命名规则

```
规则：{type}_{name_slug}
- 小写
- 空格/横杠 → 下划线

示例：
- Concept "Chain-of-Thought" → concept_chain_of_thought
- Benchmark "MMLU" → benchmark_mmlu
- Paper "CoT Prompting" → paper_cot_prompting
```

### 4. 函数定义

| 类型 | 函数 | 说明 |
|------|------|------|
| 写入 | `add_node(type, id, **attrs)` | 添加节点 |
| 写入 | `add_edge(from_id, to_id, rel)` | 添加边 |
| 更新 | `update_node(id, **attrs)` | 更新节点属性 |
| 查询 | `get_node(id)` | 获取单节点 |
| 查询 | `get_knowledge_graph()` | 全局 Taxonomy→Concept→Paper 拓扑 |
| 查询 | `get_challenges()` | Challenge + 关联 Benchmark |

### 5. 存储

```python
import networkx as nx
import json

G = nx.DiGraph()

# 持久化
def save():
    with open("graph_db.json", "w") as f:
        json.dump(nx.node_link_data(G), f)

def load():
    with open("graph_db.json", "r") as f:
        return nx.node_link_graph(json.load(f))
```