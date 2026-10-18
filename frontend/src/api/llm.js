import request from '@/utils/request'

export function chat(messages) {
  return request({
    url: '/llm',
    method: 'post',
    data: { messages, stream: false}
  })
}