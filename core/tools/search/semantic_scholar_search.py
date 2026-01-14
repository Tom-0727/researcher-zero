import requests
import time
from typing import List, Dict, Any
from core.utils.logs import logger

def search_semantic_scholar(
    query: str, 
    limit: int = 10, 
    api_key: str = None, 
    is_survey: bool = False
) -> List[Dict[str, Any]]:
    """
    使用 Semantic Scholar Graph API 搜索论文。
    
    Args:
        query: 搜索关键词 (例如 "RAG with knowledge graphs")
        limit: 返回结果数量 (默认 10)
        api_key: 你的 S2 API Key (推荐申请，否则限制每秒1次请求)
        is_survey: 是否强制搜索综述类文章
    
    Returns:
        包含论文元数据的字典列表
    """
    
    # 1. 基础 Endpoint
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    # 2. 优化 Query：如果 Agent 意图是找综述，自动注入关键词
    # 参考自 s2-folks 社区经验，显式添加 "review" 或 "survey" 往往比单纯依靠相关性排序更有效
    final_query = query
    if is_survey:
        final_query = f'{query} ("literature review" | "survey" | "state of the art")'
    
    # 3. 指定返回字段 (Fields)
    # ReAct Agent 需要摘要(abstract)来判断相关性，需要引用数(citationCount)来判断重要性
    fields = ",".join([
        "paperId", 
        "title", 
        "abstract", 
        "year", 
        "citationCount", 
        "url"
    ])
    
    params = {
        "query": final_query,
        "limit": limit,
        "fields": fields,
        # 'offset': 0 # 如果需要翻页可以加这个参数
    }
    
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
        
    try:
        # 4. 发送请求
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        
        # 5. 错误处理
        if response.status_code == 429:
            return [{"error": "Rate limit exceeded. Please wait or use an API Key."}]
        
        response.raise_for_status()
        data = response.json()
        
        # 6. 数据清洗
        # 某些论文可能没有摘要，Agent 需要知道这一点
        results = []
        for paper in data.get("data", []):
            results.append({
                "id": paper.get("paperId"),
                "title": paper.get("title"),
                "year": paper.get("year"),
                "citations": paper.get("citationCount"),
                "abstract": paper.get("abstract") if paper.get("abstract") else "No abstract available.",
                "link": paper.get("url")
            })
            
        return results

    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]

# --- 测试调用 ---
if __name__ == "__main__":
    # 示例：搜索 RAG 相关的综述
    papers = search_semantic_scholar("Agent Memory", limit=3, is_survey=True)
    
    for p in papers:
        print(f"[{p['year']}] {p['title']} (Cited: {p['citations']})")
        print(f"   Abstract snippet: {p['abstract'][:100]}...\n")