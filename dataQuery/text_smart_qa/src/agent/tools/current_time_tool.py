from langchain_core.tools import tool
from datetime import datetime
import pytz
from src import env_utils

@tool
def get_current_time() -> str:
    """
    获取当前的精确系统时间。
    当用户询问涉及到当下时间时，必须调用此工具。
    返回格式：YYYY-MM-DD HH:MM:SS 星期X
    """
    tz = pytz.timezone(env_utils.TIMEZONE)
    now = datetime.now(tz)
    
    # 格式化输出
    # %A 代表星期几的全称
    current_time = now.strftime("%Y-%m-%d %H:%M:%S %A")
    
    return f"当前系统时间为: {current_time}"

# --- 测试代码 ---
if __name__ == "__main__":
    print(get_current_time.invoke({}))