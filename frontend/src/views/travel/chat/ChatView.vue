<template>
  <div class="chat-view">
    <div class="chat-main" :class="{ 'with-sidebar': showTripSidebar && !sidebarHidden }">
      <!-- 显示侧边栏按钮（当侧边栏隐藏时显示） -->
      <div v-if="showTripSidebar && sidebarHidden" class="show-sidebar-btn" @click="toggleSidebar">
        <el-icon><ArrowRight /></el-icon>
      </div>

      <!-- 消息列表区域 -->
      <div class="messages-container" ref="messagesContainer" @click="handleGuideLinkClick">
        <!-- 欢迎界面 -->
        <div v-if="messages.length === 0" class="welcome-section">
          <div class="welcome-content">
            <div class="welcome-icon">
              <el-icon size="64"><Compass /></el-icon>
            </div>
            <h1 class="welcome-title">旅游助手</h1>
            <p class="welcome-subtitle">您的智能旅游规划专家</p>
            <!-- <div class="quick-actions">
              <div
                v-for="(action, index) in quickActions"
                :key="index"
                class="action-card"
                @click="sendQuickMessage(action.prompt)"
              >
                <el-icon size="24"><component :is="action.icon" /></el-icon>
                <span>{{ action.title }}</span>
              </div>
            </div> -->
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages-list">
          <div
            v-for="(message, index) in messages"
            :key="index"
            class="message-item"
            :class="message.role"
          >
            <div class="message-avatar">
              <el-avatar
                v-if="message.role === 'user'"
                :size="36"
                class="user-avatar"
              >
                {{ userInitial }}
              </el-avatar>
              <div v-else class="ai-avatar">
                <el-icon size="24"><Compass /></el-icon>
              </div>
            </div>
            <div class="message-content">
              <div class="message-header">
                <span class="message-role">
                  {{ message.role === 'user' ? '我' : '旅游助手' }}
                </span>
                <span class="message-time">{{ formatTime(message.created_at) }}</span>
              </div>

              <div class="message-body">
                <template v-if="message.role === 'assistant'">
                  <div
                    v-if="message.thinking && message.thinking.length > 0"
                    class="thinking-section"
                  >
                    <div
                      class="thinking-toggle"
                      @click="toggleThinking(index)"
                    >
                      <el-icon :class="{ 'rotate': thinkingExpanded[index] }">
                        <ArrowDown />
                      </el-icon>
                      <span>思考过程</span>
                      <span v-if="streamingMessageIndex === index && !message.content" class="thinking-status">
                        (思考中...)
                      </span>
                    </div>
                    <div
                      v-show="thinkingExpanded[index] || streamingMessageIndex === index"
                      class="thinking-content"
                    >
                      <div
                        v-for="(step, stepIndex) in message.thinking"
                        :key="stepIndex"
                        class="thinking-step"
                        :class="step.type"
                      >
                        <div v-if="step.type === 'thinking'">
                          <div class="step-label">🤔 思考中...</div>
                          <div class="step-content">{{ step.content }}</div>
                        </div>
                        <div v-else-if="step.type === 'tool_call'">
                          <div class="step-label">🔧 调用工具: {{ step.tool_name }}</div>
                          <div v-if="step.parameters" class="step-params">参数: {{ step.parameters }}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-if="message.content" class="markdown-body" v-html="renderMarkdown(message.content)"></div>
                  <div v-else-if="streamingMessageIndex === index && (!message.thinking || message.thinking.length === 0)" class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </template>
                <div v-else class="text-content">{{ message.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-section">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 6 }"
            placeholder="输入您的问题，按 Enter 发送，Shift + Enter 换行..."
            class="chat-input"
            @keydown="handleKeydown"
          />
          <div class="input-actions">
            <el-button
              type="primary"
              class="send-btn"
              :loading="isLoading"
              :disabled="!inputMessage.trim()"
              @click="sendMessage"
            >
              <el-icon v-if="!isLoading"><Promotion /></el-icon>
              <span v-else>发送中</span>
            </el-button>
          </div>
        </div>
        <div class="input-footer">
          <span class="hint">按 Enter 发送，Shift + Enter 换行</span>
        </div>
      </div>
    </div>

    <!-- 行程侧边栏 -->
    <div v-if="showTripSidebar && !sidebarHidden" class="trip-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">行程信息</span>
        <div class="header-actions">
          <el-button link type="primary" @click="viewFullTrip">
            查看完整行程
          </el-button>
          <el-button link class="close-btn" @click="toggleSidebar">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="sidebar-content">
        <!-- 规划中状态 -->
        <div v-if="currentTask && currentTask.status !== 'completed'" class="planning-section">
          <div class="planning-status">
            <el-icon class="loading-icon"><Loading /></el-icon>
            <span class="status-text">{{ currentTask.current_step || '规划中...' }}</span>
          </div>
          <el-progress
            :percentage="currentTask.step_progress"
            :status="currentTask.status === 'failed' ? 'exception' : undefined"
          />
          <div class="step-info">
            步骤 {{ Math.min(currentTask.step_progress ? Math.ceil(currentTask.step_progress / 12.5) : 1, 8) }} / 8
          </div>
        </div>

        <!-- 行程摘要（规划完成后显示） -->
        <div v-else-if="currentTrip" class="trip-summary">
          <el-card class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Location /></el-icon>
                <span>{{ currentTrip.city }}行程</span>
              </div>
            </template>
            <div class="summary-info">
              <div class="info-row">
                <span class="label">日期:</span>
                <span class="value">{{ currentTrip.start_date }} 至 {{ currentTrip.end_date }}</span>
              </div>
              <div class="info-row">
                <span class="label">天数:</span>
                <span class="value">{{ currentTrip.travel_days || currentTrip.days?.length || 0 }}天</span>
              </div>
              <div v-if="currentTrip.budget" class="info-row">
                <span class="label">预算:</span>
                <span class="value">¥{{ currentTrip.budget.total }}</span>
              </div>
            </div>
          </el-card>

          <!-- 每日行程摘要 -->
          <div v-if="currentTrip.days && currentTrip.days.length > 0" class="days-summary">
            <div class="days-title">每日行程</div>
            <div
              v-for="(day, index) in currentTrip.days.slice(0, 5)"
              :key="index"
              class="day-item"
            >
              <div class="day-num">第{{ day.day_index + 1}}天</div>
              <div class="day-attractions">
                {{ day.attractions?.slice(0, 3).map(a => a.name).join(' → ') || '暂无安排' }}
              </div>
            </div>
            <div v-if="currentTrip.days.length > 5" class="more-days">
              还有 {{ currentTrip.days.length - 5 }} 天...
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else class="empty-state">
          <el-icon size="48"><Document /></el-icon>
          <p>暂无关联行程</p>
          <p class="hint">说"帮我规划一个行程"试试</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Compass,
  Promotion,
  MapLocation,
  Food,
  Calendar,
  InfoFilled,
  ArrowDown,
  ArrowRight,
  Close,
  Location,
  Document,
  Loading
} from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import { getConversationDetail, getMessages, sendMessageStream } from '@/api/conversation'
import { getTripPlanById } from '@/api/trip'
import { getTaskDetail } from '@/api/task'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 消息列表
const messages = ref([])

// 每个消息的思考过程展开状态
const thinkingExpanded = ref({})

// 输入消息
const inputMessage = ref('')

// 加载状态
const isLoading = ref(false)

// 当前正在流式输出的消息索引
const streamingMessageIndex = ref(-1)

// 消息容器引用
const messagesContainer = ref(null)

// 当前会话ID（使用ref独立存储，不依赖computed）
const currentConversationId = ref(null)

// 从路由获取会话ID
const routeConversationId = computed(() => route.params.conversationId)

// 当前关联的行程
const currentTrip = ref(null)
const currentTripId = ref(null)
const currentTask = ref(null)

// 轮询定时器
let taskPollingTimer = null

// 是否正在发送/接收流式消息的标志
let isStreamingActive = false

// 侧边栏是否被手动隐藏
const sidebarHidden = ref(false)

// 是否显示侧边栏：有行程 或 有进行中的任务
const showTripSidebar = computed(() => {
  const hasTrip = currentTrip.value !== null
  const hasActiveTask = currentTask.value !== null &&
    !['completed', 'failed', 'cancelled'].includes(currentTask.value.status)
  return hasTrip || hasActiveTask
})

// 切换侧边栏显示/隐藏
const toggleSidebar = () => {
  sidebarHidden.value = !sidebarHidden.value
}

// 用户首字母
const userInitial = computed(() => {
  return userStore.userInfo.username?.charAt(0).toUpperCase() || 'U'
})

// 解析思考过程
const parseThinkingProcess = (content) => {
  if (!content) return []

  const process = []
  const toolCallRegex = /\[TOOL_CALL:([^\]]+)\]/g
  let match

  // 提取所有工具调用
  while ((match = toolCallRegex.exec(content)) !== null) {
    const fullCall = match[0]
    const toolInfo = match[1]
    const colonIndex = toolInfo.indexOf(':')

    let toolName, toolParams
    if (colonIndex !== -1) {
      toolName = toolInfo.substring(0, colonIndex)
      toolParams = toolInfo.substring(colonIndex + 1)
    } else {
      toolName = toolInfo
      toolParams = ''
    }

    process.push({
      type: 'tool_call',
      toolName: toolName,
      toolParams: toolParams,
      fullCall: fullCall
    })
  }

  return process
}

