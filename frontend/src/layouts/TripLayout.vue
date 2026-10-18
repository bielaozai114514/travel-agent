<template>
  <div class="trip-layout">
    <el-container>
      <el-aside :width="isSidebarCollapsed ? '90px' : '260px'" class="sidebar">
        <div class="sidebar-header">
          <div class="logo" v-if="!isSidebarCollapsed">
            <el-icon size="24"><Compass /></el-icon>
            <span class="logo-text">旅游助手</span>
          </div>
          <div class="logo-mini" v-else>
            <el-icon size="24"><Compass /></el-icon>
          </div>
          <el-button
            class="collapse-btn"
            text
            @click="toggleSidebar"
          >
            <el-icon><component :is="isSidebarCollapsed ? 'Expand' : 'Fold'" /></el-icon>
          </el-button>
        </div>

        <div class="sidebar-content">
          <el-menu
            :default-active="activeMenu"
            class="sidebar-menu"
            router
          >
            <el-menu-item index="/chat">
              <el-icon><ChatDotRound /></el-icon>
              <span v-if="!isSidebarCollapsed">智能对话</span>
            </el-menu-item>
            <el-menu-item index="/trip">
              <el-icon><MapLocation /></el-icon>
              <span v-if="!isSidebarCollapsed">旅游规划</span>
            </el-menu-item>
            <el-menu-item index="/guides">
              <el-icon><Document /></el-icon>
              <span v-if="!isSidebarCollapsed">旅游攻略</span>
            </el-menu-item>
          </el-menu>

          <div class="list-section" v-if="!isSidebarCollapsed && !isGuideRoute">
            <div class="section-header">
              <span class="section-title">{{ isChatRoute ? '历史会话' : '旅游规划' }}</span>
              <el-button
                type="primary"
                size="small"
                circle
                @click="createNew"
              >
                <el-icon><Plus /></el-icon>
              </el-button>
            </div>
            <div class="list-container">
              <template v-if="isChatRoute">
                <div
                  v-for="conv in conversations"
                  :key="conv.id"
                  class="list-item"
                  :class="{ active: currentConversationId === conv.id }"
                  @click="selectConversation(conv.id)"
                >
                  <el-icon><ChatDotRound /></el-icon>
                  <span class="item-title">{{ conv.title }}</span>
                  <el-dropdown trigger="click" @command="handleConvCommand($event, conv)">
                    <el-icon class="more-icon" @click.stop><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="rename">
                          <el-icon><Edit /></el-icon>
                          重命名
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <el-empty v-if="conversations.length === 0" description="暂无会话记录" :image-size="60" />
              </template>
              <template v-else>
                <div
                  v-for="item in allTripItems"
                  :key="item.type + '-' + item.id"
                  class="list-item"
                  :class="{
                    active: !item.is_running && currentTripPlanId === item.id,
                    'is-running': item.is_running
                  }"
                  @click="selectTripPlan(item.id, item.is_running)"
                >
                  <el-icon v-if="!item.is_running"><MapLocation /></el-icon>
                  <el-icon v-else class="loading-icon"><Loading /></el-icon>
                  <div class="item-info">
                    <span class="item-title">
                      {{ item.title }}
                      <span v-if="item.is_running" class="running-badge">规划中...</span>
                    </span>
                    <span class="item-date">
                      {{ item.start_date && item.end_date ? `${item.start_date} ~ ${item.end_date}` : '' }}
                    </span>
                    <!-- 规划中显示进度 -->
                    <div v-if="item.is_running" class="task-progress">
                      <el-progress
                        :percentage="item.step_progress"
                        :stroke-width="6"
                        :show-text="false"
                      />
                      <span class="step-text">{{ item.current_step }}</span>
                    </div>
                  </div>
                  <el-dropdown v-if="!item.is_running" trigger="click" @command="handlePlanCommand($event, item)">
                    <el-icon class="more-icon" @click.stop><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <el-empty v-if="allTripItems.length === 0" description="暂无旅游规划" :image-size="60" />
              </template>
            </div>
          </div>

          <!-- <el-menu
            v-if="isSidebarCollapsed"
            :default-active="activeMenu"
            class="sidebar-menu"
            router
          >
            <el-menu-item index="/trip" v-if="isChatRoute">
              <el-icon><MapLocation /></el-icon>
            </el-menu-item>
            <el-menu-item index="/chat" v-else>
              <el-icon><ChatDotRound /></el-icon>
            </el-menu-item>
          </el-menu> -->
        </div>

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
      </el-aside>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Compass,
  MapLocation,
  ChatDotRound,
  Document,
  ArrowDown,
  Setting,
  SwitchButton,
  Plus,
  MoreFilled,
  Edit,
  Delete,
  Fold,
  Expand,
  Loading
} from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import {
  getConversations,
  createConversation,
  updateConversation,
  deleteConversation
} from '@/api/conversation'
import { getTripPlans, deleteTripPlan } from '@/api/trip'
import { getUserTasks } from '@/api/task'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isSidebarCollapsed = ref(false)
const conversations = ref([])
const tripPlans = ref([])
const runningTasks = ref([])  // 规划中的任务
const renameDialogVisible = ref(false)
const newTitle = ref('')
const renamingConv = ref(null)
let taskPollingTimer = null

