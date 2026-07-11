from langchain_openai import ChatOpenAI
from src.env_utils import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    LANGSMITH_API_KEY, ZHIPUAI_API_KEY,
    QWEN_API_KEY, QWEN_BASE_URL,
    LLM_MODEL_NAME, LLM_TEMPERATURE,
    LLM_TRIMMER_MAX_TOKENS, LLM_TOKEN_COUNTER, LLM_TRIMMER_STRATEGY,
)
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain.chat_models import init_chat_model
from langchain_core.messages import trim_messages

# DeepSeek 公网模型配置
# llm = ChatOpenAI(
#     temperature=0.5,
#     model="deepseek-chat",
#     api_key=DEEPSEEK_API_KEY,
#     base_url="https://api.deepseek.com",
# )


# Qwen32B模型配置
# llm = ChatOpenAI(
#     temperature=0.5,
#     model="Qwen/Qwen3-32B",
#     api_key=QWEN_API_KEY,
#     base_url=QWEN_BASE_URL,
# )
trimmer = trim_messages(
    max_tokens=LLM_TRIMMER_MAX_TOKENS,
    strategy=LLM_TRIMMER_STRATEGY,
    token_counter=LLM_TOKEN_COUNTER,
    include_system=True,
    allow_partial=False,
)
llm = ChatOpenAI(
    temperature=LLM_TEMPERATURE,
    model=LLM_MODEL_NAME,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)
#速率限制   流式输出
# rate_limiter = InMemoryRateLimiter(
#     requests_per_second=0.1,  #每10s允许一个请求
#     check_every_n_seconds = 0.1,  #每100毫秒检查一次是否允许发出请求
#     max_bucket_size = 10,  #控制最大突发请求数量
# )
# llm = init_chat_model(
#     model = "deepseek-ai/DeepSeek-R1",
#     model_provider = "deepseek",
#     api_key = DEEPSEEK_API_KEY,
#     api_base = DEEPSEEK_BASE_URL,
#     rate_limiter = rate_limiter,
# )
# resp = llm.invoke("三句话介绍明朝那些事儿")
# print(type(resp))
# print(resp)

# zhipuai_client = ZhipuAI(api_key=ZHIPUAI_API_KEY)