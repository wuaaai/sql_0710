# test.py
import sys
import os

# 打印当前目录
print("当前工作目录:", os.getcwd())
print("文件列表:", os.listdir())

# 检查 my_llm.py 是否存在
if "my_llm.py" in os.listdir():
    print("找到 my_llm.py 文件")
    
    # 尝试导入
    try:
        from my_llm import llm
        print("导入成功!")
        print(f"llm 对象类型: {type(llm)}")
        
        # 测试 llm 是否有 with_structured_output 方法
        if hasattr(llm, 'with_structured_output'):
            print("llm 有 with_structured_output 方法")
        else:
            print("警告: llm 没有 with_structured_output 方法")
            
    except ImportError as e:
        print(f"导入失败: {e}")
    except AttributeError as e:
        print(f"属性错误: {e}")
else:
    print("错误: 没有找到 my_llm.py 文件")