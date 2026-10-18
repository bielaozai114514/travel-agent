import request from './index'

/**
 * 获取会话列表
 */
export function getConversations(params) {
  return request({
    url: '/conversations',
    method: 'get',
    params
  })
}

/**
 * 创建新会话
 */
export function createConversation(data) {
  return request({
    url: '/conversations',
    method: 'post',
    data
  })
}

/**
 * 获取会话详情
 */
export function getConversationDetail(id) {
  return request({
    url: `/conversations/${id}`,
    method: 'get'
  })
}

/**
 * 更新会话标题
 */
export function updateConversation(id, data) {
  return request({
    url: `/conversations/${id}`,
    method: 'put',
    data
  })
}

/**
 * 删除会话
 */
export function deleteConversation(id) {
  return request({
    url: `/conversations/${id}`,
    method: 'delete'
  })
}

/**
 * 获取会话消息列表
 */
export function getMessages(conversationId) {
  return request({
    url: `/conversations/${conversationId}/messages`,
    method: 'get'
  })
}

/**
 * 发送消息（非流式）
 */
export function sendMessage(data) {
  return request({
    url: '/chat/send',
    method: 'post',
    params: data
  })
}

/**
 * 发送消息（流式）
 * 返回ReadableStream reader
 */
export async function sendMessageStream(data) {
  console.log('sendMessageStream 被调用:', data)
  const { conversationId, content } = data
  const token = localStorage.getItem('access_token')
  console.log('Token 存在:', !!token)
  
  // 使用相对路径，通过Vite代理访问
  const url = '/api/chat/stream'
  console.log('请求URL:', url)
  
  try {
    console.log('开始发送请求...')
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        conversation_id: conversationId || null,
        content: content
      })
    })
    console.log('请求完成，状态:', response.status)
    console.log('响应头:', Object.fromEntries(response.headers.entries()))
  
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      console.log('错误数据:', errorData)
      throw new Error(errorData.detail || `请求失败: ${response.status}`)
    }
    
    console.log('响应体:', response.body)
    return response.body.getReader()
  } catch (error) {
    console.error('sendMessageStream 错误:', error)
    throw error
  }
}

/**
 * 将会话关联到行程
 */
export function linkConversationToTrip(conversationId, tripId) {
  return request({
    url: `/chat/conversation/${conversationId}/link-trip`,
    method: 'post',
    params: { trip_id: tripId }
  })
}
