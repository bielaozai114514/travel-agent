#!/usr/bin/env bash

set -euo pipefail

echo "=========================================="
echo "  TravelAgent Docker 快速启动脚本"
echo "=========================================="
echo ""

# 检查 Docker
if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 Compose 命令，兼容老版和新版
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose 未安装"
    echo "请安装 docker-compose，或确保 'docker compose' 可用"
    exit 1
fi

# 检查 compose 文件
if [ -f docker-compose.yml ]; then
    COMPOSE_FILE="docker-compose.yml"
elif [ -f docker-compose.yaml ]; then
    COMPOSE_FILE="docker-compose.yaml"
else
    echo "❌ 未找到 docker-compose.yml 或 docker-compose.yaml"
    exit 1
fi

# 检查 .env.docker 文件
if [ ! -f .env.docker ]; then
    if [ -f .env.docker.example ]; then
        echo "⚠️  .env.docker 文件不存在，正在从 .env.docker.example 创建..."
        cp .env.docker.example .env.docker
    else
        echo "❌ .env.docker 和 .env.docker.example 都不存在"
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "  请编辑 .env.docker 文件，填入必要的配置："
    echo "  - MODEL_API_KEY (LLM API Key)"
    echo "  - AMAP_API_KEY (高德地图 API Key，可选)"
    echo "  - SECRET_KEY (JWT 密钥)"
    echo "=========================================="
    echo ""

    # 如果存在 backend/.env，尝试复制配置
    if [ -f backend/.env ]; then
        echo "检测到 backend/.env 文件，是否要复制配置到 .env.docker？(y/n)"
        read -r answer
        if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
            echo "正在复制配置..."
            while IFS= read -r line; do
                if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
                    continue
                fi

                key=$(printf '%s\n' "$line" | cut -d'=' -f1)
                value=$(printf '%s\n' "$line" | cut -d'=' -f2-)

                if [ -n "$key" ] && [ -n "$value" ]; then
                    if grep -q "^${key}=" .env.docker; then
                        sed -i "s|^${key}=.*|${key}=${value}|" .env.docker
                    fi
                fi
            done < backend/.env
            echo "✅ 配置已复制"
        fi
    fi

    echo ""
    echo "请编辑 .env.docker 后重新运行此脚本，或按回车继续（使用默认配置）..."
    read -r
fi

echo ""
echo "🚀 开始启动服务..."
echo "使用 Compose 命令: $COMPOSE_CMD"
echo "使用 Compose 文件: $COMPOSE_FILE"
echo ""

# 启动服务
if [ "$COMPOSE_CMD" = "docker-compose" ]; then
    docker-compose -f "$COMPOSE_FILE" --env-file .env.docker up -d --build
else
    docker compose -f "$COMPOSE_FILE" --env-file .env.docker up -d --build
fi

echo ""
echo "=========================================="
echo "  ✅ 服务启动成功！"
echo "=========================================="
echo ""
echo "  访问地址："
echo "  - 前端: http://localhost:5173"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo ""
echo "  查看日志:"
if [ "$COMPOSE_CMD" = "docker-compose" ]; then
    echo "  - docker-compose -f $COMPOSE_FILE logs -f"
    echo "  停止服务: docker-compose -f $COMPOSE_FILE down"
    echo "  重置数据: docker-compose -f $COMPOSE_FILE down -v"
else
    echo "  - docker compose -f $COMPOSE_FILE logs -f"
    echo "  停止服务: docker compose -f $COMPOSE_FILE down"
    echo "  重置数据: docker compose -f $COMPOSE_FILE down -v"
fi
echo ""
echo "  默认管理员账号:"
echo "  - 用户名: admin"
echo "  - 密码: admin123456"
echo ""
echo "=========================================="