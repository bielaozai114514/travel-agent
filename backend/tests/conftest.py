
"""
Pytest configuration and shared fixtures
接口测试配置 - 使用真实 HTTP 请求
"""
import pytest
import asyncio
from faker import Faker
from pathlib import Path
import sys
from httpx import AsyncClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.helpers import clear_all_tables

# Initialize faker
fake = Faker("zh_CN")


@pytest.fixture
def faker():
    """Faker instance fixture"""
    return fake


@pytest.fixture
async def test_user_data(faker):
    """Test user data fixture"""
    return {
        "username": faker.user_name(),
        "email": faker.email(),
        "password": "testpass123",
    }


# @pytest.fixture(autouse=True)
# async def setup_test_data():
#     """每个测试前清空数据库"""
#     await clear_all_tables()
#     yield


@pytest.fixture
async def api_client():
    """HTTP client fixture - 连接到真实的 FastAPI 应用"""
    async with AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        yield client


@pytest.fixture
async def admin_token(api_client):
    """获取管理员 token fixture"""
    response = await api_client.post(
        "/users/login",
        data={
            "username": "admin@test.com",
            "password": "admin123456",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, f"登录失败: {response.text}"
    token_data = response.json()
    return token_data["access_token"]


@pytest.fixture
async def auth_headers(admin_token):
    """带认证的请求头"""
    return {"Authorization": f"Bearer {admin_token}"}

