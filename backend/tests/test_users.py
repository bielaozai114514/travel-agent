
"""
用户接口测试
"""
import pytest
from faker import Faker

fake = Faker("zh_CN")


@pytest.mark.integration
@pytest.mark.asyncio
class TestUserEndpoints:
    """用户接口测试"""

    async def test_register_success(self, api_client, test_user_data):
        """测试用户注册成功"""
        response = await api_client.post("/users/register", json=test_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert "id" in data

    async def test_register_duplicate_username(self, api_client, test_user_data):
        """测试用户名重复注册"""
        # 第一次注册
        await api_client.post("/users/register", json=test_user_data)

        # 第二次注册（相同用户名）
        user_data2 = test_user_data.copy()
        user_data2["email"] = f"another_{fake.unique.email()}"
        response = await api_client.post("/users/register", json=user_data2)

        # 应该返回 400 或 409
        assert response.status_code in [400, 409]

    async def test_register_duplicate_email(self, api_client, test_user_data):
        """测试邮箱重复注册"""
        # 第一次注册
        await api_client.post("/users/register", json=test_user_data)

        # 第二次注册（相同邮箱）
        user_data2 = test_user_data.copy()
        user_data2["username"] = f"another_{fake.unique.user_name()}"
        response = await api_client.post("/users/register", json=user_data2)

        # 应该返回 400 或 409
        assert response.status_code in [400, 409]

    async def test_login_success(self, api_client, test_user_data):
        """测试登录成功"""
        # 先注册
        await api_client.post("/users/register", json=test_user_data)

        # 再登录
        response = await api_client.post(
            "/users/login",
            data={
                "username": test_user_data["email"],
                "password": test_user_data["password"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, api_client, test_user_data):
        """测试登录密码错误"""
        # 先注册
        await api_client.post("/users/register", json=test_user_data)

        # 用错误密码登录
        response = await api_client.post(
            "/users/login",
            data={
                "username": test_user_data["email"],
                "password": "wrongpassword",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 401

    async def test_get_current_user(self, api_client, auth_headers):
        """测试获取当前用户信息"""
        response = await api_client.get("/users/current", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["email"] == "admin@test.com"
        assert "roles" in data

    async def test_get_current_user_unauthorized(self, api_client):
        """测试未登录获取当前用户"""
        response = await api_client.get("/users/current")

        assert response.status_code == 401

    async def test_get_user_list(self, api_client, auth_headers):
        """测试获取用户列表"""
        response = await api_client.get("/users", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "list" in data["data"]

    async def test_get_user_list_unauthorized(self, api_client):
        """测试未登录获取用户列表"""
        response = await api_client.get("/users")

        assert response.status_code == 401

    async def test_get_user_by_id(self, api_client, auth_headers, test_user_data):
        """测试通过ID获取用户"""
        # 先创建一个用户
        register_response = await api_client.post("/users/register", json=test_user_data)
        user_id = register_response.json()["id"]

        # 获取用户
        response = await api_client.get(f"/users/{user_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == test_user_data["username"]

    async def test_update_user(self, api_client, auth_headers, test_user_data):
        """测试更新用户"""
        # 先创建一个用户
        register_response = await api_client.post("/users/register", json=test_user_data)
        user_id = register_response.json()["id"]

        # 更新用户
        update_data = {
            "username": f"new_username_{fake.unique.user_name()}",
            "email": f"newemail_{fake.unique.email()}",
        }
        response = await api_client.put(f"/users/{user_id}", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == update_data["username"]
        assert data["email"] == update_data["email"]

    async def test_delete_user(self, api_client, auth_headers, test_user_data):
        """测试删除用户"""
        # 先创建一个用户
        register_response = await api_client.post("/users/register", json=test_user_data)
        user_id = register_response.json()["id"]

        # 删除用户
        response = await api_client.delete(f"/users/{user_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_batch_delete_users(self, api_client, auth_headers):
        """测试批量删除用户"""
        # 创建多个用户
        user_ids = []
        for i in range(3):
            user_data = {
                "username": f"testuser_{fake.unique.user_name()}",
                "email": f"test_{fake.unique.email()}",
                "password": "testpass123",
            }
            register_response = await api_client.post("/users/register", json=user_data)
            user_ids.append(register_response.json()["id"])

        # 批量删除 - 使用 request 方法
        response = await api_client.request("DELETE", "/users", json=user_ids, headers=auth_headers)

        assert response.status_code == 200

