# Dockerfile 骨架
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
CMD ["python", "-m", "src.runtime.api_server"]
