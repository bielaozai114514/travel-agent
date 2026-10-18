
# TravelAgent Docker 部署指南

本指南将帮助你使用 Docker 快速部署 TravelAgent 项目，包括前端、后端、MySQL 和 Qdrant 数据库。

## 📋 前提条件

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存

## 🚀 快速启动

### 方式一：使用快速启动脚本（推荐）

```bash
# 1. 克隆项目并进入目录
cd travel-agent

# 2. 运行快速启动脚本
chmod +x docker-start.sh
./docker-start.sh
```

### 方式二：手动启动

```bash
# 1. 复制环境变量配置文件
cp .env.docker.example .env.docker

# 2. 编辑 .env.docker，填入你的配置
# 至少需要修改:
#   - MODEL_API_KEY (你的 LLM API Key)
#   - SECRET_KEY (随机字符串)

# 3. 构建并启动所有服务
docker-compose up -d --build

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f
```

## 🌐 访问地址

服务启动成功后，可以通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端** | http://localhost:5173 | TravelAgent Web 应用 |
| **后端 API** | http://localhost:8000 | FastAPI 后端服务 |
| **API 文档** | http://localhost:8000/docs | Swagger UI 交互式文档 |
| **API 文档** | http://localhost:8000/redoc | ReDoc 文档 |
| **Qdrant UI** | http://localhost:6335/dashboard | Qdrant 管理界面 |
| **MySQL** | localhost:3307 | 数据库连接（本地工具用） |

**注意**：
- MySQL 和 Qdrant 的宿主机端口已修改为 3307 和 6334，避免与本地服务冲突
- 容器内部仍使用 3306 和 6333，`.env.docker` 中的配置无需修改 |

## 🔧 配置说明

### 环境变量文件关系说明

项目中有多个环境变量文件，各自用途不同：

| 文件 | 用途 | 使用场景 | 是否被 Docker 使用 |
|------|------|---------|-------------------|
| `backend/.env` | 后端本地开发环境 | 本机直接运行 `python main.py` | ❌ 否（被 .dockerignore 忽略） |
| `frontend/.env` | 前端本地开发环境 | 本机直接运行 `npm run dev` | ⚠️  是（代码挂载时会被读取） |
| `.env.docker` | Docker 部署环境 | `docker-compose up` 时使用 | ✅ 是（唯一配置源） |

**推荐做法：**
- **本地开发**：继续使用 `backend/.env` 和 `frontend/.env`
- **Docker 部署**：只使用 `.env.docker`，配置好后与本地环境互不干扰

### 环境变量文件 `.env.docker`

主要配置项：

```env
# ========== MySQL 配置 ==========
MYSQL_ROOT_PASSWORD=root123456      # MySQL root 密码
MYSQL_DATABASE=travel_agent          # 数据库名
MYSQL_USER=travel                    # 数据库用户
MYSQL_PASSWORD=travel123456          # 数据库密码

# ========== Backend 配置 ==========
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
MYSQL_URL=mysql+aiomysql://travel:travel123456@mysql:3306/travel_agent?charset=utf8mb4
SECRET_KEY=your_jwt_secret_key_here  # 请修改为随机字符串

# ========== LLM 配置（必须修改） ==========
MODEL_API_KEY=your_model_api_key_here
MODEL_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=Qwen/Qwen3-8B

# ========== 高德地图配置（可选） ==========
AMAP_API_KEY=your_amap_api_key_here
```

### 默认管理员账号

| 项 | 值 |
|----|-----|
| 用户名 | `admin` |
| 密码 | `admin123456` |
| 邮箱 | `admin@test.com` |

## 🐳 Docker Compose 服务说明

### 服务列表

```yaml
services:
  mysql:      # MySQL 8.0 数据库
  qdrant:     # Qdrant v1.17.0 向量数据库
  backend:    # FastAPI 后端服务
  frontend:   # Vue 3 前端开发服务器
```

### 数据持久化

数据通过 Docker Volumes 持久化：

