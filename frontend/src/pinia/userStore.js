/**
 *  这是 Pinia 的用户状态仓库，负责存储用户的权限列表和提供权限检查能力，是整个权限控制的 "数据源"。
 */

import { defineStore } from "pinia";
import { ref } from "vue";
import { login as userLogin, getCurrentUser } from "@/api/user";
import {
  getToken,
  setToken,
  removeToken,
  setScopes,
  getScopes,
} from "@/utils/auth";

export const useUserStore = defineStore("user", () => {
  // 状态
  const token = ref(getToken() || ""); // 用户登录令牌（从本地缓存获取）
  const userInfo = ref({}); // 用户基本信息
  const scopes = ref(getScopes() || []); // 核心：存储用户的权限列表（比如 ['users:write', 'permissions:delete']）

  /**
   * 登录，登录时初始化权限
   * @param {object} loginForm
   */
  const login = async (loginForm) => {
    const res = await userLogin(loginForm);
    token.value = res.access_token;
    setToken(res.access_token);

    // 获取用户信息
    await fetchUserInfo();
  };

  /**
   * 获取当前用户信息
   */
  const fetchUserInfo = async () => {
    try {
      const res = await getCurrentUser();
      userInfo.value = res;
      
      // 从角色中提取权限
      const permissions = [];
      if (res.roles) {
        res.roles.forEach(role => {
          if (role.permissions) {
            role.permissions.forEach(perm => {
              if (!permissions.includes(perm.scope)) {
                permissions.push(perm.scope);
              }
            });
          }
        });
      }
      scopes.value = permissions;
      setScopes(permissions);
      
      return res;
    } catch (error) {
      console.error('获取用户信息失败:', error);
      throw error;
    }
  };

  /**
   * 退出登录
   */
  const logout = () => {
    token.value = "";
    userInfo.value = {};
    scopes.value = [];
    removeToken();
    setScopes([]);
  };

  /**
   * 检查权限
   * @param {string} scope
   */
  const hasPermission = (scope) => {
    return scopes.value.includes(scope);
  };

  /**
   * 检查是否为管理员
   */
  const isAdmin = () => {
    const roles = userInfo.value.roles || [];
    return roles.some(role => role.name === 'admin');
  };

  return {
    token,
    userInfo,
    scopes,
    login,
    logout,
    hasPermission,
    isAdmin,
    fetchUserInfo,
  };
});
