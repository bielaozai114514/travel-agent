<template>
  <div class="chat-layout">
    <!-- 侧边栏 - 会话列表 -->
    <aside class="sidebar" :class="{ 'collapsed': isSidebarCollapsed }">
      <div class="sidebar-header">
        <div class="logo">
          <el-icon size="24"><Compass /></el-icon>
          <span v-if="!isSidebarCollapsed" class="logo-text">旅游助手</span>
        </div>
        <el-button
          v-if="!isSidebarCollapsed"
          class="collapse-btn"
          text
          @click="toggleSidebar"
        >
          <el-icon><Fold /></el-icon>
        </el-button>
        <el-button
          v-else
          class="collapse-btn"
          text
          @click="toggleSidebar"
        >
          <el-icon><Expand /></el-icon>
        </el-button>
      </div>

      <!-- 新建对话按钮 -->
      <div class="new-chat-wrapper">
        <el-button
          class="new-chat-btn"
          type="primary"
          :class="{ 'collapsed': isSidebarCollapsed }"
          @click="createNewConversation"
        >
          <el-icon><Plus /></el-icon>
          <span v-if="!isSidebarCollapsed">新建对话</span>
        </el-button>
      </div>

      <!-- 会话列表 -->
      <div class="conversation-list" v-if="!isSidebarCollapsed">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conversation-item"
          :class="{ active: currentConversationId === conv.id }"
          @click="selectConversation(conv.id)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span class="conversation-title">{{ conv.title }}</span>
          <el-dropdown trigger="click" @command="handleCommand($event, conv)">
            <el-icon class="more-icon" @click.stop><More /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 底部用户信息 -->
      <div class="sidebar-footer">
        <el-dropdown trigger="click" class="user-dropdown">
          <div class="user-info">
            <el-avatar :size="32" class="user-avatar">
              {{ userInitial }}
            </el-avatar>
            <span v-if="!isSidebarCollapsed" class="username">{{ userStore.userInfo.username }}</span>
            <el-icon v-if="!isSidebarCollapsed" class="arrow-icon"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="isAdmin" @click="goToAdmin">
                <el-icon><Setting /></el-icon>
                <span>管理后台</span>
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                <span>退出登录</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialogVisible"
      title="重命名对话"
      width="400px"
    >
      <el-input
        v-model="newTitle"
        placeholder="请输入新标题"
        maxlength="50"
        show-word-limit
      />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Compass,
  Plus,
  ChatDotRound,
  More,
  Fold,
  Expand,
  ArrowDown,
  Setting,
  SwitchButton
} from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import {
  getConversations,
  createConversation,
  updateConversation,
  deleteConversation
} from '@/api/conversation'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 侧边栏折叠状态
const isSidebarCollapsed = ref(false)

// 会话列表
const conversations = ref([])

// 当前会话ID
const currentConversationId = computed(() => {
  return route.params.conversationId || null
})

// 用户首字母
const userInitial = computed(() => {
  return userStore.userInfo.username?.charAt(0).toUpperCase() || 'U'
})

// 是否为管理员
const isAdmin = computed(() => {
  return userStore.userInfo.roles?.some(role => role.name === 'admin')
})

// 重命名对话框
const renameDialogVisible = ref(false)
const newTitle = ref('')
const renamingConv = ref(null)

// 切换侧边栏
const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

// 获取会话列表
const fetchConversations = async () => {
  try {
    const res = await getConversations()
    conversations.value = res.list || []
  } catch (error) {
    console.error('获取会话列表失败:', error)
  }
}

// 创建新对话
const createNewConversation = async () => {
  try {
    const res = await createConversation()
    await fetchConversations()
    router.push(`/chat/${res.id}`)
  } catch (error) {
    ElMessage.error('创建对话失败')
  }
}

// 选择会话
const selectConversation = (id) => {
  router.push(`/chat/${id}`)
}

// 处理下拉菜单命令
const handleCommand = (command, conv) => {
  if (command === 'rename') {
    renamingConv.value = conv
    newTitle.value = conv.title
    renameDialogVisible.value = true
  } else if (command === 'delete') {
    handleDelete(conv)
  }
}

// 确认重命名
const confirmRename = async () => {
  if (!newTitle.value.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  try {
    await updateConversation(renamingConv.value.id, { title: newTitle.value })
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    await fetchConversations()
  } catch (error) {
    ElMessage.error('重命名失败')
  }
}

// 删除会话
const handleDelete = async (conv) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteConversation(conv.id)
    ElMessage.success('删除成功')
    await fetchConversations()
    // 如果删除的是当前会话，跳转到新对话
    if (currentConversationId.value === conv.id) {
      router.push('/chat')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 跳转到管理后台
const goToAdmin = () => {
  router.push('/admin')
}

// 退出登录
const handleLogout = () => {
  userStore.logout()
  ElMessage.success('退出成功')
  router.push('/login')
}

// 初始化
onMounted(() => {
  fetchConversations()
})

watch(() => route.params.conversationId, (newId, oldId) => {
  if (newId && !oldId) {
    fetchConversations()
  }
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

/* 侧边栏样式 */
.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.sidebar.collapsed {
  width: 64px;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #667eea;
  font-weight: 600;
  font-size: 18px;
}

.collapse-btn {
  padding: 4px;
}

/* 新建对话按钮 */
.new-chat-wrapper {
  padding: 12px 16px;
}

.new-chat-btn {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  background: #409eff;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.new-chat-btn.collapsed {
  width: 40px;
  padding: 0;
}

/* 会话列表 */
.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #606266;
}

.conversation-item:hover {
  background: #f5f7fa;
}

.conversation-item.active {
  background: #eef2ff;
  color: #667eea;
}

.conversation-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.more-icon {
  opacity: 0;
  transition: opacity 0.3s;
}

.conversation-item:hover .more-icon {
  opacity: 1;
}

/* 底部用户信息 */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.user-dropdown {
  width: 100%;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.3s;
}

.user-info:hover {
  background: #f5f7fa;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.username {
  flex: 1;
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  color: #909399;
  font-size: 12px;
}

/* 主内容区 */
.main-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}
</style>