// 清理最终内容（移除工具调用标记）
const cleanFinalContent = (content) => {
  if (!content) return ''
  return content.replace(/\[TOOL_CALL:[^\]]+\]/g, '').trim()
}

// 切换思考过程展开状态
const toggleThinking = (index) => {
  thinkingExpanded.value[index] = !thinkingExpanded.value[index]
}

// 快捷操作
const quickActions = [
  {
    icon: 'MapLocation',
    title: '推荐景点',
    prompt: '请为我推荐一些热门的旅游景点'
  },
  {
    icon: 'Food',
    title: '美食推荐',
    prompt: '推荐一些当地特色美食'
  },
  {
    icon: 'Calendar',
    title: '行程规划',
    prompt: '帮我规划一个3天的旅游行程'
  },
  {
    icon: 'InfoFilled',
    title: '旅游攻略',
    prompt: '给我一些旅游注意事项和建议'
  }
]

// 配置 marked
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (e) {
        // ignore
      }
    }
    try {
      return hljs.highlightAuto(code).value
    } catch (e) {
      // ignore
    }
    return ''
  },
  breaks: true,
  gfm: true
})

// 渲染Markdown
const renderMarkdown = (content) => {
  if (!content) return ''
  const rawHtml = marked(content)
  return DOMPurify.sanitize(rawHtml)
}

