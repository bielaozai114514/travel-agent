
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（包括 MySQL 客户端库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements.txt，利用 Docker 缓存
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 直接启动
CMD ["python", "main.py"]

