from langchain_core.tools import tool
from pydantic import BaseModel,Field
from duckduckgo_search import DDGS
from env_utils import TavilyClient_API_KEY
from tavily import TavilyClient

@tool("my_web_search",parse_docstring=True)
def web_search(query: str) -> str:
    """
    互联网搜索的工具，可以搜索所有公开的信息。
    返回搜索的结果信息，该信息是一个文本字符串
    
    Args:
        query (str): 搜索的关键词或问题
    
    """
    try:
        client = TavilyClient(api_key=TavilyClient_API_KEY)
        results = client.search(query, max_results=5)
        if not results:
            return "未找到相关信息。"
        return str(results)
    except Exception as e:
        print(e)
        return f"搜索时出错: {e}"


#动态定义参数
class SearchArgs(BaseModel):
    query: str = Field(..., description="搜索的关键词或问题")
    second:int = Field(..., description="第二个参数")
@tool("my_web_search2",args_schema=SearchArgs,description="互联网搜索的工具，可以搜索所有公开的信息。",parse_docstring=True)
def web_search2(query: str,second:int) -> str:
    pass


if __name__ == "__main__":
    print(web_search.name)
    print(web_search.description)
    print(web_search.args)
    print(web_search.args_schema.model_json_schema())
    resp = web_search.invoke({"query": "石家庄今天天气如何，给我现在的时间"})
    print(resp)