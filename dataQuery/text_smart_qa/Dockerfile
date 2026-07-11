FROM python:3.12-slim

WORKDIR /app

# 在前面添加这几行
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources
# 或者对于某些版本的 Debian
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources
# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 项目代码
COPY src/ ./src/
COPY server.py .
COPY langgraph.json .
COPY pyproject.toml .

# tiktoken 离线缓存（内网无法下载）
COPY tiktoken_cache/ ./tiktoken_cache/

# 环境配置模板（.env 通过 APP_ENV 或挂载生成）
COPY .env.dev .env.prod ./

# 入口脚本
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# 运行时目录
RUN mkdir -p /app/data /app/static/images /app/logs

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