- `travelagent-mysql-data`: MySQL 数据
- `travelagent-qdrant-data`: Qdrant 数据

### 网络

所有服务通过 `travelagent-network` 内部网络通信。

## 🔨 常用命令

### 服务管理

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 启动并重新构建
docker-compose up -d --build

# 停止所有服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器，同时删除数据卷（⚠️  会清空所有数据！）
docker-compose down -v

# 查看服务状态
docker-compose ps
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mysql
```

### 进入容器

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入 MySQL 容器
docker-compose exec mysql bash

# 进入前端容器
docker-compose exec frontend sh
```

### 数据库操作

```bash
# 手动运行 Alembic 迁移
docker-compose exec backend alembic upgrade head

# 重新初始化权限
docker-compose exec backend python utils/init_permissions.py

# 重新初始化管理员
docker-compose exec backend python utils/init_admin.py

# 连接 MySQL
docker-compose exec mysql -u travel -p travel_agent
# 密码: travel123456
```

## 💻 开发模式说明

### 热重载

当前配置为开发模式，支持代码热重载：

- **后端**: Python 代码修改后，uvicorn 会自动重启
- **前端**: Vue 代码修改后，Vite HMR 会自动更新浏览器

### 本地代码挂载

本地代码目录已挂载到容器内：

- `./backend` → `/app` (后端容器)
- `./frontend` → `/app` (前端容器)

修改本地代码会立即反映到容器中。

## 🔧 故障排除

### 端口被占用

当前默认端口配置（已避免常用端口冲突）：

| 服务 | 宿主机端口 | 容器内部端口 | 说明 |
|------|-----------|-------------|------|
| MySQL | 3307 | 3306 | 避免与本地 MySQL 冲突 |
| Qdrant HTTP | 6335 | 6333 | 避免与本地 Qdrant 冲突 |
| Qdrant gRPC | 6336 | 6334 | 避免与本地 Qdrant 冲突 |
| 后端 | 8000 | 8000 | - |
| 前端 | 5173 | 5173 | - |

如果仍有端口冲突，可以继续修改 `docker-compose.yml`：

```yaml
ports:
  - "8001:8000"  # 后端：将主机端口改为 8001
  - "5174:5173"  # 前端：将主机端口改为 5174
```

**重要**：
- **容器内部端口永远不需要修改**（保持 3306、6333、8000、5173）
- `.env.docker` 中的配置（如 `MYSQL_URL`、`QDRANT_HOST`）不需要改，它们使用容器内部网络
- 只有用本地工具连接时才使用宿主机端口（如 MySQL Workbench 连 3307）

### MySQL 启动失败

```bash
# 查看 MySQL 日志
docker-compose logs mysql

# 如果是数据卷问题，尝试删除数据卷重新初始化
docker-compose down -v
docker-compose up -d
```

### 后端连接数据库失败

```bash
# 确认 MySQL 健康检查通过
docker-compose ps

# 检查后端日志
docker-compose logs backend

# 手动进入后端容器测试连接
docker-compose exec backend bash
python -c "import asyncio; from dependencies.db_session import AsyncSessionLocal; print('DB config loaded')"
```

### 前端无法访问后端 API

- 确认后端服务正常运行：`docker-compose ps backend`
- 检查前端 `.env` 文件中的 `VITE_API_BASE_URL` 配置
- 查看浏览器控制台网络请求

## 📝 生产环境部署建议

⚠️  **当前配置为开发环境，生产环境请做以下调整：**

1. **前端**: 使用多阶段构建，构建静态文件后用 Nginx 托管
2. **后端**: 关闭 `RELOAD`，增加 `WORKERS` 数量
3. **数据库**: 配置定期备份
4. **网络**: 使用 Nginx 反向代理，配置 HTTPS
5. **配置**: 使用 Docker Secrets 管理敏感信息
6. **日志**: 配置日志轮转和集中收集

## 🤝 贡献

如有问题或建议，欢迎提交 Issue 或 PR！