const isChatRoute = computed(() => {
  return route.path.startsWith('/chat')
})

const isTripRoute = computed(() => {
  return route.path.startsWith('/trip')
})

const isGuideRoute = computed(() => {
  return route.path.startsWith('/guide') || route.path.startsWith('/guides')
})

const activeMenu = computed(() => {
  if (isChatRoute.value) return '/chat'
  if (isGuideRoute.value) return '/guides'
  return '/trip'
})

const currentConversationId = computed(() => {
  const id = route.params.conversationId
  return id || null
})

const currentTripPlanId = computed(() => {
  const id = route.params.id
  return id || null
})

const userInitial = computed(() => {
  return userStore.userInfo.username?.charAt(0).toUpperCase() || 'U'
})

const isAdmin = computed(() => {
  return userStore.userInfo.roles?.some(role => role.name === 'admin')
})

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const fetchConversations = async () => {
  try {
    const res = await getConversations()
    conversations.value = res.list || []
  } catch (error) {
    console.error('获取会话列表失败:', error)
  }
}

const fetchTripPlans = async () => {
  try {
    const res = await getTripPlans()
    if (res.success && res.data) {
      tripPlans.value = res.data.list || []
    }
  } catch (error) {
    console.error('获取旅游规划列表失败:', error)
  }
}

const fetchRunningTasks = async () => {
  try {
    const res = await getUserTasks({ task_type: 'trip_plan' })
    if (res.success && res.data) {
      // 只显示运行中的任务
      runningTasks.value = (res.data.list || []).filter(task =>
        ['pending', 'running'].includes(task.status)
      )
    }
  } catch (error) {
    console.error('获取运行中任务失败:', error)
  }
}

const startTaskPolling = () => {
  stopTaskPolling()
  taskPollingTimer = setInterval(() => {
    if (isTripRoute.value) {
      fetchRunningTasks()
    }
  }, 5000)
}

const stopTaskPolling = () => {
  if (taskPollingTimer) {
    clearInterval(taskPollingTimer)
    taskPollingTimer = null
  }
}

// 合并行程列表和运行中的任务
const allTripItems = computed(() => {
  const items = []

  // 先添加运行中的任务
  runningTasks.value.forEach(task => {
    items.push({
      type: 'task',
      id: task.id,
      task_id: task.id,
      title: `${task.input_data?.city || '未知城市'}行程`,
      start_date: task.input_data?.start_date || '',
      end_date: task.input_data?.end_date || '',
      status: task.status,
      current_step: task.current_step,
      step_progress: task.step_progress,
      is_running: true
    })
  })

  // 再添加已完成的行程
  tripPlans.value.forEach(plan => {
    items.push({
      type: 'plan',
      id: plan.id,
      title: plan.title,
      start_date: plan.start_date,
      end_date: plan.end_date,
      is_running: false
    })
  })

  return items
})

const createNew = () => {
  if (isChatRoute.value) {
    createNewConversation()
  } else if (isGuideRoute.value) {
    router.push('/guide/create')
  } else {
    router.push('/trip')
  }
}

