import arxiv
from langchain.tools import tool

@tool
def search_arxiv(query: str, limit: int = 5):
    """
    arXiv 搜索
    """
    try:
        # 构造 Client，通过 delay 和 num_retries 保证稳定性
        client = arxiv.Client(
            page_size=limit,
            delay_seconds=3,
            num_retries=3
        )

        # 构造搜索对象 (按相关性排序)
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance
        )

        results = []
        for r in client.results(search):
            results.append({
                "source": "arxiv", # 标记来源，让 Agent 知道
                "id": r.entry_id,
                "title": r.title,
                "year": r.published.year,
                "authors": ", ".join([a.name for a in r.authors[:3]]),
                "abstract": r.summary.replace("\n", " "), # arXiv 摘要换行很多，需清洗
                "citations": "N/A", # arXiv 原生不提供引用数，这是最大的痛点
                "link": r.pdf_url
            })
        
        return results

    except Exception as e:
        print(f"arXiv fallback failed: {e}")
        return []

# --- 测试调用 ---
if __name__ == "__main__":
    # 示例：搜索 Agent Memory 相关论文
    papers = search_arxiv.invoke({
        "query": "Agent Memory",
        "limit": 3
    })

    for p in papers:
        print(f"[{p['year']}] {p['title']} (Cited: {p['citations']})")
        print(f"   Abstract snippet: {p['abstract'][:100]}...\n")
