<!-- src/App.vue -->
<template>
  <div id="app">
    <h1>猫娘女仆对话系统 喵~</h1>

    <!-- 聊天消息区域（固定高度，可滚动） -->
    <div class="chat-container">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message"
        :class="msg.role"
      >
        <strong>{{ msg.role === 'user' ? '主人' : '猫娘' }}:</strong>
        {{ msg.content }}
      </div>
      <!-- 空状态提示 -->
      <div v-if="messages.length === 0" class="empty-hint">
        输入问题开始对话吧～ 喵~
      </div>
    </div>

    <!-- 流式选项 -->
    <div class="options">
      <label>
        <input type="checkbox" v-model="useStream" />
        启用流式输出（逐字显示）
      </label>
    </div>

    <!-- 输入区域（始终在底部） -->
    <div class="input-area">
      <input
        v-model="inputText"
        @keyup.enter="sendMessage"
        placeholder="输入你的问题，然后回车 喵~"
        :disabled="loading"
        class="input-field"
      />
      <button @click="sendMessage" :disabled="loading" class="send-btn">
        {{ loading ? '思考中...' : '发送' }}
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error">
      ❌ {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import api from '@/api' // 你的 axios 封装（仅用于非流式）

const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const error = ref('')
const useStream = ref(false) // ← 新增：是否流式

// 滚动到底部的工具函数
const scrollToBottom = () => {
  nextTick(() => {
    const container = document.querySelector('.chat-container')
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

// 非流式：使用已有的 axios 封装
async function sendNonStreamMessage(text) {
  try {
    const data = await api.llm.chat(text)
    messages.value.push({ role: 'assistant', content: data.content })
    scrollToBottom()
  } catch (e) {
    error.value = e.message
    messages.value.push({ role: 'assistant', content: `出错了：${e.message}` })
  }
}

// 流式：使用原生 fetch + ReadableStream
async function sendStreamMessage(messagesHistory) {
  const encoder = new TextDecoder('utf-8', { stream: true });
  let fullContent = ''
  let buffer = ''

  try {
    const response = await fetch('http://192.168.101.11:8000/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        messages: messagesHistory, 
        stream: true 
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()

    // 初始化流式消息（空内容）
    messages.value.push({ role: 'assistant', content: '' })

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += encoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const parsed = JSON.parse(line)
          if (parsed.content === '[DONE]') break
          if (parsed.error) throw new Error(parsed.error)

          fullContent += parsed.content

          //替换数组最后一项为新对象
          const lastIndex = messages.value.length - 1
          messages.value[lastIndex] = {
            role: 'assistant',
            content: fullContent
          }

          await nextTick()
          scrollToBottom()
          await new Promise(resolve => setTimeout(resolve, 1))
        } catch (e) {
          console.warn('解析失败:', line, e)
        }
      }
    }
  } catch (e) {
    error.value = e.message || '流式请求失败'
    if (messages.value[messages.value.length - 1]?.role === 'assistant' && messages.value[messages.value.length - 1].content === fullContent) {
      // 如果最后一句是临时消息，替换为错误
      messages.value[messages.value.length - 1].content = `流式出错：${e.message}`
    } else {
      messages.value.push({ role: 'assistant', content: `流式出错：${e.message}` })
    }
    scrollToBottom()
  }
}

// 主发送函数
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
 
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  error.value = ''
  loading.value = true

  if (useStream.value) { 
    // 流式
    await sendStreamMessage([...messages.value])
  } else {
    const data = await api.llm.chat([...messages.value])
    messages.value.push({ role: 'assistant', content: data.content })
  }

  loading.value = false
}
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* 关键：body 使用 flex 布局 */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background-color: #f5f5f5;
  padding: 20px;
}

#app {
  width: 100%;
  max-width: 800px;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  overflow: hidden;
}

h1 {
  text-align: center;
  color: #ff69b4;
  padding: 20px;
  font-size: 24px;
  border-bottom: 1px solid #eee;
}

/* 聊天容器：自动占满中间区域 */
.chat-container {
  flex: 1; /* ← 关键！占据剩余空间 */
  min-height: 300px; /* 最小高度兜底 */
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background-color: #fafafa;
}

.empty-hint {
  color: #999;
  text-align: center;
  align-self: center;
  margin-top: auto;
  margin-bottom: auto;
}

.message {
  padding: 10px 14px;
  margin: 6px 0;
  border-radius: 12px;
  max-width: 80%;
  word-break: break-word;
  line-height: 1.5;
}

.message.user {
  background-color: #e3f2fd;
  margin-left: auto;
  text-align: right;
}

.message.assistant {
  background-color: #f1f8e9;
  margin-right: auto;
}

/* 流式选项区块 */
.options {
  margin-bottom: 12px;
  text-align: right;
  color: #666;
  font-size: 14px;
}
.options input {
  margin-right: 6px;
}

/* 输入区域：固定在底部 */
.input-area {
  display: flex;
  gap: 10px;
  padding: 16px;
  background: white;
  border-top: 1px solid #eee;
}

.input-field {
  flex: 1;
  padding: 12px 16px;
  font-size: 16px;
  border: 1px solid #ddd;
  border-radius: 24px;
  outline: none;
}

.input-field:focus {
  border-color: #ff69b4;
  box-shadow: 0 0 0 2px rgba(255, 105, 180, 0.2);
}

.send-btn {
  padding: 12px 24px;
  font-size: 16px;
  background-color: #ff69b4;
  color: white;
  border: none;
  border-radius: 24px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.send-btn:hover:not(:disabled) {
  background-color: #ff4da6;
}

.send-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error {
  color: #d32f2f;
  text-align: center;
  font-size: 14px;
  padding: 0 16px 16px;
}
</style>