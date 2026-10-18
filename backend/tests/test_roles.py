
"""
角色接口测试
"""
import pytest
from faker import Faker

fake = Faker("zh_CN")


@pytest.mark.integration
@pytest.mark.asyncio
class TestRoleEndpoints:
    """角色接口测试"""

    async def test_get_role_list(self, api_client, auth_headers):
        """测试获取角色列表"""
        response = await api_client.get("/roles", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "list" in data["data"]

    async def test_get_role_list_unauthorized(self, api_client):
        """测试未登录获取角色列表"""
        response = await api_client.get("/roles")

        assert response.status_code == 401

    async def test_create_role(self, api_client, auth_headers):
        """测试创建角色"""
        unique_name = f"test_role_{fake.unique.user_name()}"
        role_data = {
            "name": unique_name,
            "description": "测试角色",
        }
        response = await api_client.post("/roles", json=role_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == unique_name

    async def test_get_role_by_id(self, api_client, auth_headers):
        """测试通过ID获取角色"""
        # 先创建角色
        unique_name = f"test_getrole_{fake.unique.user_name()}"
        role_data = {"name": unique_name, "description": "测试"}
        create_response = await api_client.post("/roles", json=role_data, headers=auth_headers)
        role_id = create_response.json()["data"]["id"]

        # 获取角色
        response = await api_client.get(f"/roles/{role_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == role_id

    async def test_get_role_by_name(self, api_client, auth_headers):
        """测试通过名称获取角色"""
        # 先创建角色
        unique_name = f"test_getbyname_{fake.unique.user_name()}"
        role_data = {"name": unique_name, "description": "测试"}
        await api_client.post("/roles", json=role_data, headers=auth_headers)

        # 获取角色
        response = await api_client.get(f"/roles/name/{unique_name}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == unique_name

    async def test_update_role(self, api_client, auth_headers):
        """测试更新角色"""
        # 先创建角色
        unique_name = f"test_updaterole_{fake.unique.user_name()}"
        role_data = {"name": unique_name, "description": "原始描述"}
        create_response = await api_client.post("/roles", json=role_data, headers=auth_headers)
        role_id = create_response.json()["data"]["id"]

        # 更新角色
        update_data = {
            "name": f"{unique_name}_updated",
            "description": "更新后的描述",
        }
        response = await api_client.put(f"/roles/{role_id}", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == f"{unique_name}_updated"

    async def test_delete_role(self, api_client, auth_headers):
        """测试删除角色"""
        # 先创建角色
        unique_name = f"test_deleterole_{fake.unique.user_name()}"
        role_data = {"name": unique_name, "description": "测试"}
        create_response = await api_client.post("/roles", json=role_data, headers=auth_headers)
        role_id = create_response.json()["data"]["id"]

        # 删除角色
        response = await api_client.delete(f"/roles/{role_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_batch_delete_roles(self, api_client, auth_headers):
        """测试批量删除角色"""
        # 创建多个角色
        role_ids = []
        for i in range(3):
            unique_name = f"test_batchrole_{fake.unique.user_name()}"
            role_data = {"name": unique_name, "description": "测试"}
            create_response = await api_client.post("/roles", json=role_data, headers=auth_headers)
            role_ids.append(create_response.json()["data"]["id"])

        # 批量删除 - 使用 request 方法
        response = await api_client.request("DELETE", "/roles", json=role_ids, headers=auth_headers)

        assert response.status_code == 200

