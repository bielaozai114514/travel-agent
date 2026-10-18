# TravelAgent - AI 智能旅行规划系统

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121+-green.svg)
![Vue](https://img.shields.io/badge/Vue-3.5+-brightgreen.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)

---

一个基于大语言模型的智能旅行规划系统，采用多智能体工作流架构，提供个性化的行程推荐、AI 助手服务和旅游攻略社区。核心研究贡献为 **TCR-RAG（Tourism-Constrained RAG）**——面向旅游场景的向量分数主导检索算法与轻量约束校正方法。

---

## 🚀 项目特色

### 核心功能
- 🤖 **多智能体工作流规划**：多个专业 Agent 按工作流协作生成详细行程（并发搜索 + 中心规划）
- 🎯 **意图识别与参数提取**：TripIntentAgent 自动识别规划/修改意图，参数不全时智能追问
- 🛠️ **行程修改 Agent**：TripModifierAgent 根据用户需求修改已有行程，遵循"最小化修改原则"
- 💬 **AI 对话系统**：流式响应的智能客服，支持思考过程可视化，可感知当前行程上下文
- 📝 **旅游攻略社区**：用户创建、编辑、分享攻略，包含点赞、评论、审核工作流
- 🔍 **TCR-RAG 攻略检索**：向量分数主导 + 旅游约束校正的语义检索，为规划提供高质量参考
- 👥 **完整权限系统**：JWT 认证 + RBAC 权限控制
- 📊 **管理后台**：用户、角色、权限、攻略可视化管理
- 🌍 **地图服务集成**：高德地图 MCP 协议支持，景点/天气/酒店查询
- ⚡ **服务预热模块**：按优先级异步预热，提升首屏体验
- 📱 **响应式设计**：支持桌面端和移动端
- 🔄 **后台任务系统**：行程规划/修改可后台运行，支持进度查询和中途切换
- 🔗 **行程-对话联动**：会话和行程 1:1 关联，双向跳转
- 📊 **规划/修改进度实时展示**：对话页面侧边栏 + 行程列表，双端展示进度

### 技术亮点
- ⚡ **高性能**：FastAPI 异步框架 + Vue 3 响应式开发
- 🎯 **Settings 分层配置**：各 Agent 可独立配置 LLM，灵活调度
- 🧠 **EsAgent 自研框架**：支持多种 Agent 类型（Simple/ReAct/PlanSolve）
- 🔄 **实时反馈**：SSE 流式响应，思考过程和工具调用可视化
- 🗄️ **数据持久化**：旅行计划、攻略历史记录查询
- 🛡️ **安全可靠**：JWT 认证 + 权限控制 + 雪花 ID 生成
- 🔧 **MCP 协议**：支持模型上下文协议，集成外部工具服务
- 🧪 **RAG 实验体系**：6 种检索方法对比 + 消融实验 + 83 条标注评测集 + 可复现评估框架

---

## 🤖 多智能体工作流

TravelAgent 采用多个专业智能体按工作流协作完成旅行规划和修改：

### 规划工作流

```
用户输入 → 意图识别 → 参数提取/追问 → 并发搜索(景点+天气+酒店+攻略RAG) → 行程规划整合 → 输出计划
```

各 Agent 由编排层（TripPlannerAgent）统一调度，景点/天气/酒店/攻略四个搜索任务并发执行，最后由规划 Agent 整合所有信息生成完整行程。这不是 Agent 间的自主协商，而是预设工作流中的分工协作。

### 修改工作流

```
修改需求 → 意图识别(修改) → 分析修改类型 → 按需搜索补充信息 → 最小化修改 → 输出修改后行程
```

### Agent 列表

| Agent | 职责 | 工具 |
|-------|------|------|
| **意图识别 Agent** | 识别用户意图（规划/修改/聊天）并提取参数 | - |
| **景点搜索 Agent** | 根据城市和偏好搜索景点 | 高德地图 MCP |
| **天气查询 Agent** | 查询目的地天气信息 | 高德地图 MCP |
| **酒店推荐 Agent** | 推荐合适的住宿 | 高德地图 MCP |
| **行程规划 Agent** | 整合搜索结果生成完整计划 | - |
| **行程修改 Agent** | 根据用户需求修改已有行程，最小化修改原则 | 高德地图 MCP |
| **攻略专家 Agent** | 搜索和总结已有攻略，为规划提供参考 | - |
| **聊天助手 Agent** | 日常对话和旅游咨询 | 内置工具 |

---

## 🔍 TCR-RAG 攻略检索算法

### 算法概述

TCR-RAG（Tourism-Constrained RAG）是面向旅游场景的向量分数主导检索算法。核心思想：**向量嵌入模型已提供高质量语义排序，旅游约束特征仅作轻量校正**，不破坏模型原始排序能力。

### 方法演进

| 方法 | 描述 | 状态 |
|------|------|------|
| M0 Basic | bge-small-zh 嵌入 + 基础 Qdrant 搜索 | 基线 |
| M1 Enhanced | 增强分块（标题/城市/标签前缀）+ 增强索引 | 基线 |
| M2 LLM-RAG | M1 + LLM 查询改写 + 关键词提取 | 遗留（高延迟，已弃用） |
| M3 TCR | 多路召回 + 约束门控 + 加权评分 | 消融对照 |
| M4 TCR-Tuned | M3 + guide 级聚合 + 增强特征 | 消融对照 |
| **M5 Adaptive** | **向量分数主导 + 轻量旅游约束校正** | **最终方法** |

### M5 Adaptive 评分公式

```
adaptive_score = vector_score
  + 0.04 × 标题匹配     (title_match)
  + 0.03 × 标签匹配     (tag_match)
  + 0.02 × 关键词匹配   (keyword_match)
  + 0.015 × 板块匹配    (section_match)
  + 0.02 × 城市匹配     (city_match)
  - 0.20 × 城市不匹配惩罚 (city_mismatch_penalty)
  + 0.005 × min(命中次数, 3) (hit_count)
```

设计要点：
- **无 LLM 调用**：排序过程完全基于规则，延迟极低（23.4ms）
- **城市不匹配强惩罚**（-0.20）是最强单一特征，有效过滤跨城市噪音
- **最大校正幅度约 +0.125**，高置信度向量排序不会被破坏
- **Guide 级去重**：按标题聚合，保留最高向量分数的代表性分块

### 实验结果（83 条评测样本，5 城市）

| 方法 | Hit@3 | P@5 | R@5 | MRR@5 | City@5 | SecG@5 | Must@1 | Top1+ | Neg@5 | 延迟 |
|------|-------|-----|-----|-------|--------|--------|--------|-------|-------|------|
| M0 Basic | 0.964 | 0.301 | 0.940 | 0.915 | 0.890 | 0.376 | 0.747 | 0.880 | 0.034 | 188.6ms |
| M1 Enhanced | 0.940 | 0.304 | 0.946 | 0.913 | 0.976 | 0.393 | 0.735 | 0.868 | 0.007 | 22.2ms |
| M3 TCR | 0.783 | 0.280 | 0.886 | 0.718 | 0.995 | 0.424 | 0.446 | 0.602 | 0.005 | 38.2ms |
| M4 TCR-Tuned | 0.916 | 0.284 | 0.892 | 0.800 | 0.992 | 0.522 | 0.566 | 0.687 | 0.005 | 54.3ms |
| **M5 Adaptive** | **0.928** | **0.316** | **0.976** | **0.917** | **0.995** | **0.512** | **0.747** | **0.880** | **0.007** | **23.4ms** |

M5 实现综合最优平衡：Top1 准确率（0.880）和召回率（0.976）最高，同时保持城市精确率（0.995）和板块指导率（0.512），延迟仅 23.4ms。

### 消融实验结论

- **M5 v1 vs v2**：v2 放宽置信度门控（65% 保持原序 vs v1 的 1.2%），MRR、MustHit、Recall、SectionMatch 均下降，验证了"向量分数主导"设计的正确性
- **M3 → M4 → M5**：从全局规则评分到 guide 级聚合再到轻量校正，Top1+ 从 0.602 → 0.687 → 0.880，证明保留向量排序的重要性

### RAG 搜索策略配置

通过环境变量 `RAG_SEARCH_MODE` 切换检索方法：
- `adaptive_tcr`（默认）→ M5
- `tcr` → M3（实验对照）
- `enhanced_vector` → M1（实验对照）
- `basic_vector` → M0（实验对照）
- `llm_rag` → M2（遗留降级）

---

## 📁 项目结构

```
TravelAgent/
├── backend/                 # 后端服务
│   ├── main.py             # 应用入口
│   ├── core/               # 核心业务逻辑
│   │   ├── agent.py        # 聊天 Agent 服务（含行程上下文注入）
│   │   ├── trip_planner_agent.py  # 旅行规划多智能体工作流
│   │   ├── trip_intent_agent.py   # 行程意图识别 Agent
│   │   ├── trip_modifier_agent.py # 行程修改 Agent
│   │   ├── task_manager.py        # 后台任务管理器
│   │   ├── llm.py          # LLM 调用封装
│   │   ├── warmup.py       # 服务预热管理
│   │   └── EsAgent/        # 自研 Agent 框架
│   │       ├── agents/     # 多种 Agent 实现
│   │       ├── tools/      # 工具系统（内置/RAG/MCP）
│   │       └── protocols/mcp/  # MCP 协议实现
│   ├── models/             # 数据库模型
│   ├── routers/            # API 路由
│   ├── curd/               # 数据库操作
│   ├── schemas/            # Pydantic 模型
│   ├── services/           # 业务服务
│   │   ├── amap_service.py         # 高德地图服务
│   │   ├── location_fix_service.py # 位置修复服务
│   │   ├── guide_rag_service.py    # 攻略 RAG 主入口（按 RAG_SEARCH_MODE 分发）
│   │   ├── adaptive_tcr_ranker.py  # M5 自适应 TCR-RAG 排序器
│   │   ├── tcr_rag_service.py      # M3 TCR-RAG 服务（消融对照）
│   │   ├── rag_tuned_ranker.py     # M4 增强排序器（消融对照）
│   │   ├── rag_query_utils.py      # RAG 查询工具函数
│   │   └── tcr_section_classifier.py # 分块板块分类器
│   ├── settings/           # Settings 分层配置系统
│   ├── scripts/            # 独立脚本
│   │   ├── evaluate_rag.py         # RAG 评测脚本
│   │   ├── import_guides.py        # 种子攻略批量导入
│   │   ├── clear_seed_guides.py    # 清理种子攻略
│   │   └── sync_basic_rag.py       # 基础 RAG 索引同步
│   ├── data/               # 数据文件
│   │   ├── eval/           # 评测数据集与结果
│   │   │   ├── rag_eval_queries.jsonl  # 83 条标注评测集
│   │   │   ├── final_results/      # 最终实验结果（论文数据）
│   │   │   ├── final_results_recheck/ # 可复现性验证
│   │   │   └── archive/            # 历史实验归档
│   │   └── seed_guides/    # 种子攻略（JSON 元数据 + Markdown 正文）
│   └── utils/              # 工具函数
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   │   ├── travel/trip/    # 行程规划
│   │   │   ├── travel/chat/    # AI 对话
│   │   │   ├── travel/guide/   # 旅游攻略
│   │   │   └── admin/          # 后台管理
│   │   ├── components/     # 通用组件
│   │   ├── api/            # API 接口
│   │   ├── pinia/          # 状态管理
│   │   └── layouts/        # 布局组件
│   └── package.json
└── README.md
```

---

## 🛠️ 技术栈

### 后端
| 技术 | 版本 | 说明 |
|------|------|------|
| FastAPI | 0.121+ | 异步 Web 框架 |
| SQLAlchemy | 2.x | ORM 框架 |
| OpenAI API | 1.0+ | LLM 调用（兼容 OpenAI API 协议） |
| MySQL | 8.0+ | 关系型数据库 |
| Qdrant | - | 向量数据库（攻略 RAG） |
| bge-small-zh-v1.5 | - | 中文嵌入模型（512 维） |
| JWT | PyJWT | 认证机制 |
| Alembic | - | 数据库迁移 |
| FastMCP | 2.0+ | MCP 协议支持 |

### 前端
| 技术 | 版本 | 说明 |
|------|------|------|
| Vue | 3.5+ | 前端框架 |
| Element Plus | 2.13+ | UI 组件库 |
| Pinia | 3.0+ | 状态管理 |
| Axios | 1.13+ | HTTP 客户端 |
| Vite | 6.2+ | 构建工具 |
| Marked | - | Markdown 渲染 |

---

## 📦 快速开始

### 系统要求
- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Qdrant（攻略 RAG 功能必需）

### 1. 克隆项目
```bash
git clone <repo_url>
cd TravelAgent
```

### 2. 后端启动

#### 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

#### 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

#### 数据库初始化
```bash
# 确保 MySQL 服务已启动
# 运行迁移
alembic upgrade head

# 初始化权限和管理员
python utils/init_permissions.py
python utils/init_admin.py
```

#### 导入种子攻略（可选）
```bash
# 导入 5 城市共 36 篇种子攻略到 MySQL + Qdrant
python scripts/import_guides.py --dir data/seed_guides --author-username admin

# 仅预览不写入
python scripts/import_guides.py --dir data/seed_guides --author-username admin --dry-run
```

#### 启动服务
```bash
python main.py
# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**服务预热说明：**
- P1（立即）: EmbeddingModel、Qdrant 连接
- P2（延迟 2 秒）: 聊天 Agent、行程规划 Agent

访问 API 文档：http://localhost:8000/docs
健康检查接口：http://localhost:8000/health

### 3. 前端启动

#### 安装依赖
```bash
cd frontend
npm install
```

#### 启动开发服务器
```bash
npm run dev
```

访问应用：http://localhost:5173

---

## ⚙️ 配置说明

### Settings 分层配置系统

项目支持不同 Agent 独立配置 LLM，通过环境变量灵活配置：

```env
# ========== 默认 LLM 配置 ==========
MODEL_API_KEY="your_api_key"
MODEL_BASE_URL="https://api.siliconflow.cn/v1"
MODEL_NAME="Qwen/Qwen3-8B"
MODEL_TEMPERATURE=0.7
MODEL_TIMEOUT=120

# ========== 各 Agent 特定配置（可选，不设置则用默认） ==========
# 聊天助手 Agent
CHAT_AGENT_API_KEY=...
CHAT_AGENT_MODEL=...
CHAT_AGENT_TEMPERATURE=...

# 景点搜索 Agent
ATTRACTION_AGENT_API_KEY=...
ATTRACTION_AGENT_MODEL=...

# 天气查询 Agent
WEATHER_AGENT_API_KEY=...

# 酒店推荐 Agent
HOTEL_AGENT_API_KEY=...

# 攻略专家 Agent
GUIDE_EXPERT_AGENT_API_KEY=...

# 行程规划 Agent
PLANNER_AGENT_API_KEY=...
```

### RAG 配置

```env
# RAG 搜索策略（默认 adaptive_tcr 即 M5 方法）
RAG_SEARCH_MODE=adaptive_tcr

# RAG 优化配置
RAG_USE_LLM_OPTIMIZATION=true
RAG_LLM_TEMPERATURE=0.3
RAG_QUERY_REWRITE_ENABLED=true
RAG_KEYWORD_EXTRACTION_ENABLED=true
RAG_CACHE_ENABLED=true
RAG_CACHE_TTL_SECONDS=3600
```

### 支持的模型
- Qwen/Qwen3-8B
- DeepSeek-V2.5
- 其他兼容 OpenAI API 的模型

---

## 🧪 RAG 评测

### 评测脚本

```bash
cd backend

# 完整评测（所有方法，排除 M2 LLM-RAG）
python scripts/evaluate_rag.py \
  --dataset data/eval/rag_eval_queries.jsonl \
  --output-dir data/eval/final_results \
  --candidate-pool 30

# 指定方法评测
python scripts/evaluate_rag.py \
  --dataset data/eval/rag_eval_queries.jsonl \
  --methods m0_basic,m1_enhanced,m5_adaptive \
  --output-dir data/eval/results \
  --candidate-pool 30

# 快速冒烟测试
python scripts/evaluate_rag.py \
  --dataset data/eval/rag_eval_queries.jsonl \
  --limit 5 --candidate-pool 30 \
  --output-dir data/eval/test_results
```

### 评测指标

| 指标 | 说明 |
|------|------|
| Hit@3 | 前 3 结果中命中的比例 |
| P@5 | 前 5 结果的精确率（固定 5 条） |
| R@5 | 前 5 结果的召回率 |
| MRR@5 | 前 5 结果的倒数排名均值 |
| City@5 | 前 5 结果城市匹配率 |
| SecG@5 | 前 5 结果板块指导率（匹配攻略 section） |
| MustHit@1 | 必须命中的攻略是否出现在 Top1 |
| Top1+ | Top1 结果为正例的比例 |
| Neg@5 | 前 5 结果中负例命中率（越低越好） |

---

## 🎮 使用指南

### 方式一：从对话发起规划

1. 登录系统，进入「AI 对话」页面
2. 直接说："帮我规划一个去杭州3天的行程"
3. 如果参数不全，AI 会自动追问（如："你想什么时候去呢？"）
4. 补充信息后，AI 自动启动后台规划
5. 右侧边栏实时显示规划进度
6. 规划完成后，自动在对话中发送确认消息，侧边栏显示行程摘要
7. 点击「查看完整行程」跳转到详细页面

### 方式二：从对话修改行程

1. 在关联了行程的对话中，直接说修改需求
2. 例如：
   - "不想去西湖，换一个景点"
   - "把第一天改成5月2日"
   - "再加一天行程"
   - "把酒店换成经济型"
3. AI 自动识别修改意图，启动后台修改任务
4. 遵循"最小化修改原则"：只修改用户要求的部分，其他保持原样
5. 右侧边栏实时显示修改进度
6. 修改完成后，自动在对话中发送确认消息

### 方式三：从规划页面发起

1. 登录系统
2. 进入「旅行规划」页面
3. 填写旅行信息：
   - 目的地城市
   - 旅行日期
   - 旅行天数
   - 交通方式（公共交通/自驾/步行/混合）
   - 住宿偏好（经济型/舒适型/豪华/民宿）
   - 偏好类型（历史文化/自然景观/美食购物等）
4. 点击「生成行程」
5. 系统提示"已开始后台规划"
6. 在左侧列表查看规划进度
7. 规划完成后点击查看详情

### 行程详情页功能

- **日计划**：查看每天的详细安排
- **景点信息**：包含门票、地址、经纬度
- **住宿推荐**：酒店信息和价格范围
- **餐饮推荐**：三餐建议
- **天气信息**：实时天气查询
- **预算统计**：详细的费用预估
- **打开对话**：点击右上角按钮，跳转至关联对话

### AI 对话功能

- 支持多轮对话
- 流式实时响应
- 思考过程可视化
- 工具调用展示
- 会话历史管理
- **行程感知**：关联行程后，AI 能读取当前行程信息
- **行程侧边栏**：可手动显示/隐藏，查看行程摘要

### 旅游攻略

- **创建攻略**：支持 Markdown 编辑器
- **攻略列表**：浏览、搜索、筛选攻略
- **攻略详情**：查看完整攻略、评论、点赞
- **审核工作流**：草稿 → 待审核 → 已发布/已拒绝

### 历史记录

- 查看过去生成的旅行计划
- 查看我的攻略
- 支持重新生成和分享功能

---

## 🔌 API 接口

### 认证方式
使用 JWT Bearer Token 认证：
```
Authorization: Bearer <token>
```

### 核心接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康检查 | GET | `/health` | 获取服务健康状态 |
| 健康检查 | GET | `/health/ready` | 检查服务是否就绪 |
| 健康检查 | GET | `/health/live` | 检查服务是否存活 |
| 用户 | POST | `/users/login` | 用户登录 |
| 用户 | POST | `/users/register` | 用户注册 |
| 用户 | GET | `/users/current` | 获取当前用户信息 |
| 聊天 | POST | `/chat/stream` | 发送消息（流式 SSE） |
| 旅行规划 | POST | `/trip/plan/stream` | 流式生成旅行计划 |
| 旅行规划 | GET | `/trip/plans` | 获取计划列表 |
| 攻略 | GET | `/guide/guides` | 获取攻略列表 |
| 攻略 | POST | `/guide/guides` | 创建攻略 |
| 攻略 | POST | `/guide/guides/{id}/like` | 点赞攻略 |

完整 API 文档：http://localhost:8000/docs

---

## 📄 许可证

本项目采用 **MIT License** 开源协议。

---

## 🙏 感谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的 Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Qwen](https://github.com/QwenLM/Qwen) - 阿里开源模型
- [Qdrant](https://qdrant.tech/) - 向量数据库
- [BGE](https://huggingface.co/BAAI/bge-small-zh-v1.5) - 中文嵌入模型
- [高德地图](https://lbs.amap.com/) - 地图与位置服务
