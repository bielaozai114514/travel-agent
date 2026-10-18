import request from './index'

/**
 * 获取任务详情
 */
export const getTaskDetail = (taskId) => {
  return request({
    url: `/task/tasks/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取用户任务列表
 */
export const getUserTasks = (params) => {
  return request({
    url: '/task/tasks',
    method: 'get',
    params
  })
}

/**
 * 取消任务
 */
export const cancelTask = (taskId) => {
  return request({
    url: `/task/tasks/${taskId}/cancel`,
    method: 'post'
  })
}

export default {
  getTaskDetail,
  getUserTasks,
  cancelTask
}
