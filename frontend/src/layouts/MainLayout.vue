<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="sidebar">
      <div class="logo-container">
        <div class="logo-icon">
          <el-icon size="28"><Setting /></el-icon>
        </div>
        <h2 class="logo-text">后台管理系统</h2>
      </div>
      <el-menu
        class="sidebar-menu"
        background-color="transparent"
        text-color="#b8c5d6"
        active-text-color="#fff"
        router
      >
        <el-menu-item index="/admin/users" class="menu-item">
          <el-icon><User /></el-icon>
          <template #title>
            <span class="menu-title">用户管理</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/roles" class="menu-item">
          <el-icon><UserFilled /></el-icon>
          <template #title>
            <span class="menu-title">角色管理</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/permissions" class="menu-item">
          <el-icon><Key /></el-icon>
          <template #title>
            <span class="menu-title">权限管理</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/guides" class="menu-item">
          <el-icon><Document /></el-icon>
          <template #title>
            <span class="menu-title">攻略管理</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/traces" class="menu-item">
          <el-icon><View /></el-icon>
          <template #title>
            <span class="menu-title">Trace 追踪</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/admin/logs" class="menu-item">
          <el-icon><Monitor /></el-icon>
          <template #title>
            <span class="menu-title">日志查看</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/chat" class="menu-item">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>
            <span class="menu-title">旅游助手</span>
          </template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <span class="welcome-text">欢迎回来，{{ userStore.userInfo.username || '管理员' }}</span>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" class="user-dropdown">
            <div class="user-info">
              <el-avatar :size="32" class="user-avatar">
                {{ (userStore.userInfo.username || 'A').charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ userStore.userInfo.username || '管理员' }}</span>
              <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu class="user-dropdown-menu">
                <el-dropdown-item @click="handleLogout" class="logout-item">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区域 -->
      <el-main class="main-content">
        <div class="content-wrapper">
          <router-view />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { User, UserFilled, Key, Setting, ArrowDown, SwitchButton, Document, ChatDotRound, View, Monitor } from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const router = useRouter()

/**
 * 退出登录
 */
const handleLogout = () => {
  userStore.logout()
  ElMessage.success('退出成功')
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
  background: #f0f2f5;
}

/* 侧边栏样式 */
.sidebar {
  background: #304156;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 10;
}

.logo-container {
  padding: 24px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: #409eff;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.logo-text {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  letter-spacing: 0.5px;
}

.sidebar-menu {
  border: none;
  padding: 16px 12px;
}

.menu-item {
  margin: 8px 0;
  border-radius: 8px;
  height: 48px;
  line-height: 48px;
  transition: all 0.3s ease;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.1) !important;
}

.menu-item.is-active {
  background: #409eff !important;
}

.menu-title {
  font-size: 14px;
  font-weight: 500;
  margin-left: 8px;
}

/* 主容器样式 */
.main-container {
  background: #f0f2f5;
}

/* 顶部导航样式 */
.header {
  background: #fff;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.welcome-text {
  font-size: 16px;
  color: #606266;
  font-weight: 500;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 8px;
  transition: background 0.3s ease;
}

.user-info:hover {
  background: #f5f7fa;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.username {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.dropdown-icon {
  color: #909399;
  font-size: 12px;
}

/* 内容区域样式 */
.main-content {
  padding: 20px;
  overflow-y: auto;
}

.content-wrapper {
  background: #fff;
  border-radius: 12px;
  min-height: calc(100vh - 104px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

/* 下拉菜单样式 */
:deep(.user-dropdown-menu) {
  padding: 6px;
}

:deep(.logout-item) {
  padding: 10px 16px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f56c6c;
}

:deep(.logout-item:hover) {
  background: #fef0f0;
}
</style>
