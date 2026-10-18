
"""
权限接口测试
"""
import pytest
from faker import Faker

fake = Faker("zh_CN")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPermissionEndpoints:
    """权限接口测试"""

    async def test_get_permission_list(self, api_client, auth_headers):
        """测试获取权限列表"""
        response = await api_client.get("/permissions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_get_permission_list_unauthorized(self, api_client):
        """测试未登录获取权限列表"""
        response = await api_client.get("/permissions")

        assert response.status_code == 401

    async def test_create_permission(self, api_client, auth_headers):
        """测试创建权限"""
        unique_scope = f"test:{fake.unique.uuid4()}"
        unique_desc = f"测试权限:{fake.unique.uuid4()}"
        permission_data = {
            "scope": unique_scope,
            "description": unique_desc,
        }
        response = await api_client.post("/permissions", json=permission_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    async def test_get_permission_by_id(self, api_client, auth_headers):
        """测试通过ID获取权限"""
        # 先创建权限
        unique_scope = f"test:getid:{fake.unique.uuid4()}"
        unique_desc = f"获取测试:{fake.unique.uuid4()}"
        create_data = {"scope": unique_scope, "description": unique_desc}
        create_resp = await api_client.post("/permissions", json=create_data, headers=auth_headers)
        perm_id = create_resp.json()["data"]["id"]

        # 获取权限
        response = await api_client.get(f"/permissions/{perm_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_update_permission(self, api_client, auth_headers):
        """测试更新权限"""
        # 先创建权限
        unique_scope = f"test:update:{fake.unique.uuid4()}"
        unique_desc = f"原始描述:{fake.unique.uuid4()}"
        create_data = {"scope": unique_scope, "description": unique_desc}
        create_resp = await api_client.post("/permissions", json=create_data, headers=auth_headers)
        perm_id = create_resp.json()["data"]["id"]

        # 更新权限 - 只改描述，scope 不能改
        new_desc = f"更新后的描述:{fake.unique.uuid4()}"
        update_data = {
            "description": new_desc,
        }
        response = await api_client.put(f"/permissions/{perm_id}", json=update_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_delete_permission(self, api_client, auth_headers):
        """测试删除权限"""
        # 先创建权限
        unique_scope = f"test:delete:{fake.unique.uuid4()}"
        unique_desc = f"删除测试:{fake.unique.uuid4()}"
        create_data = {"scope": unique_scope, "description": unique_desc}
        create_resp = await api_client.post("/permissions", json=create_data, headers=auth_headers)
        perm_id = create_resp.json()["data"]["id"]

        # 删除权限
        response = await api_client.delete(f"/permissions/{perm_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_batch_delete_permissions(self, api_client, auth_headers):
        """测试批量删除权限"""
        # 创建多个权限
        perm_ids = []
        for i in range(2):
            unique_scope = f"test:batch:{fake.unique.uuid4()}"
            unique_desc = f"批量测试{i}:{fake.unique.uuid4()}"
            create_data = {"scope": unique_scope, "description": unique_desc}
            create_resp = await api_client.post("/permissions", json=create_data, headers=auth_headers)
            perm_ids.append(create_resp.json()["data"]["id"])

        # 批量删除
        response = await api_client.request("DELETE", "/permissions", json=perm_ids, headers=auth_headers)

        assert response.status_code == 200

