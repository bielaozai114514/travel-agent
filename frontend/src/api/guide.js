import request from './index'

// 获取攻略列表
export const getGuideList = (params) => {
  return request({
    url: '/guides',
    method: 'get',
    params
  })
}

// 获取我的未发布攻略
export const getMyUnpublishedGuides = () => {
  return request({
    url: '/guides/my-unpublished',
    method: 'get'
  })
}

// 获取攻略详情
export const getGuideDetail = (id, incrementView = true) => {
  return request({
    url: `/guides/${id}`,
    method: 'get',
    params: { increment_view: incrementView }
  })
}

// 创建攻略
export const createGuide = (data) => {
  return request({
    url: '/guides',
    method: 'post',
    data
  })
}

// 更新攻略
export const updateGuide = (id, data) => {
  return request({
    url: `/guides/${id}`,
    method: 'put',
    data
  })
}

// 删除攻略
export const deleteGuide = (id) => {
  return request({
    url: `/guides/${id}`,
    method: 'delete'
  })
}

// 分享攻略
export const shareGuide = (id) => {
  return request({
    url: `/guides/${id}/share`,
    method: 'post'
  })
}

// 审核攻略
export const reviewGuide = (id, data) => {
  return request({
    url: `/guides/${id}/review`,
    method: 'post',
    data
  })
}

// 获取攻略评论
export const getGuideComments = (id, params) => {
  return request({
    url: `/guides/${id}/comments`,
    method: 'get',
    params
  })
}

// 创建评论
export const createComment = (id, data) => {
  return request({
    url: `/guides/${id}/comments`,
    method: 'post',
    data
  })
}

// 删除评论
export const deleteComment = (commentId) => {
  return request({
    url: `/guides/comments/${commentId}`,
    method: 'delete'
  })
}

// 检查点赞状态
export const checkLikeStatus = (id) => {
  return request({
    url: `/guides/${id}/like`,
    method: 'get'
  })
}

// 切换点赞状态
export const toggleLike = (id) => {
  return request({
    url: `/guides/${id}/like`,
    method: 'post'
  })
}

// RAG搜索攻略
export const ragSearchGuides = (data) => {
  return request({
    url: '/guides/rag/search',
    method: 'post',
    data
  })
}

// 攻略搜索（带LLM优化选项）
export const ragSearchGuidesWithOptions = (query, options = {}) => {
  return request({
    url: '/guides/rag/search',
    method: 'post',
    data: {
      query,
      city: options.city,
      limit: options.limit || 5,
      min_score: options.min_score || 0.3,
      use_llm_optimization: options.use_llm_optimization,
      enable_query_rewrite: options.enable_query_rewrite,
      enable_keyword_extraction: options.enable_keyword_extraction
    }
  })
}

// 攻略转行程
export const guideToTrip = (guideId, data) => {
  return request({
    url: `/guides/${guideId}/to-trip`,
    method: 'post',
    data
  })
}

// AI生成攻略（LLM调用耗时较长，单独设置超时）
export const generateGuide = (data) => {
  return request({
    url: '/guides/generate',
    method: 'post',
    data,
    timeout: 120000
  })
}

export default {
  getGuideList,
  getGuideDetail,
  createGuide,
  updateGuide,
  deleteGuide,
  shareGuide,
  reviewGuide,
  getGuideComments,
  createComment,
  deleteComment,
  checkLikeStatus,
  toggleLike,
  ragSearchGuides,
  guideToTrip,
  generateGuide
}
