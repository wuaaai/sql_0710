from ..agent.my_llm import llm

resp = llm.invoke("说一些明朝那些事的作者")
print(type(resp))
print(resp)
