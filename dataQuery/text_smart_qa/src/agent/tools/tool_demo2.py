from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from env_utils import TavilyClient_API_KEY
from tavily import TavilyClient

class SearchArgs(BaseModel):
    query: str = Field(..., description="搜索的关键词或问题")

class MyWebSearchTool(BaseTool):
    name : str= "wu_web_search" 
    description : str = "互联网搜索的工具，可以搜索所有公开的信息。返回搜索的结果信息，该信息是一个文本字符串"
    args_schema : type[BaseModel] = SearchArgs
    async def _run(self, query : str) -> str:
        try:
            client = TavilyClient(api_key=TavilyClient_API_KEY)
            results = client.search(query, max_results=5)
            if not results:
                return "未找到相关信息。"
            return str(results)
        except Exception as e:
            print(e)
            return f"搜索时出错: {e}"