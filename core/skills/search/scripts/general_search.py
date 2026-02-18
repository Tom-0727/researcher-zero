import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


def search(query: str, **kwargs):
    """使用 Tavily 进行通用搜索。kwargs 会传给 TavilyClient.search。"""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("未设置环境变量 TAVILY_API_KEY")
    client = TavilyClient(api_key=key)
    return client.search(query, **kwargs)
