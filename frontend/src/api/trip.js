import request from './index'

export const generateTripPlan = (data) => {
  return request({
    url: '/trip/plan',
    method: 'post',
    data,
    timeout: 180000
  })
}

export const getTripPlans = (params) => {
  return request({
    url: '/trip/plans',
    method: 'get',
    params
  })
}

export const getTripPlanById = (id) => {
  return request({
    url: `/trip/plans/${id}`,
    method: 'get'
  })
}

export const updateTripPlan = (id, data) => {
  return request({
    url: `/trip/plans/${id}`,
    method: 'put',
    data
  })
}

export const deleteTripPlan = (id) => {
  return request({
    url: `/trip/plans/${id}`,
    method: 'delete'
  })
}

export const generateTripPlanStream = async (data) => {
  const token = localStorage.getItem('token')
  const response = await fetch('/api/trip/plan/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data)
  })
  
  if (!response.ok) {
    throw new Error('请求失败')
  }
  
  return response.body.getReader()
}

/**
 * 后台生成行程计划
 */
export const generateTripPlanBackground = (data) => {
  return request({
    url: '/trip/plan/background',
    method: 'post',
    data,
    timeout: 30000
  })
}

/**
 * 从行程创建/获取会话
 */
export const createConversationFromTrip = (planId) => {
  return request({
    url: `/trip/plans/${planId}/conversation`,
    method: 'post'
  })
}

export default {
  generateTripPlan,
  getTripPlans,
  getTripPlanById,
  updateTripPlan,
  deleteTripPlan,
  generateTripPlanStream,
  generateTripPlanBackground,
  createConversationFromTrip
}
