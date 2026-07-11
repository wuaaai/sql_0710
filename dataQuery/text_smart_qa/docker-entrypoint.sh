#!/bin/bash
# Docker 启动脚本
# 用法:
#   挂载自定义配置: docker run -v /path/.env.prod:/app/.env ...
#   环境变量切换:   docker run -e APP_ENV=prod ...
#   APP_ENV=prod  → 从镜像内置的 .env.prod 复制
#   APP_ENV=dev   → 从镜像内置的 .env.dev 复制
#   不设置时默认 dev

set -e

cd /app

# 如果用户已挂载自定义 .env，优先使用，不做任何切换
if [ -f /app/.env ]; then
    echo "[entrypoint] 检测到已挂载 .env，使用自定义配置"
else
    case "${APP_ENV:-dev}" in
        prod)
            echo "[entrypoint] 切换到生产环境 (内网)"
            cp /app/.env.prod /app/.env
            ;;
        dev)
            echo "[entrypoint] 切换到开发环境 (本地)"
            cp /app/.env.dev /app/.env
            ;;
        *)
            echo "[entrypoint] 未知 APP_ENV=${APP_ENV}，回退到 dev"
            cp /app/.env.dev /app/.env
            ;;
    esac
fi

echo "[entrypoint] 执行: $*"
exec "$@"
