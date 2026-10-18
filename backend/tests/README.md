
# 接口测试指南

## 测试方案

- **测试方式**：真实 HTTP 请求（需要手动启动 FastAPI 应用）
- **数据库**：独立测试库 `test_travel_agent`
- **认证方式**：管理员账号 `admin` / `admin123456`

---

## 快速开始

### 1. 初始化测试数据库（只需运行一次）

```bash
cd backend
python -m tests.helpers
```

这会：
- 创建 `test_travel_agent` 数据库
- 创建所有表
- 初始化权限数据
- 创建管理员账号（admin/admin123456）

### 2. 启动测试服务器

```bash
# Windows (Git Bash / WSL)
ENV=test python main.py

# Windows (PowerShell)
$env:ENV="test"; python main.py
```

确保看到：
- 数据库连接的是 `test_travel_agent`
- "启动成功" 日志

### 3. 运行测试

新开一个终端窗口：

```bash
cd backend
python -m pytest tests/ -v
```

---

## 测试文件结构

```
tests/
├── conftest.py          # 共享 fixtures
├── helpers.py           # 测试辅助函数
├── test_users.py        # 用户接口测试
├── test_roles.py        # 角色接口测试
├── test_permissions.py  # 权限接口测试
└── ...
```

---

## Fixtures 说明

| Fixture | 说明 |
|---------|------|
| `api_client` | HTTP 客户端，连接 `http://localhost:8000` |
| `auth_headers` | 带管理员认证的请求头 |
| `admin_token` | 管理员 JWT token |
| `test_user_data` | 测试用户数据（faker 生成） |
| `faker` | Faker 实例 |

---

## 添加新测试

参考 `test_users.py` 的写法：

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
class TestMyEndpoints:
    async def test_something(self, api_client, auth_headers):
        response = await api_client.get("/some-endpoint", headers=auth_headers)
        assert response.status_code == 200
```

---

## 常见问题

**Q: 测试连接不上服务器？**

A: 确保：
1. 服务器已启动（`ENV=test python main.py`）
2. 服务器日志显示连接的是 `test_travel_agent`
3. 端口是 8000

**Q: 管理员账号不存在？**

A: 重新运行初始化：`python -m tests.helpers`

**Q: 怎么只运行某个测试文件？**

A: `python -m pytest tests/test_users.py -v`

