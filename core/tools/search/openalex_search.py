import requests
from langchain.tools import tool

@tool
def search_openalex(query: str, limit: int = 5, email: str = "your_email@example.com"):
    """
    OpenAlex 搜索兜底。
    在 header 中带上 User-Agent 和 email 可以进入 polite pool，响应更快。
    """
    base_url = "https://api.openalex.org/works"
    
    params = {
        "search": query,
        "per-page": limit,
        "select": "id,title,publication_year,cited_by_count,authorships,abstract_inverted_index,doi"
    }
    
    headers = {
        "User-Agent": f"MyResearchAgent/1.0 ({email})"
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", []):
            # OpenAlex 的摘要是 inverted index 格式，需要重组（或者直接拿不到摘要）
            # 为了简化，这里暂时不解析摘要，或者需要专门的解码函数
            # 这是一个 tradeoff：OpenAlex 的摘要解析比较麻烦
            
            authors = ", ".join([a["author"]["display_name"] for a in item.get("authorships", [])[:3]])
            
            results.append({
                "source": "openalex",
                "id": item.get("id"),
                "title": item.get("title"),
                "year": item.get("publication_year"),
                "citations": item.get("cited_by_count"),
                "authors": authors,
                "abstract": "Abstract retrieval requires decoding inverted index (skipped for speed).",
                "link": f"https://doi.org/{item.get('doi')}" if item.get('doi') else item.get("id")
            })
        return results

    except Exception as e:
        print(f"OpenAlex fallback failed: {e}")
        return []

# --- 测试调用 ---
if __name__ == "__main__":
    # 示例：搜索 Agent Memory 相关论文
    papers = search_openalex.invoke({
        "query": "Agent Memory",
        "limit": 3
    })

    for p in papers:
        print(f"[{p['year']}] {p['title']} (Cited: {p['citations']})")
        print(f"   Abstract snippet: {p['abstract'][:100]}...\n")
