import request from './index'

// ============ Trace API ============

// 获取 Trace 列表
export const getTraceList = (params) => {
  return request({
    url: '/admin/trace/traces',
    method: 'get',
    params
  })
}

// 获取 Trace 详情
export const getTraceDetail = (traceId) => {
  return request({
    url: `/admin/trace/traces/${traceId}`,
    method: 'get'
  })
}

// 删除 Trace
export const deleteTrace = (traceId) => {
  return request({
    url: `/admin/trace/traces/${traceId}`,
    method: 'delete'
  })
}

// 获取 Trace 统计数据
export const getTraceStatistics = (days = 7) => {
  return request({
    url: '/admin/trace/statistics',
    method: 'get',
    params: { days }
  })
}

// ============ Log API ============

// 获取日志文件列表
export const getLogFiles = () => {
  return request({
    url: '/admin/trace/logs/files',
    method: 'get'
  })
}

// 读取日志文件内容
export const readLogFile = (filename, offset = 0, limit = 1000) => {
  return request({
    url: `/admin/trace/logs/files/${filename}`,
    method: 'get',
    params: { offset, limit }
  })
}

export default {
  getTraceList,
  getTraceDetail,
  deleteTrace,
  getTraceStatistics,
  getLogFiles,
  readLogFile
}