const createNewConversation = async () => {
  try {
    const res = await createConversation()
    await fetchConversations()
    router.push(`/chat/${res.id}`)
  } catch (error) {
    ElMessage.error('创建对话失败')
  }
}

const selectConversation = (id) => {
  router.push(`/chat/${id}`)
}

const selectTripPlan = (id, isTask = false) => {
  if (isTask) {
    // 点击规划中的任务，提示用户
    ElMessage.info('行程正在规划中，请稍候...')
  } else {
    router.push(`/trip/result/${id}`)
  }
}

const handleConvCommand = (command, conv) => {
  if (command === 'rename') {
    renamingConv.value = conv
    newTitle.value = conv.title
    renameDialogVisible.value = true
  } else if (command === 'delete') {
    handleDeleteConversation(conv)
  }
}

const handlePlanCommand = (command, plan) => {
  if (command === 'delete') {
    handleDeleteTripPlan(plan)
  }
}

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

const handleDeleteConversation = async (conv) => {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteConversation(conv.id)
    ElMessage.success('删除成功')
    await fetchConversations()
    if (currentConversationId.value === conv.id) {
      router.push('/chat')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleDeleteTripPlan = async (plan) => {
  try {
    await ElMessageBox.confirm('确定要删除这个旅游规划吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteTripPlan(plan.id)
    ElMessage.success('删除成功')
    await fetchTripPlans()
    if (currentTripPlanId.value === plan.id) {
      router.push('/trip')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const goToAdmin = () => {
  router.push('/admin')
}

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('退出成功')
  router.push('/login')
}

watch(() => route.path, (newPath) => {
  if (newPath.startsWith('/chat')) {
    fetchConversations()
    stopTaskPolling()
  } else if (newPath.startsWith('/trip')) {
    fetchTripPlans()
    fetchRunningTasks()
    startTaskPolling()
  } else {
    stopTaskPolling()
  }
}, { immediate: true })

onMounted(() => {
  if (isChatRoute.value) {
    fetchConversations()
  } else if (isTripRoute.value) {
    fetchTripPlans()
    fetchRunningTasks()
    startTaskPolling()
  }
  // 攻略页面不加载列表
})

onUnmounted(() => {
  stopTaskPolling()
})
</script>

<style scoped>
.trip-layout {
  height: 100vh;
  background: #f5f7fa;
}

.el-container {
  height: 100%;
}

.sidebar {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
  transition: width 0.3s ease;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  min-height: 60px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #667eea;
  font-weight: 600;
  font-size: 18px;
}

.logo-mini {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

.logo-text {
  color: #409eff;
}

.collapse-btn {
  padding: 8px;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.sidebar-menu {
  border-right: none;
  padding: 12px;
}

.sidebar-menu :deep(.el-menu-item) {
  margin-bottom: 8px;
  border-radius: 8px;
  height: 48px;
  line-height: 48px;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: #ecf5ff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: #409eff;
  color: #fff;
}

.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
}

.list-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px;
  border-top: 1px solid #e4e7ed;
  margin-top: 8px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
}

.list-container {
  flex: 1;
  overflow-y: auto;
}

.list-item {
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

.list-item:hover {
  background: #f5f7fa;
}

.list-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.list-item.is-running {
  background: #fdf6ec;
}

.list-item.is-running .loading-icon {
  color: #e6a23c;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.running-badge {
  margin-left: 8px;
  padding: 2px 8px;
  background: #e6a23c;
  color: white;
  font-size: 10px;
  border-radius: 4px;
}

.task-progress {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-progress .step-text {
  font-size: 11px;
  color: #909399;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.item-date {
  font-size: 12px;
  color: #909399;
}

.more-icon {
  opacity: 0;
  transition: opacity 0.3s;
  color: #909399;
}

.list-item:hover .more-icon {
  opacity: 1;
}

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
  padding: 8px 12px;
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
  flex-shrink: 0;
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

.main-content {
  padding: 0;
  background: #f5f7fa;
  overflow-y: auto;
  height: 100%;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    height: 100%;
    z-index: 1000;
  }
  
  .main-content {
    margin-left: 0;
  }
}
</style>
