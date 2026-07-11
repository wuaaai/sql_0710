import sys, os
from loguru import logger
from src import env_utils

#获取当前项目的绝对路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#日志文件路径
log_file = os.path.join(root_dir, "logs")
#确保日志目录存在
if not os.path.exists(log_file):
    os.makedirs(log_file)

class MyLogger:
    def __init__(self):
        self.logger = logger #写日志的对象
        self.logger.remove() #移除默认的日志处理器
        #日志保存到文件
        self.logger.add(log_file, level=env_utils.LOG_LEVEL, encoding='utf-8',
                        format="{time:YYYY-MM-DD HH:mm:ss} |" #日志时间
                        "{process.name} |" #进程名称
                        "{thread.name} |" #线程名称
                        "{module}.{function}" #模块名.方法名
                        ": {line}  |" #行号
                        "{level}: " #日志级别
                        "{message}", #日志内容
                        rotation=env_utils.LOG_ROTATION,
                        retention=env_utils.LOG_RETENTION,
        )
    def get_logger(self):
        return self.logger
log = MyLogger().get_logger()      