// 处理攻略链接点击
const handleGuideLinkClick = (event) => {
  const target = event.target
  if (target.tagName === 'A' && target.getAttribute('href')) {
    const href = target.getAttribute('href')
    if (href.startsWith('guide://')) {
      event.preventDefault()
      const guideId = href.replace('guide://', '')
      if (guideId) {
        router.push(`/guide/${guideId}`)
      }
    }
  }
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 获取会话消息
const fetchMessages = async () => {
  if (!currentConversationId.value) {
    messages.value = []
    return
  }

  try {
    const res = await getMessages(currentConversationId.value)
    messages.value = res || []
    scrollToBottom()
  } catch (error) {
    console.error('获取消息失败:', error)
    ElMessage.error('获取消息失败')
  }
}

// 加载会话详情和关联行程
const loadConversationAndTrip = async () => {
  if (!currentConversationId.value) {
    currentTrip.value = null
    currentTripId.value = null
    currentTask.value = null
    return
  }

  try {
    const res = await getConversationDetail(currentConversationId.value)
    if (res.success && res.data) {
      const conversation = res.data
      if (conversation.current_trip_id) {
        // 加载关联的行程
        await loadTrip(conversation.current_trip_id)
      } else {
        currentTrip.value = null
        currentTripId.value = null
      }
    }
  } catch (error) {
    console.error('加载会话详情失败:', error)
  }
}

// 加载行程
const loadTrip = async (tripId) => {
  try {
    const response = await getTripPlanById(tripId)
    if (response.success && response.data) {
      // 确保 days 数组按 day_index 排序
      if (response.data.days && Array.isArray(response.data.days)) {
        response.data.days.sort((a, b) => a.day_index - b.day_index)
      }
      currentTripId.value = tripId
      currentTrip.value = response.data
    }
  } catch (error) {
    console.error('加载行程失败:', error)
  }
}

// 轮询任务状态
const pollTaskStatus = async (taskId) => {
  try {
    const response = await getTaskDetail(taskId)
    if (response.success && response.data) {
      currentTask.value = response.data

      // 如果任务完成，加载行程
      if (response.data.status === 'completed' && response.data.output_data?.trip_id) {
        await loadTrip(response.data.output_data.trip_id)
        // 任务完成，停止轮询
        stopTaskPolling()
      } else if (response.data.status === 'failed' || response.data.status === 'cancelled') {
        // 任务失败或取消，停止轮询
        stopTaskPolling()
      }
    }
  } catch (error) {
    console.error('轮询任务状态失败:', error)
  }
}

// 开始任务轮询
const startTaskPolling = (taskId) => {
  stopTaskPolling()
  taskPollingTimer = setInterval(() => {
    pollTaskStatus(taskId)
  }, 2000)
  // 立即执行一次
  pollTaskStatus(taskId)
}

// 停止任务轮询
const stopTaskPolling = () => {
  if (taskPollingTimer) {
    clearInterval(taskPollingTimer)
    taskPollingTimer = null
  }
}

// 查看完整行程
const viewFullTrip = () => {
  if (currentTripId.value) {
    router.push(`/trip/result/${currentTripId.value}`)
  } else if (currentTask.value) {
    ElMessage.info('行程正在规划中，请稍候...')
  }
}

// 处理键盘事件
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 发送快捷消息
const sendQuickMessage = (prompt) => {
  inputMessage.value = prompt
  sendMessage()
}

// 发送消息
const sendMessage = async () => {
  console.log('开始发送消息:', { content: inputMessage.value, conversationId: currentConversationId.value })
  const content = inputMessage.value.trim()
  if (!content || isLoading.value) return

  // 设置流式传输标志
  isStreamingActive = true

  // 添加用户消息到列表
  const userMessage = {
    role: 'user',
    content: content,
    created_at: new Date().toISOString()
  }
  messages.value.push(userMessage)

  // 清空输入框
  inputMessage.value = ''

  // 设置加载状态
  isLoading.value = true
  scrollToBottom()

  try {
    console.log('调用 sendMessageStream API')
    // 使用新的流式API
    const reader = await sendMessageStream({
      conversationId: currentConversationId.value,
      content: content
    })
    console.log('获取到 reader:', reader)

    let assistantMessage = {
      role: 'assistant',
      content: '',
      thinking: [],
      created_at: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

    const messageIndex = messages.value.length - 1
    streamingMessageIndex.value = messageIndex

    const decoder = new TextDecoder()
    let buffer = ''
    let currentThinking = null
    let currentToolCall = null
    let receivedTaskId = null

    // 读取流数据
    const readStream = async () => {
      const { done, value } = await reader.read()
      if (done) {
        // 处理剩余的数据
        if (buffer.trim()) {
          try {
            const data = JSON.parse(buffer)
            if (data.type === 'error') {
              ElMessage.error(data.data || '发送消息失败')
            }
          } catch (error) {
            console.error('解析剩余数据失败:', error)
          }
        }
        isLoading.value = false
        isStreamingActive = false
        return
      }

      // 解码数据
      buffer += decoder.decode(value, { stream: true })

      // 处理缓冲区中的完整行
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的最后一行

      for (const line of lines) {
        if (!line.trim()) continue

        try {
          const data = JSON.parse(line)
          console.log('收到消息:', data)

          if (data.type === 'conversation_id') {
            if (data.data && !currentConversationId.value) {
              currentConversationId.value = data.data
              // 这里不调用 router.replace，避免触发 watch，等 done 之后再处理
              // 或者即使调用了 router.replace，watch 里也会检查 isStreamingActive
              router.replace(`/chat/${data.data}`)
            }
          } else if (data.type === 'user_message') {
            // 用户消息已添加，忽略
          } else if (data.type === 'task_started') {
            // 任务开始，显示规划中状态
            receivedTaskId = data.data.task_id
            currentTask.value = {
              id: receivedTaskId,
              status: 'running',
              current_step: '初始化中...',
              step_progress: 0
            }
            // 开始轮询任务状态
            startTaskPolling(receivedTaskId)
          } else if (data.type === 'content') {
            if (!assistantMessage.content) {
              streamingMessageIndex.value = -1
            }
            assistantMessage.content += data.data
            messages.value = [...messages.value]
            scrollToBottom()
          } else if (data.type === 'thinking_start') {
            currentThinking = {
              type: 'thinking',
              iteration: data.data.iteration,
              content: ''
            }
            assistantMessage.thinking.push(currentThinking)
            messages.value = [...messages.value]
            scrollToBottom()
          } else if (data.type === 'thinking_content') {
            if (currentThinking) {
              currentThinking.content += data.data
              messages.value = [...messages.value]
              scrollToBottom()
            }
          } else if (data.type === 'thinking_end') {
            if (currentThinking) {
              currentThinking = null
              messages.value = [...messages.value]
            }
          } else if (data.type === 'tool_call_start') {
            currentToolCall = {
              type: 'tool_call',
              tool_name: data.data.tool_name,
              parameters: data.data.parameters,
              result: ''
            }
            assistantMessage.thinking.push(currentToolCall)
            messages.value = [...messages.value]
            scrollToBottom()
          } else if (data.type === 'tool_call_end') {
            if (currentToolCall) {
              currentToolCall.result = data.data.result
              currentToolCall = null
              messages.value = [...messages.value]
            }
          } else if (data.type === 'done') {
            isLoading.value = false
            streamingMessageIndex.value = -1

            if (data.data.conversation_id && !currentConversationId.value) {
              currentConversationId.value = data.data.conversation_id
              // 这里也可以更新路由，但要注意 watch 的处理
              router.replace(`/chat/${data.data.conversation_id}`)
            }

            // 加载会话和关联的行程
            if (currentConversationId.value) {
              await loadConversationAndTrip()
            }

            // 流式传输结束
            isStreamingActive = false
          } else if (data.type === 'error') {
            // 错误
            isLoading.value = false
            isStreamingActive = false
            ElMessage.error(data.data || '发送消息失败')
          }
        } catch (error) {
          console.error('解析消息失败:', error, '原始数据:', line)
        }
      }

      // 继续读取
      await readStream()
    }

    // 开始读取流
    await readStream()

  } catch (error) {
    console.error('发送消息失败:', error)
    isLoading.value = false
    isStreamingActive = false
    ElMessage.error(error.message || '发送消息失败')
  }
}

// 监听路由会话ID变化
watch(() => routeConversationId.value, (newId) => {
  // 如果正在流式传输中，不要做任何重置或 fetchMessages 的操作
  if (isStreamingActive) {
    console.log('正在流式传输中，跳过路由变化处理')
    return
  }

  // 如果 newId 和 currentConversationId.value 是同一个，不要做任何操作
  if (newId && newId === currentConversationId.value) {
    console.log('会话ID未变化，跳过处理')
    return
  }

  // 重置侧边栏状态
  sidebarHidden.value = false

  if (newId) {
    currentConversationId.value = newId
    fetchMessages()
    loadConversationAndTrip()
  } else {
    currentConversationId.value = null
    messages.value = []
    currentTrip.value = null
    currentTripId.value = null
    currentTask.value = null
    stopTaskPolling()
  }
}, { immediate: true })

// 组件卸载时清理
onUnmounted(() => {
  stopTaskPolling()
  isStreamingActive = false
})

// 初始化
onMounted(() => {
  if (routeConversationId.value) {
    currentConversationId.value = routeConversationId.value
    fetchMessages()
    loadConversationAndTrip()
  }
})
</script>

<style scoped>
.chat-view {
  display: flex;
  height: 100%;
  background: #f5f7fa;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-main.with-sidebar {
  flex: 0 0 calc(100% - 360px);
}

/* 消息容器 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* 欢迎界面 */
.welcome-section {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.welcome-content {
  text-align: center;
  max-width: 600px;
}

.welcome-icon {
  width: 100px;
  height: 100px;
  background: #409eff;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24px;
  color: #fff;
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
}

.welcome-title {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 8px;
}

.welcome-subtitle {
  font-size: 16px;
  color: #909399;
  margin-bottom: 40px;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.action-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #606266;
}

.action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  color: #667eea;
}

.action-card .el-icon {
  color: #667eea;
}

/* 消息列表 */
.messages-list {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message-item {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.ai-avatar {
  width: 36px;
  height: 36px;
  background: #409eff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.message-content {
  max-width: 70%;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.message-item.user .message-content {
  background: #409eff;
  color: #fff;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.message-role {
  font-weight: 600;
  color: #667eea;
}

.message-item.user .message-role {
  color: #fff;
}

.message-time {
  color: #909399;
  font-size: 12px;
}

.message-item.user .message-time {
  color: rgba(255, 255, 255, 0.8);
}

.message-body {
  line-height: 1.6;
  font-size: 14px;
}

.text-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* Markdown 美化样式 */
.markdown-body {
  color: #24292f;
  line-height: 1.7;
  font-size: 15px;
}

.markdown-body :deep(*) {
  box-sizing: border-box;
}

.markdown-body :deep(h1) {
  font-size: 1.8em;
  font-weight: 700;
  margin: 24px 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid #667eea;
  color: #303133;
}

.markdown-body :deep(h2) {
  font-size: 1.5em;
  font-weight: 700;
  margin: 20px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
  color: #303133;
}

.markdown-body :deep(h3) {
  font-size: 1.25em;
  font-weight: 600;
  margin: 18px 0 12px;
  color: #303133;
}

.markdown-body :deep(h4) {
  font-size: 1.1em;
  font-weight: 600;
  margin: 16px 0 10px;
  color: #606266;
}

.markdown-body :deep(p) {
  margin: 0 0 14px;
  word-wrap: break-word;
}

.markdown-body :deep(a) {
  color: #667eea;
  text-decoration: none;
  transition: color 0.2s;
}

.markdown-body :deep(a:hover) {
  color: #764ba2;
  text-decoration: underline;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 14px;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
  line-height: 1.7;
}

.markdown-body :deep(ul ul),
.markdown-body :deep(ul ol),
.markdown-body :deep(ol ol),
.markdown-body :deep(ol ul) {
  margin: 4px 0 0;
}

.markdown-body :deep(code) {
  background: #f5f7fa;
  color: #e74c3c;
  padding: 3px 8px;
  border-radius: 6px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  font-weight: 500;
}

.markdown-body :deep(pre) {
  background: #282c34;
  padding: 16px 18px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 0 0 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.markdown-body :deep(pre code) {
  background: transparent;
  color: #abb2bf;
  padding: 0;
  border-radius: 0;
  font-size: 0.92em;
  line-height: 1.6;
  font-weight: normal;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid #667eea;
  background: #f8f9ff;
  padding: 14px 18px;
  margin: 0 0 16px;
  border-radius: 0 8px 8px 0;
  color: #606266;
}

.markdown-body :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 16px;
  font-size: 0.95em;
}

.markdown-body :deep(th) {
  background: #409eff;
  color: white;
  font-weight: 600;
  padding: 12px 14px;
  text-align: left;
  border: 1px solid #5a6fd8;
}

.markdown-body :deep(td) {
  padding: 10px 14px;
  border: 1px solid #e4e7ed;
  background: white;
}

.markdown-body :deep(tr:nth-child(even) td) {
  background: #f8f9ff;
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 12px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.markdown-body :deep(hr) {
  border: none;
  height: 3px;
  background: #409eff;
  margin: 24px 0;
  border-radius: 2px;
}

.markdown-body :deep(input[type="checkbox"]) {
  margin-right: 8px;
  accent-color: #667eea;
}

.markdown-body :deep(del) {
  color: #909399;
  text-decoration: line-through;
}

.markdown-body :deep(sup) {
  font-size: 0.75em;
  vertical-align: super;
  line-height: 0;
}

.markdown-body :deep(sub) {
  font-size: 0.75em;
  vertical-align: sub;
  line-height: 0;
}

/* 代码高亮主题微调 */
.markdown-body :deep(.hljs-keyword) {
  color: #c678dd;
}

.markdown-body :deep(.hljs-string) {
  color: #98c379;
}

.markdown-body :deep(.hljs-number) {
  color: #d19a66;
}

.markdown-body :deep(.hljs-function) {
  color: #61afef;
}

.markdown-body :deep(.hljs-comment) {
  color: #5c6370;
  font-style: italic;
}

/* 正在输入指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 输入区域 */
.input-section {
  background: #fff;
  border-top: 1px solid #e4e7ed;
  padding: 20px;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: #f5f7fa;
  border-radius: 12px;
  padding: 12px;
}

.chat-input :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  padding: 8px;
  box-shadow: none;
}

.chat-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.input-actions {
  flex-shrink: 0;
}

.send-btn {
  min-width: 40px;
  height: 40px;
  border-radius: 10px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #409eff;
  border: none;
  white-space: nowrap;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-footer {
  max-width: 800px;
  margin: 8px auto 0;
  text-align: center;
}

.hint {
  font-size: 12px;
  color: #909399;
}

/* 思考过程样式 */
.thinking-section {
  margin-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
  padding-bottom: 12px;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #667eea;
  font-size: 13px;
  font-weight: 500;
  transition: color 0.2s;
}

.thinking-toggle:hover {
  color: #764ba2;
}

.thinking-status {
  font-size: 12px;
  color: #e6a23c;
  margin-left: 8px;
}

.thinking-toggle .el-icon {
  transition: transform 0.3s ease;
}

.thinking-toggle .el-icon.rotate {
  transform: rotate(180deg);
}

.thinking-content {
  margin-top: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.thinking-step {
  margin-bottom: 12px;
  padding: 10px;
  background: #fff;
  border-radius: 6px;
  border-left: 3px solid #667eea;
}

.thinking-step:last-child {
  margin-bottom: 0;
}

.thinking-step.tool_call {
  border-left-color: #e6a23c;
}

.step-label {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  margin-bottom: 6px;
}

.step-content,
.step-params,
.step-result {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.step-params,
.step-result {
  margin-top: 4px;
  padding-left: 12px;
}

.step-result {
  color: #67c23a;
}

/* ==================== 行程侧边栏样式 ==================== */
.trip-sidebar {
  width: 360px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.close-btn {
  padding: 4px;
  margin-left: 8px;
  color: #909399;
}

.close-btn:hover {
  color: #667eea;
}

/* 显示侧边栏按钮 */
.show-sidebar-btn {
  position: fixed;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 80px;
  background: #409eff;
  border-radius: 8px 0 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  box-shadow: -4px 0 12px rgba(102, 126, 234, 0.2);
  transition: all 0.3s ease;
  z-index: 100;
}

.show-sidebar-btn:hover {
  width: 48px;
  box-shadow: -4px 0 16px rgba(102, 126, 234, 0.3);
}

.show-sidebar-btn .el-icon {
  font-size: 20px;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* 规划中状态 */
.planning-section {
  text-align: center;
  padding: 24px 0;
}

.planning-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}

.loading-icon {
  font-size: 20px;
  color: #667eea;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-text {
  font-size: 14px;
  color: #606266;
}

.step-info {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* 行程摘要 */
.trip-summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-card {
  border-radius: 12px;
}

.summary-card .card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.summary-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-info .info-row {
  display: flex;
  gap: 8px;
}

.summary-info .label {
  font-weight: 500;
  color: #909399;
  min-width: 60px;
}

.summary-info .value {
  color: #303133;
  flex: 1;
}

/* 每日行程摘要 */
.days-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.days-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  padding: 0 4px;
}

.day-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.day-num {
  font-size: 13px;
  font-weight: 600;
  color: #667eea;
}

.day-attractions {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.more-days {
  font-size: 12px;
  color: #909399;
  text-align: center;
  padding: 8px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: #909399;
}

.empty-state .el-icon {
  color: #c0c4cc;
  margin-bottom: 16px;
}

.empty-state p {
  margin: 4px 0;
  font-size: 14px;
}

.empty-state .hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* 响应式 */
@media (max-width: 1200px) {
  .chat-main.with-sidebar {
    flex: 0 0 calc(100% - 320px);
  }
  .trip-sidebar {
    width: 320px;
  }
}

@media (max-width: 900px) {
  .trip-sidebar {
    display: none;
  }
  .chat-main.with-sidebar {
    flex: 1;
  }
}
</style>
